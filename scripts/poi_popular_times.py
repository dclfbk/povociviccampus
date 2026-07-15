#!/usr/bin/env python3
"""
poi_popular_times.py
====================
A partire da un GeoJSON (poligono/multipoligono di una zona, es. una
circoscrizione), estrae tutti i punti di interesse (POI) interni alla zona
e per ciascuno recupera i "Popular Times" di Google Maps:

  - istogramma affluenza per giorno della settimana e fascia oraria (0-100)
  - affluenza "live" corrente (se disponibile)
  - tempo medio di permanenza e di attesa (se disponibili)
  - rating e numero di recensioni

NOTA BENE: Google NON fornisce conteggi assoluti di persone. I valori sono
percentuali relative al picco massimo del singolo luogo (100 = ora di punta
di quel posto). Non esiste un "numero di persone".

Due modalità di scoperta dei POI:

  --mode overpass   (default, gratuito, nessuna chiave)
      POI da OpenStreetMap via Overpass API (amenity/shop/tourism/leisure...),
      poi ricerca dei popular times su Google per "nome + indirizzo/coord".

  --mode google     (richiede --api-key, API Places a pagamento oltre quota)
      Copertura del poligono con una griglia di Nearby Search di Google
      Places, dedup per place_id, filtro punto-nel-poligono, poi popular
      times per ogni place_id.

Output (nella cartella --outdir):
  - places.csv            : un POI per riga (metadati + flag has_populartimes)
  - popular_times_long.csv: formato lungo -> place, giorno, ora, affluenza
  - places.geojson        : POI georiferiti con popular times nelle properties

Dipendenze:
  pip install shapely requests
  pip install --upgrade git+https://github.com/GrocerCheck/LivePopularTimes

Esempi:
  python3 poi_popular_times.py circoscrizione.geojson
  python3 poi_popular_times.py circoscrizione.geojson --mode google \
      --api-key $GOOGLE_KEY --radius 300
  python3 poi_popular_times.py circoscrizione.geojson --categories amenity shop
"""

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

import requests
from shapely.geometry import shape, Point, mapping

# ---------------------------------------------------------------------------
# LivePopularTimes: usata per lo scraping dell'istogramma popular times.
# ---------------------------------------------------------------------------
try:
    import livepopulartimes
except ImportError:
    livepopulartimes = None

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GOOGLE_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
GOOGLE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

DAYS_IT = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

# Categorie OSM che tipicamente hanno popular times su Google
DEFAULT_OSM_KEYS = ["amenity", "shop", "tourism", "leisure", "office", "healthcare"]


# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------

def load_polygon(geojson_path):
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    if gj.get("type") == "FeatureCollection":
        geoms = [shape(feat["geometry"]) for feat in gj["features"]]
        from shapely.ops import unary_union
        return unary_union(geoms)
    if gj.get("type") == "Feature":
        return shape(gj["geometry"])
    return shape(gj)


def meters_to_deg(lat, dx_m, dy_m):
    """Converte metri in gradi (approssimazione locale)."""
    dlat = dy_m / 110_574.0
    dlon = dx_m / (111_320.0 * math.cos(math.radians(lat)))
    return dlon, dlat


def circle_grid(polygon, radius_m):
    """Genera centri di una griglia esagonale di cerchi di raggio radius_m
    che coprono il poligono (per le Nearby Search di Google)."""
    minx, miny, maxx, maxy = polygon.bounds
    lat0 = (miny + maxy) / 2
    step_x_m = radius_m * math.sqrt(3)          # spaziatura orizzontale
    step_y_m = radius_m * 1.5                   # spaziatura verticale
    dlon, dlat = meters_to_deg(lat0, step_x_m, step_y_m)
    buffered = polygon.buffer(meters_to_deg(lat0, radius_m, radius_m)[0])

    centers = []
    row = 0
    y = miny
    while y <= maxy + dlat:
        offset = (dlon / 2) if (row % 2) else 0.0
        x = minx + offset
        while x <= maxx + dlon:
            if buffered.contains(Point(x, y)):
                centers.append((y, x))  # (lat, lng)
            x += dlon
        y += dlat
        row += 1
    return centers


# ---------------------------------------------------------------------------
# Scoperta POI — modalità Overpass (OSM)
# ---------------------------------------------------------------------------

def fetch_pois_overpass(polygon, keys, timeout=180):
    """Scarica da Overpass tutti gli elementi con i tag richiesti nel bbox
    del poligono, poi filtra punto-nel-poligono con shapely."""
    minx, miny, maxx, maxy = polygon.bounds
    bbox = f"{miny},{minx},{maxy},{maxx}"
    clauses = "".join(
        f'nwr["{k}"]["name"]({bbox});' for k in keys
    )
    query = f"[out:json][timeout:{timeout}];({clauses});out center tags;"
    print(f"[overpass] query su bbox {bbox} per chiavi {keys} ...")
    r = requests.post(OVERPASS_URL, data={"data": query}, timeout=timeout + 30)
    r.raise_for_status()
    elements = r.json().get("elements", [])
    print(f"[overpass] {len(elements)} elementi nel bbox")

    pois = []
    for el in elements:
        if el["type"] == "node":
            lat, lng = el["lat"], el["lon"]
        else:
            c = el.get("center")
            if not c:
                continue
            lat, lng = c["lat"], c["lon"]
        if not polygon.contains(Point(lng, lat)):
            continue
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        category = next(
            (f"{k}={tags[k]}" for k in keys if k in tags), ""
        )
        addr = " ".join(filter(None, [
            tags.get("addr:street"), tags.get("addr:housenumber"),
            tags.get("addr:postcode"), tags.get("addr:city"),
        ]))
        pois.append({
            "source_id": f"{el['type']}/{el['id']}",
            "name": name,
            "category": category,
            "address": addr,
            "lat": lat,
            "lng": lng,
        })
    print(f"[overpass] {len(pois)} POI con nome dentro il poligono")
    return pois


# ---------------------------------------------------------------------------
# Scoperta POI — modalità Google Places
# ---------------------------------------------------------------------------

# Tipi Places (legacy) da interrogare per cella: ogni type ha il suo tetto
# di 60 risultati, quindi interrogare per tipo aumenta molto il richiamo.
DEFAULT_GOOGLE_TYPES = [
    "pharmacy", "supermarket", "grocery_or_supermarket", "restaurant",
    "cafe", "bar", "bakery", "store", "gym", "bank", "post_office",
    "tourist_attraction", "library", "park", "lodging",
]


def _nearby_query(params, polygon, seen, pause):
    """Esegue una Nearby Search (con paginazione) e accumula in `seen`."""
    while True:
        r = requests.get(GOOGLE_NEARBY_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            print(f"[google] status {status}: {data.get('error_message','')}",
                  file=sys.stderr)
            return
        for res in data.get("results", []):
            pid = res["place_id"]
            loc = res["geometry"]["location"]
            if pid in seen:
                continue
            if not polygon.contains(Point(loc["lng"], loc["lat"])):
                continue
            seen[pid] = {
                "source_id": pid,
                "name": res.get("name", ""),
                "category": ",".join(res.get("types", [])[:3]),
                "address": res.get("vicinity", ""),
                "lat": loc["lat"],
                "lng": loc["lng"],
            }
        token = data.get("next_page_token")
        if not token:
            return
        time.sleep(pause)  # il token impiega ~2s ad attivarsi
        params = {"pagetoken": token, "key": params["key"]}


def fetch_pois_google(polygon, api_key, radius_m=300, pause=2.0,
                      types=None):
    """Copre il poligono con Nearby Search per ciascun `type`; dedup per
    place_id; filtra punto-nel-poligono.

    NOTA: senza `type`, Google restituisce solo i luoghi 'prominenti'
    (spesso solo hotel/B&B). Interrogare per tipo è essenziale per
    ottenere farmacie, supermercati, ristoranti, ecc."""
    types = types or DEFAULT_GOOGLE_TYPES
    centers = circle_grid(polygon, radius_m)
    total_q = len(centers) * len(types)
    print(f"[google] griglia di {len(centers)} cerchi (r={radius_m} m) "
          f"x {len(types)} tipi = ~{total_q} query Nearby Search")
    seen = {}
    for i, (lat, lng) in enumerate(centers, 1):
        for t in types:
            params = {"location": f"{lat},{lng}", "radius": radius_m,
                      "type": t, "key": api_key}
            _nearby_query(params, polygon, seen, pause)
            time.sleep(0.05)
        if i % 10 == 0:
            print(f"[google] {i}/{len(centers)} celle, {len(seen)} POI unici")
    print(f"[google] totale {len(seen)} POI dentro il poligono")
    return list(seen.values())


# ---------------------------------------------------------------------------
# Popular times
# ---------------------------------------------------------------------------

def get_popular_times(poi, api_key=None, city_hint=""):
    """Recupera i popular times per un POI. Ritorna il dict di
    livepopulartimes oppure None."""
    if livepopulartimes is None:
        raise RuntimeError(
            "Manca la libreria LivePopularTimes: "
            "pip install --upgrade git+https://github.com/GrocerCheck/LivePopularTimes"
        )
    try:
        if api_key and poi["source_id"].startswith("ChIJ"):
            return livepopulartimes.get_populartimes_by_PlaceID(
                api_key, poi["source_id"])
        # Modalità senza API key: ricerca per "nome, indirizzo/città"
        address = poi["address"] or city_hint
        query = f"{poi['name']}, {address}" if address else poi["name"]
        return livepopulartimes.get_populartimes_by_address(query)
    except Exception as e:  # la libreria può fallire su POI senza scheda
        print(f"  [warn] {poi['name']}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_outputs(pois, outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # places.csv -------------------------------------------------------------
    with open(outdir / "places.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "name", "category", "address", "lat", "lng",
                    "rating", "rating_n", "current_popularity",
                    "time_spent_min", "has_populartimes"])
        for p in pois:
            pt = p.get("populartimes") or {}
            ts = pt.get("time_spent") or [None, None]
            w.writerow([
                p["source_id"], p["name"], p["category"], p["address"],
                p["lat"], p["lng"],
                pt.get("rating"), pt.get("rating_n"),
                pt.get("current_popularity"),
                ts[0] if ts else None,
                bool(pt.get("populartimes")),
            ])

    # popular_times_long.csv ---------------------------------------------------
    with open(outdir / "popular_times_long.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "name", "day", "day_it", "hour",
                    "popularity_percent"])
        for p in pois:
            pt = p.get("populartimes") or {}
            for day_idx, day in enumerate(pt.get("populartimes") or []):
                for hour, val in enumerate(day["data"]):
                    w.writerow([p["source_id"], p["name"], day["name"],
                                DAYS_IT[day_idx], hour, val])

    # places.geojson -----------------------------------------------------------
    features = []
    for p in pois:
        props = {k: v for k, v in p.items() if k not in ("lat", "lng")}
        features.append({
            "type": "Feature",
            "geometry": mapping(Point(p["lng"], p["lat"])),
            "properties": props,
        })
    with open(outdir / "places.geojson", "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f,
                  ensure_ascii=False)

    print(f"\nOutput scritti in {outdir}/ :")
    print("  places.csv, popular_times_long.csv, places.geojson")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("geojson", help="GeoJSON con il poligono della zona")
    ap.add_argument("--mode", choices=["overpass", "google"], default="overpass")
    ap.add_argument("--api-key", help="Google API key (per --mode google)")
    ap.add_argument("--radius", type=int, default=300,
                    help="raggio in metri dei cerchi Nearby Search (google)")
    ap.add_argument("--categories", nargs="+", default=DEFAULT_OSM_KEYS,
                    help="chiavi OSM da cercare (overpass)")
    ap.add_argument("--types", nargs="+", default=None,
                    help="tipi Google Places da interrogare per cella "
                         "(default: lista predefinita di 15 tipi)")
    ap.add_argument("--city-hint", default="",
                    help="suffisso per disambiguare la ricerca, es. 'Povo, Trento'")
    ap.add_argument("--outdir", default="output")
    ap.add_argument("--sleep", type=float, default=2.0,
                    help="pausa (s) tra richieste popular times")
    ap.add_argument("--limit", type=int, default=0,
                    help="limita il numero di POI (0 = tutti), utile per test")
    ap.add_argument("--skip-populartimes", action="store_true",
                    help="solo scoperta POI, senza popular times")
    args = ap.parse_args()

    polygon = load_polygon(args.geojson)
    print(f"Poligono caricato: bounds={tuple(round(b,5) for b in polygon.bounds)}")

    if args.mode == "google":
        if not args.api_key:
            ap.error("--mode google richiede --api-key")
        pois = fetch_pois_google(polygon, args.api_key, args.radius,
                                 types=args.types)
    else:
        pois = fetch_pois_overpass(polygon, args.categories)

    if args.limit:
        pois = pois[: args.limit]

    if not args.skip_populartimes:
        print(f"\nRecupero popular times per {len(pois)} POI "
              f"(pausa {args.sleep}s tra richieste)...")
        found = 0
        for i, p in enumerate(pois, 1):
            pt = get_popular_times(p, api_key=args.api_key,
                                   city_hint=args.city_hint)
            p["populartimes"] = pt
            if pt and pt.get("populartimes"):
                found += 1
            print(f"  [{i}/{len(pois)}] {p['name']}: "
                  f"{'OK' if pt and pt.get('populartimes') else '—'}")
            time.sleep(args.sleep)
        print(f"\nPopular times trovati per {found}/{len(pois)} POI "
              f"(molti POI piccoli non hanno dati sufficienti su Google).")

    write_outputs(pois, args.outdir)


if __name__ == "__main__":
    main()
