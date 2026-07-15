#!/usr/bin/env python3
"""Associa coordinate ai servizi di Povo usando esclusivamente file POI locali.

Non usa geocoding online. Legge un CSV dei servizi e uno o piu file POI
(CSV, GeoJSON, GPKG, SHP), cerca la corrispondenza migliore per nome e indirizzo,
e produce un CSV pronto per 05_accessibilita_servizi.py.
"""
from __future__ import annotations

import argparse
import math
import re
import unicodedata
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd
from rapidfuzz import fuzz, process

NAME_CANDIDATES = (
    "name", "nome", "denominazione", "title", "titolo", "label",
    "fsq_name", "poi_name", "display_name",
)
ADDRESS_CANDIDATES = (
    "address", "indirizzo", "indirizzo:", "formatted_address", "street_address",
    "addr:full", "addr_full", "vicinity", "location",
)
LAT_CANDIDATES = ("latitude", "lat", "y")
LON_CANDIDATES = ("longitude", "lon", "lng", "x")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--services", required=True, help="CSV dei servizi da arricchire")
    p.add_argument("--poi", required=True, nargs="+", help="Uno o piu file POI locali")
    p.add_argument("--out", default="servizi_povo_geocodificati.csv")
    p.add_argument("--review-out", default="servizi_povo_da_verificare.csv")
    p.add_argument("--candidates-out", default="servizi_povo_candidati_match.csv")
    p.add_argument("--name-field", default="name", help="Campo nome nel CSV servizi")
    p.add_argument(
        "--address-field", default="Indirizzo:", help="Campo indirizzo nel CSV servizi"
    )
    p.add_argument(
        "--category-field", default="Ambito di appartenenza del servizio:",
        help="Campo categoria nel CSV servizi",
    )
    p.add_argument("--min-score", type=float, default=72.0)
    p.add_argument("--auto-score", type=float, default=86.0)
    p.add_argument("--top-k", type=int, default=5)
    return p.parse_args()


def norm_text(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = str(value).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    replacements = {
        "piazza giuseppe manci": "piazza manci",
        "piazza g. manci": "piazza manci",
        "p.zza": "piazza",
        "via don t. dallafior": "via don tommaso dallafior",
        "via don t.dallafior": "via don tommaso dallafior",
        "spre'": "spre",
        "sprè": "spre",
        "sale'": "sale",
        "salè": "sale",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)
    s = re.sub(r"\b(?:38123|tn|trento|italia|povo)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def find_col(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    lookup = {str(c).strip().lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lookup:
            return str(lookup[cand.lower()])
    for c in columns:
        nc = norm_text(c)
        if any(norm_text(x) == nc for x in candidates):
            return str(c)
    return None


def read_poi(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        lat_col = find_col(df.columns, LAT_CANDIDATES)
        lon_col = find_col(df.columns, LON_CANDIDATES)
        if not lat_col or not lon_col:
            raise ValueError(f"{path}: colonne coordinate non trovate")
        out = df.copy()
        out["latitude"] = pd.to_numeric(out[lat_col], errors="coerce")
        out["longitude"] = pd.to_numeric(out[lon_col], errors="coerce")
    else:
        gdf = gpd.read_file(path)
        if gdf.empty:
            return pd.DataFrame()
        if gdf.crs is None:
            raise ValueError(f"{path}: CRS mancante")
        gdf = gdf.to_crs(4326)
        # Per geometrie non puntuali usa il punto rappresentativo.
        pts = gdf.geometry.apply(
            lambda g: g if g is not None and g.geom_type == "Point" else (
                g.representative_point() if g is not None and not g.is_empty else None
            )
        )
        out = pd.DataFrame(gdf.drop(columns="geometry"))
        out["longitude"] = pts.apply(lambda p: p.x if p is not None else None)
        out["latitude"] = pts.apply(lambda p: p.y if p is not None else None)

    name_col = find_col(out.columns, NAME_CANDIDATES)
    address_col = find_col(out.columns, ADDRESS_CANDIDATES)
    if not name_col:
        raise ValueError(f"{path}: campo nome POI non trovato; colonne: {list(out.columns)}")
    out = out.loc[out["latitude"].notna() & out["longitude"].notna()].copy()
    out["poi_name"] = out[name_col].astype(str)
    out["poi_address"] = out[address_col].astype(str) if address_col else ""
    out["poi_source"] = path.name
    out["poi_name_norm"] = out["poi_name"].map(norm_text)
    out["poi_address_norm"] = out["poi_address"].map(norm_text)
    return out[[
        "poi_name", "poi_address", "latitude", "longitude", "poi_source",
        "poi_name_norm", "poi_address_norm",
    ]]


def score_pair(service_name: str, service_addr: str, poi_name: str, poi_addr: str) -> float:
    name_score = max(
        fuzz.token_set_ratio(service_name, poi_name),
        fuzz.WRatio(service_name, poi_name),
    )
    if service_addr and poi_addr:
        addr_score = max(
            fuzz.token_set_ratio(service_addr, poi_addr),
            fuzz.partial_ratio(service_addr, poi_addr),
        )
        # Il nome pesa di piu, ma l'indirizzo risolve omonimie/sedi multiple.
        return 0.68 * name_score + 0.32 * addr_score
    return float(name_score)


def main() -> int:
    args = parse_args()
    services = pd.read_csv(args.services, dtype=str, keep_default_na=False)
    for col in (args.name_field, args.address_field):
        if col not in services.columns:
            raise ValueError(f"Campo mancante nel CSV servizi: {col}")

    poi_frames = [read_poi(Path(p)) for p in args.poi]
    poi = pd.concat([x for x in poi_frames if not x.empty], ignore_index=True)
    if poi.empty:
        raise ValueError("Nessun POI con coordinate utilizzabile")
    poi = poi.drop_duplicates(
        subset=["poi_name_norm", "poi_address_norm", "latitude", "longitude"]
    ).reset_index(drop=True)

    rows = []
    candidate_rows = []
    for idx, srow in services.iterrows():
        sname = norm_text(srow[args.name_field])
        saddr = norm_text(srow[args.address_field])
        scored = []
        for pidx, prow in poi.iterrows():
            score = score_pair(sname, saddr, prow["poi_name_norm"], prow["poi_address_norm"])
            if score >= args.min_score:
                scored.append((score, pidx))
        scored.sort(reverse=True)
        top = scored[: args.top_k]

        best = poi.loc[top[0][1]] if top else None
        best_score = float(top[0][0]) if top else 0.0
        second_score = float(top[1][0]) if len(top) > 1 else 0.0
        gap = best_score - second_score
        auto_ok = bool(top and best_score >= args.auto_score and (gap >= 4 or best_score >= 94))

        out = dict(srow)
        out["latitude"] = float(best["latitude"]) if best is not None else ""
        out["longitude"] = float(best["longitude"]) if best is not None else ""
        out["coord_source"] = best["poi_source"] if best is not None else ""
        out["matched_poi_name"] = best["poi_name"] if best is not None else ""
        out["matched_poi_address"] = best["poi_address"] if best is not None else ""
        out["match_score"] = round(best_score, 2)
        out["match_gap"] = round(gap, 2)
        out["match_status"] = "automatico" if auto_ok else ("da_verificare" if top else "non_trovato")
        rows.append(out)

        for rank, (score, pidx) in enumerate(top, 1):
            p = poi.loc[pidx]
            candidate_rows.append({
                "service_row": idx,
                "service_name": srow[args.name_field],
                "service_address": srow[args.address_field],
                "rank": rank,
                "score": round(float(score), 2),
                "poi_name": p["poi_name"],
                "poi_address": p["poi_address"],
                "latitude": p["latitude"],
                "longitude": p["longitude"],
                "poi_source": p["poi_source"],
            })

    result = pd.DataFrame(rows)
    # Aggiunge alias standard richiesti dallo script 05.
    if args.category_field in result.columns and "map_category" not in result.columns:
        result["map_category"] = result[args.category_field]
    if args.address_field in result.columns and "address" not in result.columns:
        result["address"] = result[args.address_field]

    result.to_csv(args.out, index=False, encoding="utf-8")
    result.loc[result["match_status"] != "automatico"].to_csv(
        args.review_out, index=False, encoding="utf-8"
    )
    pd.DataFrame(candidate_rows).to_csv(args.candidates_out, index=False, encoding="utf-8")

    print(f"Servizi: {len(result)}")
    print(f"Match automatici: {(result['match_status'] == 'automatico').sum()}")
    print(f"Da verificare: {(result['match_status'] == 'da_verificare').sum()}")
    print(f"Non trovati: {(result['match_status'] == 'non_trovato').sum()}")
    print(f"Output: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
