#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Calcola l'accessibilità pedonale alle fermate GTFS urbane ed "
            "extraurbane realmente pertinenti alla Circoscrizione di Povo."
        )
    )
    p.add_argument("--graph", required=True, help="GraphML della rete pedonale corretta per pendenza")
    p.add_argument("--sections", required=True, help="GeoPackage/GeoJSON delle sezioni")
    p.add_argument("--sections-layer", default=None, help="Layer delle sezioni nel GeoPackage")
    p.add_argument("--boundary", required=True, help="Confine della Circoscrizione")
    p.add_argument("--boundary-layer", default=None, help="Layer del confine nel GeoPackage")
    p.add_argument("--urban-gtfs", required=True, help="GTFS urbano .zip")
    p.add_argument("--extraurban-gtfs", required=True, help="GTFS extraurbano .zip")
    p.add_argument("--date", default=None, help="Data YYYY-MM-DD; default: prossimo feriale comune ai feed")
    p.add_argument("--time-start", default="07:00:00", help="Inizio fascia oraria")
    p.add_argument("--time-end", default="20:00:00", help="Fine fascia oraria")
    p.add_argument(
        "--external-stop-buffer-m",
        type=float,
        default=500.0,
        help="Distanza massima dal confine per includere fermate esterne accessibili",
    )
    p.add_argument(
        "--merge-stops-m",
        type=float,
        default=35.0,
        help="Distanza massima per aggregare fermate coincidenti",
    )
    p.add_argument(
        "--population-field",
        default="pop_riferimento",
        help="Campo della popolazione nelle sezioni",
    )
    p.add_argument(
        "--out-dir",
        default="output_accessibilita_gtfs_v4",
        help="Cartella di output",
    )
    return p.parse_args()


def read_gtfs_table(zf: zipfile.ZipFile, name: str, required: bool = True) -> pd.DataFrame:
    try:
        with zf.open(name) as f:
            return pd.read_csv(f, dtype=str, keep_default_na=False)
    except KeyError:
        if required:
            raise FileNotFoundError(f"Nel GTFS manca {name}")
        return pd.DataFrame()


def normalize_route(value: object) -> str:
    text = str(value).strip().upper()
    return re.sub(r"\.0$", "", text)


def hhmmss_to_seconds(value: object) -> float:
    if value is None or pd.isna(value):
        return float("nan")
    text = str(value).strip()
    if not text:
        return float("nan")
    parts = text.split(":")
    if len(parts) != 3:
        return float("nan")
    try:
        h, m, s = (int(x) for x in parts)
    except ValueError:
        return float("nan")
    if h < 0 or not (0 <= m < 60) or not (0 <= s < 60):
        return float("nan")
    return float(h * 3600 + m * 60 + s)


def seconds_to_hhmm(seconds: float) -> str:
    if not np.isfinite(seconds):
        return ""
    seconds = int(round(seconds))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}"


def calendar_active_services(
    calendar: pd.DataFrame,
    calendar_dates: pd.DataFrame,
    date: datetime,
) -> set[str]:
    active: set[str] = set()
    date_s = date.strftime("%Y%m%d")
    weekday = date.strftime("%A").lower()

    if not calendar.empty:
        weekday_values = (
            calendar[weekday]
            if weekday in calendar.columns
            else pd.Series("0", index=calendar.index)
        )
        mask = (
            (calendar["start_date"] <= date_s)
            & (calendar["end_date"] >= date_s)
            & (weekday_values == "1")
        )
        active.update(calendar.loc[mask, "service_id"].astype(str))

    if not calendar_dates.empty:
        exceptions = calendar_dates[calendar_dates["date"] == date_s]
        for row in exceptions.itertuples(index=False):
            sid = str(row.service_id)
            if str(row.exception_type) == "1":
                active.add(sid)
            elif str(row.exception_type) == "2":
                active.discard(sid)

    return active


def choose_common_service_date(feed_paths: Iterable[Path]) -> datetime:
    calendars = []
    for path in feed_paths:
        with zipfile.ZipFile(path) as zf:
            calendars.append(
                (
                    read_gtfs_table(zf, "calendar.txt", required=False),
                    read_gtfs_table(zf, "calendar_dates.txt", required=False),
                )
            )

    today = datetime.now().date()
    for offset in range(31):
        candidate = datetime.combine(today + timedelta(days=offset), datetime.min.time())
        if candidate.weekday() >= 5:
            continue
        if all(calendar_active_services(c, cd, candidate) for c, cd in calendars):
            return candidate

    raise ValueError("Nessuna data feriale comune trovata nei prossimi 31 giorni")


def load_graph(path: Path) -> nx.MultiDiGraph:
    g = nx.read_graphml(path)

    mapping = {}
    for node in g.nodes:
        try:
            mapping[node] = int(node)
        except (TypeError, ValueError):
            pass
    if mapping:
        g = nx.relabel_nodes(g, mapping)

    for _, data in g.nodes(data=True):
        data["x"] = float(data["x"])
        data["y"] = float(data["y"])

    for _, _, data in g.edges(data=True):
        for key in ("walk_time_s", "travel_time", "length"):
            if key in data and data[key] not in ("", None):
                try:
                    data[key] = float(data[key])
                except (TypeError, ValueError):
                    pass
        if "walk_time_s" not in data:
            if "travel_time" in data:
                data["walk_time_s"] = float(data["travel_time"])
            elif "length" in data:
                data["walk_time_s"] = float(data["length"]) / 1.2
            else:
                data["walk_time_s"] = 1.0
    return g


def graph_crs(g: nx.MultiDiGraph) -> object:
    return g.graph.get("crs") or "EPSG:4326"


def nearest_node(g: nx.MultiDiGraph, x: float, y: float) -> tuple[object, float]:
    best_node = None
    best_d2 = float("inf")
    for node, data in g.nodes(data=True):
        dx = float(data["x"]) - x
        dy = float(data["y"]) - y
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_node = node
            best_d2 = d2
    if best_node is None:
        raise ValueError("Il grafo non contiene nodi validi")
    return best_node, math.sqrt(best_d2)


def build_shape_lines(
    shapes: pd.DataFrame,
    target_crs: object,
) -> gpd.GeoDataFrame:
    if shapes.empty:
        return gpd.GeoDataFrame(columns=["shape_id", "geometry"], geometry="geometry", crs=target_crs)

    s = shapes.copy()
    s["shape_pt_sequence_num"] = pd.to_numeric(s["shape_pt_sequence"], errors="coerce")
    s["shape_pt_lat_num"] = pd.to_numeric(s["shape_pt_lat"], errors="coerce")
    s["shape_pt_lon_num"] = pd.to_numeric(s["shape_pt_lon"], errors="coerce")
    s = s.dropna(subset=["shape_pt_sequence_num", "shape_pt_lat_num", "shape_pt_lon_num"])

    rows = []
    for shape_id, group in s.sort_values("shape_pt_sequence_num").groupby("shape_id"):
        coords = list(zip(group["shape_pt_lon_num"], group["shape_pt_lat_num"]))
        if len(coords) >= 2:
            rows.append({"shape_id": str(shape_id), "geometry": LineString(coords)})

    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326").to_crs(target_crs)


def fallback_trip_lines(
    trips: pd.DataFrame,
    stop_times: pd.DataFrame,
    stops_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    stop_geom = stops_gdf.set_index("stop_id").geometry.to_dict()
    st = stop_times.copy()
    st["stop_sequence_num"] = pd.to_numeric(st["stop_sequence"], errors="coerce")
    st = st.dropna(subset=["stop_sequence_num"])
    trip_route = trips[["trip_id", "route_id"]].copy()
    st = st.merge(trip_route, on="trip_id", how="inner")

    rows = []
    for (trip_id, route_id), group in st.sort_values("stop_sequence_num").groupby(["trip_id", "route_id"]):
        geoms = [stop_geom.get(str(sid)) for sid in group["stop_id"]]
        coords = [(g.x, g.y) for g in geoms if g is not None]
        if len(coords) >= 2:
            rows.append(
                {
                    "trip_id": str(trip_id),
                    "route_id": str(route_id),
                    "geometry": LineString(coords),
                }
            )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=stops_gdf.crs)


def load_and_classify_feed(
    feed_path: Path,
    feed_label: str,
    service_date: datetime,
    time_start_s: int,
    time_end_s: int,
    boundary: gpd.GeoDataFrame,
    target_crs: object,
    external_buffer_m: float,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, pd.DataFrame]:
    with zipfile.ZipFile(feed_path) as zf:
        routes = read_gtfs_table(zf, "routes.txt")
        trips = read_gtfs_table(zf, "trips.txt")
        stop_times = read_gtfs_table(zf, "stop_times.txt")
        stops = read_gtfs_table(zf, "stops.txt")
        shapes = read_gtfs_table(zf, "shapes.txt", required=False)
        calendar = read_gtfs_table(zf, "calendar.txt", required=False)
        calendar_dates = read_gtfs_table(zf, "calendar_dates.txt", required=False)

    active_services = calendar_active_services(calendar, calendar_dates, service_date)
    trips_active = trips[trips["service_id"].isin(active_services)].copy()
    if trips_active.empty:
        raise ValueError(f"Feed {feed_label}: nessuna corsa attiva il {service_date.date()}")

    routes = routes.copy()
    routes["route_short_name"] = routes["route_short_name"].map(normalize_route)

    stops_gdf = gpd.GeoDataFrame(
        stops.copy(),
        geometry=gpd.points_from_xy(
            pd.to_numeric(stops["stop_lon"], errors="coerce"),
            pd.to_numeric(stops["stop_lat"], errors="coerce"),
        ),
        crs="EPSG:4326",
    ).dropna(subset=["geometry"]).to_crs(target_crs)

    boundary_geom = boundary.geometry.union_all()
    external_area = boundary_geom.buffer(external_buffer_m)

    shape_lines = build_shape_lines(shapes, target_crs)
    if not shape_lines.empty and "shape_id" in trips_active.columns:
        trip_lines = (
            trips_active[["trip_id", "route_id", "shape_id"]]
            .drop_duplicates()
            .merge(shape_lines, on="shape_id", how="inner")
        )
        trip_lines = gpd.GeoDataFrame(trip_lines, geometry="geometry", crs=target_crs)
    else:
        trip_lines = fallback_trip_lines(trips_active, stop_times, stops_gdf)

    if trip_lines.empty:
        raise ValueError(f"Feed {feed_label}: impossibile ricostruire i percorsi delle corse")

    route_intersection = (
        trip_lines.assign(interseca_confine=trip_lines.geometry.intersects(boundary_geom))
        .groupby("route_id", as_index=False)["interseca_confine"]
        .max()
    )

    active_stop_times = stop_times[stop_times["trip_id"].isin(trips_active["trip_id"])].copy()
    active_trip_routes = trips_active[["trip_id", "route_id"]]
    active_stop_times = active_stop_times.merge(active_trip_routes, on="trip_id", how="inner")
    stop_routes = active_stop_times[["stop_id", "route_id"]].drop_duplicates()

    stops_rel = stops_gdf.merge(stop_routes, on="stop_id", how="inner")
    stops_rel["fermata_interna"] = stops_rel.geometry.within(boundary_geom)
    stops_rel["fermata_esterna_accessibile"] = (
        ~stops_rel["fermata_interna"]
        & stops_rel.geometry.intersects(external_area)
    )

    route_stops = (
        stops_rel.groupby("route_id", as_index=False)
        .agg(
            ha_fermata_interna=("fermata_interna", "max"),
            ha_fermata_esterna_accessibile=("fermata_esterna_accessibile", "max"),
        )
    )

    route_status = (
        routes[["route_id", "route_short_name", "route_long_name"]]
        .merge(route_intersection, on="route_id", how="left")
        .merge(route_stops, on="route_id", how="left")
    )
    for c in ["interseca_confine", "ha_fermata_interna", "ha_fermata_esterna_accessibile"]:
        route_status[c] = route_status[c].fillna(False).astype(bool)

    route_status["pertinente"] = (
        route_status["interseca_confine"]
        | route_status["ha_fermata_interna"]
        | route_status["ha_fermata_esterna_accessibile"]
    )

    def relation(row: pd.Series) -> str:
        if row["interseca_confine"] and row["ha_fermata_interna"]:
            return "attraversa_con_fermata_interna"
        if row["interseca_confine"]:
            return "attraversa_senza_fermata_interna"
        if row["ha_fermata_interna"]:
            return "fermata_interna"
        if row["ha_fermata_esterna_accessibile"]:
            return "solo_fermata_esterna_accessibile"
        return "non_pertinente"

    route_status["relazione_confine"] = route_status.apply(relation, axis=1)
    route_status["feed_source"] = feed_label

    selected_route_ids = set(
        route_status.loc[route_status["pertinente"], "route_id"].astype(str)
    )

    trips_sel = trips_active[trips_active["route_id"].isin(selected_route_ids)].copy()
    st = stop_times[stop_times["trip_id"].isin(trips_sel["trip_id"])].copy()

    dep = st.get("departure_time", pd.Series("", index=st.index)).astype(str).str.strip()
    arr = st.get("arrival_time", pd.Series("", index=st.index)).astype(str).str.strip()
    st["event_time"] = dep.where(dep.ne(""), arr)
    st["dep_s"] = st["event_time"].map(hhmmss_to_seconds)
    st = st.dropna(subset=["dep_s"])
    st = st[(st["dep_s"] >= time_start_s) & (st["dep_s"] <= time_end_s)].copy()

    trip_route = trips_sel[["trip_id", "route_id"]].merge(
        routes[["route_id", "route_short_name"]],
        on="route_id",
        how="left",
    )
    st = st.merge(trip_route, on="trip_id", how="left")

    counts = (
        st.groupby("stop_id")
        .agg(
            passaggi=("trip_id", "count"),
            prima_departure_s=("dep_s", "min"),
            ultima_departure_s=("dep_s", "max"),
            linee=("route_short_name", lambda v: ",".join(sorted({str(x) for x in v if str(x).strip()}))),
        )
        .reset_index()
    )
    counts["frequenza_media_min"] = np.where(
        counts["passaggi"] > 1,
        (counts["ultima_departure_s"] - counts["prima_departure_s"])
        / 60.0
        / (counts["passaggi"] - 1),
        np.nan,
    )
    counts["prima_corsa"] = counts["prima_departure_s"].map(seconds_to_hhmm)
    counts["ultima_corsa"] = counts["ultima_departure_s"].map(seconds_to_hhmm)

    used_stop_ids = set(counts["stop_id"].astype(str))
    selected_stops = stops_gdf[stops_gdf["stop_id"].isin(used_stop_ids)].copy()
    selected_stops = selected_stops.merge(counts, on="stop_id", how="left")
    selected_stops["feed_source"] = feed_label
    selected_stops["fermata_interna"] = selected_stops.geometry.within(boundary_geom)
    selected_stops["fermata_esterna_accessibile"] = (
        ~selected_stops["fermata_interna"]
        & selected_stops.geometry.intersects(external_area)
    )
    selected_stops = selected_stops[
        selected_stops["fermata_interna"]
        | selected_stops["fermata_esterna_accessibile"]
    ].copy()

    relevant_lines = route_status[route_status["pertinente"]].copy()
    relevant_trip_lines = trip_lines[
        trip_lines["route_id"].isin(selected_route_ids)
    ].copy()
    relevant_trip_lines = relevant_trip_lines.merge(
        routes[["route_id", "route_short_name", "route_long_name"]],
        on="route_id",
        how="left",
    )
    relevant_trip_lines["feed_source"] = feed_label

    return selected_stops, relevant_trip_lines, relevant_lines


def aggregate_coincident_stops(
    stops: gpd.GeoDataFrame,
    merge_distance_m: float,
) -> gpd.GeoDataFrame:
    if stops.empty:
        return stops

    remaining = set(stops.index)
    clusters = []

    while remaining:
        seed = remaining.pop()
        seed_geom = stops.at[seed, "geometry"]
        nearby = {
            idx for idx in list(remaining)
            if seed_geom.distance(stops.at[idx, "geometry"]) <= merge_distance_m
        }
        remaining.difference_update(nearby)
        clusters.append([seed, *sorted(nearby)])

    rows = []
    for cluster_id, indices in enumerate(clusters, start=1):
        subset = stops.loc[indices]
        urban = subset[subset["feed_source"] == "urbano"]
        extra = subset[subset["feed_source"] == "extraurbano"]
        names = [x for x in subset["stop_name"].astype(str) if x.strip()]

        def collect_lines(frame: pd.DataFrame) -> str:
            values = set()
            for value in frame.get("linee", pd.Series(dtype=str)).astype(str):
                values.update(x.strip() for x in value.split(",") if x.strip())
            return ",".join(sorted(values))

        rows.append(
            {
                "stop_cluster_id": cluster_id,
                "stop_name": max(names, key=len) if names else "",
                "stop_ids": ",".join(sorted(set(subset["stop_id"].astype(str)))),
                "feed_sources": ",".join(sorted(set(subset["feed_source"].astype(str)))),
                "linee_urbane": collect_lines(urban),
                "linee_extraurbane": collect_lines(extra),
                "passaggi_urbani": int(pd.to_numeric(urban.get("passaggi"), errors="coerce").fillna(0).sum()) if not urban.empty else 0,
                "passaggi_extraurbani": int(pd.to_numeric(extra.get("passaggi"), errors="coerce").fillna(0).sum()) if not extra.empty else 0,
                "fermata_interna": bool(subset["fermata_interna"].any()),
                "fermata_esterna_accessibile": bool(subset["fermata_esterna_accessibile"].any()),
                "geometry": subset.geometry.union_all().centroid,
            }
        )

    result = gpd.GeoDataFrame(rows, geometry="geometry", crs=stops.crs)
    result["passaggi_totali"] = result["passaggi_urbani"] + result["passaggi_extraurbani"]
    result["tipo_servizio"] = np.select(
        [
            (result["passaggi_urbani"] > 0) & (result["passaggi_extraurbani"] > 0),
            result["passaggi_urbani"] > 0,
            result["passaggi_extraurbani"] > 0,
        ],
        ["misto", "urbano", "extraurbano"],
        default="",
    )
    result["relazione_confine"] = np.where(
        result["fermata_interna"],
        "fermata_interna",
        "fermata_esterna_accessibile",
    )
    return result


def build_best_stop_lookup(
    g: nx.MultiDiGraph,
    stops: gpd.GeoDataFrame,
    mask: pd.Series,
) -> tuple[dict[object, float], dict[object, int]]:
    selected = stops[mask].copy()
    if selected.empty:
        return {}, {}

    selected["graph_node"] = [nearest_node(g, geom.x, geom.y)[0] for geom in selected.geometry]
    reverse_graph = g.reverse(copy=False)
    travel_time = {}
    nearest_cluster = {}

    for row in selected.itertuples():
        lengths = nx.single_source_dijkstra_path_length(
            reverse_graph, row.graph_node, weight="walk_time_s"
        )
        for node, seconds in lengths.items():
            seconds = float(seconds)
            if seconds < travel_time.get(node, float("inf")):
                travel_time[node] = seconds
                nearest_cluster[node] = int(row.stop_cluster_id)

    return travel_time, nearest_cluster


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    g = load_graph(Path(args.graph))
    g_crs = graph_crs(g)

    sections = (
        gpd.read_file(args.sections, layer=args.sections_layer)
        if args.sections_layer
        else gpd.read_file(args.sections)
    ).to_crs(g_crs)

    boundary = (
        gpd.read_file(args.boundary, layer=args.boundary_layer)
        if args.boundary_layer
        else gpd.read_file(args.boundary)
    ).to_crs(g_crs)

    service_date = (
        datetime.strptime(args.date, "%Y-%m-%d")
        if args.date
        else choose_common_service_date(
            [Path(args.urban_gtfs), Path(args.extraurban_gtfs)]
        )
    )

    start_s = int(hhmmss_to_seconds(args.time_start))
    end_s = int(hhmmss_to_seconds(args.time_end))

    all_stops = []
    all_lines = []
    all_route_tables = []

    for feed_label, feed_path in [
        ("urbano", Path(args.urban_gtfs)),
        ("extraurbano", Path(args.extraurban_gtfs)),
    ]:
        stops, lines, route_table = load_and_classify_feed(
            feed_path=feed_path,
            feed_label=feed_label,
            service_date=service_date,
            time_start_s=start_s,
            time_end_s=end_s,
            boundary=boundary,
            target_crs=g_crs,
            external_buffer_m=args.external_stop_buffer_m,
        )
        all_stops.append(stops)
        all_lines.append(lines)
        all_route_tables.append(route_table)

    raw_stops = gpd.GeoDataFrame(
        pd.concat(all_stops, ignore_index=True),
        geometry="geometry",
        crs=g_crs,
    )
    route_lines = gpd.GeoDataFrame(
        pd.concat(all_lines, ignore_index=True),
        geometry="geometry",
        crs=g_crs,
    )
    routes_summary = pd.concat(all_route_tables, ignore_index=True)

    stops = aggregate_coincident_stops(raw_stops, args.merge_stops_m)
    stops["graph_node"] = [nearest_node(g, geom.x, geom.y)[0] for geom in stops.geometry]
    stops["snap_dist_m"] = [nearest_node(g, geom.x, geom.y)[1] for geom in stops.geometry]

    travel_any, nearest_any = build_best_stop_lookup(
        g, stops, pd.Series(True, index=stops.index)
    )
    travel_urban, nearest_urban = build_best_stop_lookup(
        g, stops, stops["passaggi_urbani"] > 0
    )
    travel_extra, nearest_extra = build_best_stop_lookup(
        g, stops, stops["passaggi_extraurbani"] > 0
    )

    stop_by_cluster = stops.set_index("stop_cluster_id")
    representative = sections.copy()
    representative.geometry = sections.geometry.representative_point()

    records = []
    for index, row in representative.iterrows():
        node, section_snap_m = nearest_node(g, row.geometry.x, row.geometry.y)

        def stop_data(time_lookup, cluster_lookup):
            seconds = time_lookup.get(node, float("inf"))
            cluster_id = cluster_lookup.get(node)
            if cluster_id is None:
                return np.nan, None
            return seconds / 60.0, stop_by_cluster.loc[cluster_id]

        any_min, any_stop = stop_data(travel_any, nearest_any)
        urban_min, urban_stop = stop_data(travel_urban, nearest_urban)
        extra_min, extra_stop = stop_data(travel_extra, nearest_extra)

        records.append(
            {
                "section_index": index,
                "centroid_node": node,
                "centroid_snap_dist_m": section_snap_m,
                "tempo_fermata_qualsiasi_min": any_min,
                "tempo_fermata_urbana_min": urban_min,
                "tempo_fermata_extraurbana_min": extra_min,
                "fermata_migliore": any_stop["stop_name"] if any_stop is not None else "",
                "fermata_interna_migliore": bool(any_stop["fermata_interna"]) if any_stop is not None else False,
                "tipo_relazione_confine": any_stop["relazione_confine"] if any_stop is not None else "",
                "tipo_servizio_migliore": any_stop["tipo_servizio"] if any_stop is not None else "",
                "linee_urbane_migliore": any_stop["linee_urbane"] if any_stop is not None else "",
                "linee_extraurbane_migliore": any_stop["linee_extraurbane"] if any_stop is not None else "",
                "passaggi_totali_fermata": any_stop["passaggi_totali"] if any_stop is not None else np.nan,
                "fermata_urbana_piu_vicina": urban_stop["stop_name"] if urban_stop is not None else "",
                "fermata_extraurbana_piu_vicina": extra_stop["stop_name"] if extra_stop is not None else "",
                "entro_5_min": int(np.isfinite(any_min) and any_min <= 5),
                "entro_10_min": int(np.isfinite(any_min) and any_min <= 10),
                "entro_15_min": int(np.isfinite(any_min) and any_min <= 15),
                "entro_5_min_urbano": int(np.isfinite(urban_min) and urban_min <= 5),
                "entro_10_min_urbano": int(np.isfinite(urban_min) and urban_min <= 10),
                "entro_15_min_urbano": int(np.isfinite(urban_min) and urban_min <= 15),
                "entro_5_min_extraurbano": int(np.isfinite(extra_min) and extra_min <= 5),
                "entro_10_min_extraurbano": int(np.isfinite(extra_min) and extra_min <= 10),
                "entro_15_min_extraurbano": int(np.isfinite(extra_min) and extra_min <= 15),
            }
        )

    access = pd.DataFrame(records).set_index("section_index")
    sections_out = sections.join(access)
    representative_out = representative.join(access)

    internal_routes = routes_summary[
        routes_summary["interseca_confine"] | routes_summary["ha_fermata_interna"]
    ].copy()
    urban_lines_inside = ",".join(
        sorted(
            set(
                internal_routes.loc[
                    internal_routes["feed_source"] == "urbano",
                    "route_short_name",
                ].astype(str)
            )
        )
    )
    extra_lines_inside = ",".join(
        sorted(
            set(
                internal_routes.loc[
                    internal_routes["feed_source"] == "extraurbano",
                    "route_short_name",
                ].astype(str)
            )
        )
    )

    sections_out["linee_urbane_nella_circoscrizione"] = urban_lines_inside
    sections_out["linee_extraurbane_nella_circoscrizione"] = extra_lines_inside
    representative_out["linee_urbane_nella_circoscrizione"] = urban_lines_inside
    representative_out["linee_extraurbane_nella_circoscrizione"] = extra_lines_inside

    gpkg = out_dir / "accessibilita_gtfs_multifeed_povo_v4.gpkg"
    if gpkg.exists():
        gpkg.unlink()

    sections_out.to_file(gpkg, layer="sezioni_accessibilita_gtfs", driver="GPKG")
    representative_out.to_file(gpkg, layer="punti_rappresentativi_sezioni", driver="GPKG")
    stops.to_file(gpkg, layer="fermate_gtfs_aggregate", driver="GPKG")
    raw_stops.to_file(gpkg, layer="fermate_gtfs_originali", driver="GPKG")
    route_lines.to_file(gpkg, layer="percorsi_gtfs_pertinenti", driver="GPKG")

    sections_out.to_file(
        out_dir / "sezioni_accessibilita_gtfs_v4.geojson",
        driver="GeoJSON",
    )

    sections_out.drop(columns="geometry").to_csv(
        out_dir / "sezioni_accessibilita_gtfs_v4.csv", index=False
    )
    stops.drop(columns="geometry").to_csv(
        out_dir / "fermate_gtfs_aggregate_v4.csv", index=False
    )
    routes_summary.to_csv(
        out_dir / "linee_gtfs_classificate_v4.csv", index=False
    )

    summary = {
        "data_servizio": service_date.date().isoformat(),
        "fascia_oraria": f"{args.time_start}-{args.time_end}",
        "linee_urbane_nella_circoscrizione": urban_lines_inside,
        "linee_extraurbane_nella_circoscrizione": extra_lines_inside,
        "numero_linee_pertinenti": int(routes_summary["pertinente"].sum()),
        "numero_fermate_interne": int(stops["fermata_interna"].sum()),
        "numero_fermate_esterne_accessibili": int(
            stops["fermata_esterna_accessibile"].sum()
        ),
        "numero_sezioni": int(len(sections_out)),
        "sezioni_entro_5_min": int(sections_out["entro_5_min"].sum()),
        "sezioni_entro_10_min": int(sections_out["entro_10_min"].sum()),
        "sezioni_entro_15_min": int(sections_out["entro_15_min"].sum()),
    }

    if args.population_field in sections_out.columns:
        population = pd.to_numeric(
            sections_out[args.population_field], errors="coerce"
        ).fillna(0)
        summary.update(
            {
                "popolazione_totale": float(population.sum()),
                "popolazione_entro_5_min": float(
                    population[sections_out["entro_5_min"] == 1].sum()
                ),
                "popolazione_entro_10_min": float(
                    population[sections_out["entro_10_min"] == 1].sum()
                ),
                "popolazione_entro_15_min": float(
                    population[sections_out["entro_15_min"] == 1].sum()
                ),
            }
        )

    pd.DataFrame([summary]).to_csv(
        out_dir / "sintesi_accessibilita_gtfs_v4.csv", index=False
    )
    with (out_dir / "metadati_accessibilita_gtfs_v4.json").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Elaborazione completata: {out_dir.resolve()}")
    print(f"Data di servizio: {service_date.date()}")
    print(f"Linee urbane interne/attraversanti: {urban_lines_inside or '-'}")
    print(f"Linee extraurbane interne/attraversanti: {extra_lines_inside or '-'}")
    print(f"Fermate interne: {int(stops['fermata_interna'].sum())}")
    print(f"Fermate esterne accessibili: {int(stops['fermata_esterna_accessibile'].sum())}")
    print(f"Sezioni analizzate: {len(sections_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
