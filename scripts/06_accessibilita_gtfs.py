#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import Point


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Integra rete pedonale, sezioni censuarie e GTFS per le linee 5 e 13."
    )
    p.add_argument("--graph", required=True, help="GraphML della rete pedonale")
    p.add_argument("--sections", required=True, help="GeoPackage/GeoJSON con le sezioni")
    p.add_argument("--sections-layer", default=None, help="Layer del GeoPackage")
    p.add_argument("--gtfs", required=True, help="Archivio GTFS .zip")
    p.add_argument("--routes", nargs="+", default=["5", "13"], help="Linee da analizzare")
    p.add_argument("--date", default=None, help="Data di servizio YYYY-MM-DD; default: prossimo feriale disponibile")
    p.add_argument("--time-start", default="07:00:00", help="Inizio fascia oraria")
    p.add_argument("--time-end", default="20:00:00", help="Fine fascia oraria")
    p.add_argument("--out-dir", default="output_accessibilita_gtfs", help="Cartella output")
    p.add_argument("--population-field", default="pop_riferimento", help="Campo popolazione sezioni")
    return p.parse_args()


def read_gtfs_table(zf: zipfile.ZipFile, name: str, required: bool = True) -> pd.DataFrame:
    try:
        with zf.open(name) as f:
            return pd.read_csv(f, dtype=str, keep_default_na=False)
    except KeyError:
        if required:
            raise FileNotFoundError(f"Nel GTFS manca {name}")
        return pd.DataFrame()


def hhmmss_to_seconds(value: str) -> int:
    h, m, s = (int(x) for x in value.split(":"))
    return h * 3600 + m * 60 + s


def seconds_to_hhmm(seconds: float) -> str:
    if not np.isfinite(seconds):
        return ""
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h:02d}:{m:02d}"


def normalize_route(value: str) -> str:
    value = str(value).strip()
    value = re.sub(r"\.0$", "", value)
    return value.upper()


def parse_service_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y%m%d")


def calendar_active_services(calendar: pd.DataFrame, calendar_dates: pd.DataFrame, date: datetime) -> set[str]:
    day_name = date.strftime("%A").lower()
    date_s = date.strftime("%Y%m%d")
    active: set[str] = set()

    if not calendar.empty:
        c = calendar.copy()
        mask = (
            (c["start_date"] <= date_s)
            & (c["end_date"] >= date_s)
            & (c.get(day_name, "0") == "1")
        )
        active.update(c.loc[mask, "service_id"].astype(str))

    if not calendar_dates.empty:
        ex = calendar_dates[calendar_dates["date"] == date_s]
        for row in ex.itertuples(index=False):
            if str(row.exception_type) == "1":
                active.add(str(row.service_id))
            elif str(row.exception_type) == "2":
                active.discard(str(row.service_id))
    return active


def choose_service_date(calendar: pd.DataFrame, calendar_dates: pd.DataFrame) -> datetime:
    today = datetime.now().date()
    for offset in range(0, 31):
        d = datetime.combine(today + timedelta(days=offset), datetime.min.time())
        if d.weekday() < 5 and calendar_active_services(calendar, calendar_dates, d):
            return d
    return datetime.combine(today, datetime.min.time())


def load_graph(path: Path) -> nx.MultiDiGraph:
    G = nx.read_graphml(path)
    # Convert node ids where possible and numeric edge attributes.
    mapping = {}
    for n in G.nodes:
        try:
            mapping[n] = int(n)
        except Exception:
            pass
    if mapping:
        G = nx.relabel_nodes(G, mapping)
    for _, data in G.nodes(data=True):
        for k in ("x", "y"):
            if k in data:
                data[k] = float(data[k])
    for _, _, data in G.edges(data=True):
        for k in ("walk_time_s", "travel_time", "length"):
            if k in data and data[k] not in (None, ""):
                try:
                    data[k] = float(data[k])
                except Exception:
                    pass
        if "walk_time_s" not in data:
            if "travel_time" in data:
                data["walk_time_s"] = float(data["travel_time"])
            elif "length" in data:
                data["walk_time_s"] = float(data["length"]) / 1.2
            else:
                data["walk_time_s"] = 1.0
    return G


def graph_crs(G: nx.MultiDiGraph):
    crs = G.graph.get("crs")
    if crs:
        return crs
    return "EPSG:4326"


def nearest_node(G: nx.MultiDiGraph, x: float, y: float) -> tuple[object, float]:
    best = None
    best_d2 = float("inf")
    for n, data in G.nodes(data=True):
        nx_ = float(data["x"])
        ny_ = float(data["y"])
        d2 = (nx_ - x) ** 2 + (ny_ - y) ** 2
        if d2 < best_d2:
            best = n
            best_d2 = d2
    return best, math.sqrt(best_d2)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    G = load_graph(Path(args.graph))
    g_crs = graph_crs(G)

    if args.sections_layer:
        sections = gpd.read_file(args.sections, layer=args.sections_layer)
    else:
        sections = gpd.read_file(args.sections)
    sections = sections.to_crs(g_crs)
    centroids = sections.copy()
    centroids.geometry = sections.geometry.representative_point()

    with zipfile.ZipFile(args.gtfs) as zf:
        routes = read_gtfs_table(zf, "routes.txt")
        trips = read_gtfs_table(zf, "trips.txt")
        stop_times = read_gtfs_table(zf, "stop_times.txt")
        stops = read_gtfs_table(zf, "stops.txt")
        calendar = read_gtfs_table(zf, "calendar.txt", required=False)
        calendar_dates = read_gtfs_table(zf, "calendar_dates.txt", required=False)

    wanted = {normalize_route(x) for x in args.routes}
    routes["route_short_norm"] = routes["route_short_name"].map(normalize_route)
    selected_routes = routes[routes["route_short_norm"].isin(wanted)].copy()
    if selected_routes.empty:
        available = sorted(routes["route_short_name"].dropna().astype(str).unique())
        raise ValueError(f"Nessuna linea trovata tra {sorted(wanted)}. Linee disponibili: {available[:50]}")

    service_date = datetime.strptime(args.date, "%Y-%m-%d") if args.date else choose_service_date(calendar, calendar_dates)
    active_services = calendar_active_services(calendar, calendar_dates, service_date)

    trips_sel = trips[trips["route_id"].isin(selected_routes["route_id"])].copy()
    if active_services:
        trips_sel = trips_sel[trips_sel["service_id"].isin(active_services)]
    if trips_sel.empty:
        raise ValueError(f"Nessuna corsa attiva per {service_date.date()} sulle linee richieste")

    st = stop_times[stop_times["trip_id"].isin(trips_sel["trip_id"])].copy()
    start_s = hhmmss_to_seconds(args.time_start)
    end_s = hhmmss_to_seconds(args.time_end)
    st["dep_s"] = st["departure_time"].map(hhmmss_to_seconds)
    st_window = st[(st["dep_s"] >= start_s) & (st["dep_s"] <= end_s)].copy()
    if st_window.empty:
        raise ValueError("Nessun passaggio nella fascia oraria selezionata")

    trip_route = trips_sel[["trip_id", "route_id", "trip_headsign"]].merge(
        selected_routes[["route_id", "route_short_name"]], on="route_id", how="left"
    )
    st_window = st_window.merge(trip_route, on="trip_id", how="left")

    stops_sel = stops[stops["stop_id"].isin(st_window["stop_id"].unique())].copy()
    stops_gdf = gpd.GeoDataFrame(
        stops_sel,
        geometry=gpd.points_from_xy(
            pd.to_numeric(stops_sel["stop_lon"], errors="coerce"),
            pd.to_numeric(stops_sel["stop_lat"], errors="coerce")
        ),
        crs="EPSG:4326",
    ).to_crs(g_crs)

    counts = st_window.groupby("stop_id").agg(
        passaggi=("trip_id", "count"),
        prime_departure_s=("dep_s", "min"),
        last_departure_s=("dep_s", "max"),
        linee=("route_short_name", lambda s: ",".join(sorted(set(map(str, s))))),
    ).reset_index()
    counts["frequenza_media_min"] = np.where(
        counts["passaggi"] > 1,
        (counts["last_departure_s"] - counts["prime_departure_s"]) / 60 / (counts["passaggi"] - 1),
        np.nan,
    )
    counts["prima_corsa"] = counts["prime_departure_s"].map(seconds_to_hhmm)
    counts["ultima_corsa"] = counts["last_departure_s"].map(seconds_to_hhmm)
    stops_gdf = stops_gdf.merge(counts, on="stop_id", how="left")

    stop_nodes = []
    for row in stops_gdf.itertuples():
        n, d = nearest_node(G, row.geometry.x, row.geometry.y)
        stop_nodes.append((n, d))
    stops_gdf["graph_node"] = [x[0] for x in stop_nodes]
    stops_gdf["snap_dist"] = [x[1] for x in stop_nodes]

    unique_stop_nodes = list(dict.fromkeys(stops_gdf["graph_node"].tolist()))
    rev = G.reverse(copy=False)
    travel_to_stop: dict[object, float] = {}
    nearest_stop_node: dict[object, object] = {}
    for stop_node in unique_stop_nodes:
        lengths = nx.single_source_dijkstra_path_length(rev, stop_node, weight="walk_time_s")
        for node, sec in lengths.items():
            if sec < travel_to_stop.get(node, float("inf")):
                travel_to_stop[node] = float(sec)
                nearest_stop_node[node] = stop_node

    stop_by_node = {}
    for row in stops_gdf.itertuples():
        current = stop_by_node.get(row.graph_node)
        if current is None or int(row.passaggi) > int(current.passaggi):
            stop_by_node[row.graph_node] = row

    records = []
    centroid_nodes = []
    for idx, row in centroids.iterrows():
        node, snap_d = nearest_node(G, row.geometry.x, row.geometry.y)
        centroid_nodes.append(node)
        walk_s = travel_to_stop.get(node, float("inf"))
        sn = nearest_stop_node.get(node)
        stop = stop_by_node.get(sn)
        rec = {
            "section_index": idx,
            "centroid_node": node,
            "centroid_snap_dist": snap_d,
            "tempo_fermata_min": walk_s / 60 if np.isfinite(walk_s) else np.nan,
            "fermata_piu_vicina": getattr(stop, "stop_name", "") if stop else "",
            "stop_id": getattr(stop, "stop_id", "") if stop else "",
            "linee_fermata": getattr(stop, "linee", "") if stop else "",
            "passaggi_fascia": getattr(stop, "passaggi", np.nan) if stop else np.nan,
            "frequenza_media_min": getattr(stop, "frequenza_media_min", np.nan) if stop else np.nan,
            "entro_5_min": int(np.isfinite(walk_s) and walk_s <= 300),
            "entro_10_min": int(np.isfinite(walk_s) and walk_s <= 600),
            "entro_15_min": int(np.isfinite(walk_s) and walk_s <= 900),
        }
        records.append(rec)

    access_df = pd.DataFrame(records).set_index("section_index")
    sections_out = sections.join(access_df)
    centroids_out = centroids.join(access_df)

    gpkg = out_dir / "accessibilita_gtfs_povo.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    sections_out.to_file(gpkg, layer="sezioni_accessibilita_gtfs", driver="GPKG")
    centroids_out.to_file(gpkg, layer="centroidi_sezioni_gtfs", driver="GPKG")
    stops_gdf.to_file(gpkg, layer="fermate_gtfs", driver="GPKG")

    sections_out.drop(columns="geometry").to_csv(out_dir / "sezioni_accessibilita_gtfs.csv", index=False)
    stops_gdf.drop(columns="geometry").to_csv(out_dir / "fermate_gtfs.csv", index=False)

    pop_field = args.population_field
    summary = {
        "data_servizio": service_date.date().isoformat(),
        "fascia_oraria": f"{args.time_start}-{args.time_end}",
        "linee": ",".join(args.routes),
        "numero_fermate": int(len(stops_gdf)),
        "numero_sezioni": int(len(sections_out)),
        "sezioni_entrambe_5_min": int(sections_out["entro_5_min"].sum()),
        "sezioni_entrambe_10_min": int(sections_out["entro_10_min"].sum()),
        "sezioni_entrambe_15_min": int(sections_out["entro_15_min"].sum()),
    }
    if pop_field in sections_out.columns:
        pop = pd.to_numeric(sections_out[pop_field], errors="coerce").fillna(0)
        summary.update({
            "popolazione_totale": float(pop.sum()),
            "popolazione_entro_5_min": float(pop[sections_out["entro_5_min"] == 1].sum()),
            "popolazione_entro_10_min": float(pop[sections_out["entro_10_min"] == 1].sum()),
            "popolazione_entro_15_min": float(pop[sections_out["entro_15_min"] == 1].sum()),
        })
    pd.DataFrame([summary]).to_csv(out_dir / "sintesi_accessibilita_gtfs.csv", index=False)

    print(f"Elaborazione completata: {out_dir.resolve()}")
    print(f"Data di servizio: {service_date.date()}")
    print(f"Fermate analizzate: {len(stops_gdf)}")
    print(f"Sezioni analizzate: {len(sections_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
