#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scarica i PDF delle pagine:
"Seduta Consiglio circoscrizionale Povo ..."

Fonte:
https://www.comune.trento.it/content/search?SearchText=seduta+consiglio+Povo&Class%5B%5D=25

Requisiti:
    pip install requests beautifulsoup4 lxml tqdm

Uso:
    python scarica_sedute_povo.py
"""

from __future__ import annotations

import csv
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


BASE_URL = "https://www.comune.trento.it"
SEARCH_URL = "https://www.comune.trento.it/content/search"

QUERY = "seduta consiglio Povo"
CLASS_VALUE = "25"

OUT_DIR = Path("sedute_consiglio_povo")
PDF_DIR = OUT_DIR / "pdf"
HTML_DIR = OUT_DIR / "html"
METADATA_CSV = OUT_DIR / "metadata.csv"

# Filtro stretto: prende solo le sedute del Consiglio, non le Commissioni.
TITLE_PREFIX = "Seduta Consiglio circoscrizionale Povo"

REQUEST_DELAY = 0.5
TIMEOUT = 30
MAX_PAGES = 100


def slugify(text: str, max_len: int = 140) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len].strip("-") or "file"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; ricerca-civica-povo/0.1; +https://www.comune.trento.it)"
            )
        }
    )
    return s


def get_soup(session: requests.Session, url: str, params: dict | None = None) -> BeautifulSoup:
    r = session.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def find_result_links(soup: BeautifulSoup) -> list[dict]:
    """
    Estrae i risultati che hanno titolo:
    Seduta Consiglio circoscrizionale Povo ...
    """
    results = []

    for a in soup.find_all("a", href=True):
        title = clean_text(a.get_text(" "))
        if not title.startswith(TITLE_PREFIX):
            continue

        url = urljoin(BASE_URL, a["href"])

        # Prova a recuperare uno snippet vicino al link.
        snippet = ""
        parent = a.find_parent()
        if parent:
            candidate = parent.find_next_sibling()
            if candidate:
                snippet = clean_text(candidate.get_text(" "))

        results.append(
            {
                "title": title,
                "page_url": url,
                "snippet": snippet,
            }
        )

    # Deduplica mantenendo ordine
    seen = set()
    unique = []
    for item in results:
        if item["page_url"] not in seen:
            unique.append(item)
            seen.add(item["page_url"])

    return unique


def find_next_page_url(soup: BeautifulSoup) -> str | None:
    """
    Cerca un link di paginazione "Successivo".
    """
    for a in soup.find_all("a", href=True):
        label = clean_text(a.get_text(" ")).lower()
        if label == "successivo":
            return urljoin(BASE_URL, a["href"])
    return None


def scrape_search_results(session: requests.Session) -> list[dict]:
    """
    Scorre tutte le pagine della ricerca.
    """
    all_results = []
    seen_pages = set()

    params = {
        "SearchText": QUERY,
        "Class[]": CLASS_VALUE,
    }

    url = SEARCH_URL

    for _ in range(MAX_PAGES):
        if url in seen_pages:
            break
        seen_pages.add(url)

        soup = get_soup(session, url, params=params)
        params = None

        page_results = find_result_links(soup)
        all_results.extend(page_results)

        next_url = find_next_page_url(soup)
        if not next_url:
            break

        url = next_url
        time.sleep(REQUEST_DELAY)

    # Deduplica risultati
    seen = set()
    unique = []
    for item in all_results:
        if item["page_url"] not in seen:
            unique.append(item)
            seen.add(item["page_url"])

    return unique


def extract_date_from_title(title: str) -> str:
    """
    Estrae una data testuale dal titolo, senza normalizzarla.
    Esempio: "mercoledì 20 maggio 2026"
    """
    m = re.search(r" di (.+)$", title)
    return clean_text(m.group(1)) if m else ""


def find_pdf_links(soup: BeautifulSoup) -> list[dict]:
    """
    Trova link PDF nella pagina della seduta.
    Il sito spesso usa URL tipo /ocmultibinary/download/.../file/...
    """
    pdfs = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        label = clean_text(a.get_text(" "))

        looks_like_pdf = ".pdf" in href.lower()
        looks_like_download = "/download/" in href.lower() or "ocmultibinary" in href.lower()

        if not (looks_like_pdf or looks_like_download):
            continue

        url = urljoin(BASE_URL, href)

        # Evita link sociali o immagini accidentalmente presi
        if "comune.trento.it" not in urlparse(url).netloc:
            continue

        pdfs.append(
            {
                "label": label or "documento",
                "pdf_url": url,
            }
        )

    # Deduplica
    seen = set()
    unique = []
    for item in pdfs:
        if item["pdf_url"] not in seen:
            unique.append(item)
            seen.add(item["pdf_url"])

    return unique


def filename_from_response_or_url(response: requests.Response, fallback: str) -> str:
    """
    Prova a ricavare il nome file dal Content-Disposition o dall'URL.
    """
    cd = response.headers.get("content-disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.I)
    if m:
        return slugify(m.group(1).replace("%20", " ")) + ".pdf"

    path = urlparse(response.url).path
    candidate = Path(path).name
    if candidate and candidate.lower().endswith(".pdf"):
        return slugify(candidate[:-4]) + ".pdf"

    return slugify(fallback) + ".pdf"


def download_file(session: requests.Session, url: str, out_path: Path) -> tuple[bool, str]:
    """
    Scarica un file se non già presente.
    """
    if out_path.exists() and out_path.stat().st_size > 0:
        return True, "already_exists"

    try:
        with session.get(url, stream=True, timeout=TIMEOUT) as r:
            r.raise_for_status()

            content_type = r.headers.get("content-type", "").lower()
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                # Alcuni download non dichiarano PDF correttamente: salvo comunque,
                # ma segnalo nel metadata.
                note = f"content-type={content_type or 'unknown'}"
            else:
                note = "ok"

            with out_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)

        return True, note

    except Exception as e:
        return False, str(e)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    session = make_session()

    print("Cerco le sedute del Consiglio circoscrizionale di Povo...")
    results = scrape_search_results(session)
    print(f"Trovate {len(results)} pagine candidate.")

    rows = []

    for item in tqdm(results, desc="Scarico documenti"):
        title = item["title"]
        page_url = item["page_url"]
        date_text = extract_date_from_title(title)

        page_slug = slugify(title)
        page_html_path = HTML_DIR / f"{page_slug}.html"

        try:
            r = session.get(page_url, timeout=TIMEOUT)
            r.raise_for_status()
            page_html_path.write_text(r.text, encoding="utf-8")
            soup = BeautifulSoup(r.text, "lxml")
        except Exception as e:
            rows.append(
                {
                    "title": title,
                    "date_text": date_text,
                    "page_url": page_url,
                    "document_label": "",
                    "pdf_url": "",
                    "local_file": "",
                    "status": "page_error",
                    "note": str(e),
                }
            )
            continue

        pdf_links = find_pdf_links(soup)

        if not pdf_links:
            rows.append(
                {
                    "title": title,
                    "date_text": date_text,
                    "page_url": page_url,
                    "document_label": "",
                    "pdf_url": "",
                    "local_file": "",
                    "status": "no_pdf_found",
                    "note": "",
                }
            )
            continue

        for i, pdf in enumerate(pdf_links, start=1):
            label = pdf["label"]
            pdf_url = pdf["pdf_url"]

            # Scarico prima con un nome temporaneo, poi provo a ricavare un nome sensato.
            try:
                head_or_get = session.get(pdf_url, stream=True, timeout=TIMEOUT)
                head_or_get.raise_for_status()

                real_name = filename_from_response_or_url(
                    head_or_get,
                    fallback=f"{page_slug}-{i}-{label}",
                )
                local_name = f"{page_slug}__{i:02d}__{real_name}"
                local_path = PDF_DIR / local_name

                if local_path.exists() and local_path.stat().st_size > 0:
                    ok, note = True, "already_exists"
                    head_or_get.close()
                else:
                    content_type = head_or_get.headers.get("content-type", "").lower()
                    note = "ok" if "pdf" in content_type or pdf_url.lower().endswith(".pdf") else f"content-type={content_type or 'unknown'}"

                    with local_path.open("wb") as f:
                        for chunk in head_or_get.iter_content(chunk_size=1024 * 64):
                            if chunk:
                                f.write(chunk)
                    head_or_get.close()
                    ok = True

                status = "downloaded" if ok else "download_error"

            except Exception as e:
                local_path = Path("")
                status = "download_error"
                note = str(e)

            rows.append(
                {
                    "title": title,
                    "date_text": date_text,
                    "page_url": page_url,
                    "document_label": label,
                    "pdf_url": pdf_url,
                    "local_file": str(local_path) if local_path else "",
                    "status": status,
                    "note": note,
                }
            )

            time.sleep(REQUEST_DELAY)

    with METADATA_CSV.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "title",
            "date_text",
            "page_url",
            "document_label",
            "pdf_url",
            "local_file",
            "status",
            "note",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"Finito.")
    print(f"PDF salvati in: {PDF_DIR}")
    print(f"HTML salvati in: {HTML_DIR}")
    print(f"Metadata: {METADATA_CSV}")


if __name__ == "__main__":
    main()
