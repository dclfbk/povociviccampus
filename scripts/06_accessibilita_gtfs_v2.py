#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import Point


@dataclass(frozen=True)
class FeedSpec:
    label: str
    path: Path
    route_names: tuple[str, ...] | None
    spatial_selection: bool


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Integra rete pedonale, sezioni censuarie e due feed GTFS: "
            "urbano ed extraurbano."
        )
    )
    p.add_argument("--graph", required=True, help="GraphML della rete pedonale")
    p.add_argument("--sections", required=True, help="GeoPackage/GeoJSON con le sezioni")
    p.add_argument("--sections-layer", default=None, help="Layer del GeoPackage")
    p.add_argument("--boundary", required=True, help="Confine della Circoscrizione")

    p.add_argument("--urban-gtfs", required=True, help="Archivio GTFS urbano .zip")
    p.add_argument(
        "--urban-routes",
        nargs="+",
        default=["5", "13"],
        help="Linee urbane da analizzare",
    )
    p.add_argument(
        "--extraurban-gtfs",
        required=True,
        help="Archivio GTFS extraurbano .zip",
    )
    p.add_argument(
        "--extraurban-selection",
        choices=["spatial", "all"],
        default="spatial",
        help="Selezione linee extraurbane",
    )
    p.add_argument(
        "--stop-buffer-m",
        type=float,
        default=500.0,
        help="Buffer esterno al confine per selezionare fermate extraurbane",
    )
    p.add_argument(
        "--merge-stops-m",
        type=float,
        default=35.0,
        help="Distanza massima per aggregare fermate fisicamente coincidenti",
    )
    p.add_argument(
        "--date",
        default=None,
        help="Data di servizio YYYY-MM-DD; default: prossimo feriale disponibile",
    )
    p.add_argument("--time-start", default="07:00:00", help="Inizio fascia oraria")
    p.add_argument("--time-end", default="20:00:00", help="Fine fascia oraria")
    p.add_argument(
        "--population-field",
        default="pop_riferimento",
        help="Campo popolazione nelle sezioni",
    )
    p.add_argument(
        "--out-dir",
        default="output_accessibilita_gtfs_v2",
        help="Cartella di output",
    )
    return p.parse_args()


def read_gtfs_table(
    zf: zipfile.ZipFile, name: str, required: bool = True
) -> pd.DataFrame:
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


def hhmmss_to_seconds(value: str) -> int:
    h, m, s = (int(x) for x in str(value).split(":"))
    return h * 3600 + m * 60 + s


def seconds_to_hhmm(seconds: float) -> str:
    if not np.isfinite(seconds):
        return ""
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h:02d}:{m:02d}"


def calendar_active_services(
    calendar: pd.DataFrame,
    calendar_dates: pd.DataFrame,
    date: datetime,
) -> set[str]:
    active: set[str] = set()
    date_s = date.strftime("%Y%m%d")
    weekday = date.strftime("%A").lower()

    if not calendar.empty:
        c = calendar.copy()
        weekday_values = c[weekday] if weekday in c.columns else pd.Series("0", index=c.index)
        mask = (
            (c["start_date"] <= date_s)
            & (c["end_date"] >= date_s)
            & (weekday_values == "1")
        )
        active.update(c.loc[mask, "service_id"].astype(str))

    if not calendar_dates.empty:
        exceptions = calendar_dates[calendar_dates["date"] == date_s]
        for row in exceptions.itertuples(index=False):
            service_id = str(row.service_id)
            if str(row.exception_type) == "1":
                active.add(service_id)
            elif str(row.exception_type) == "2":
                active.discard(service_id)

    return active


def choose_common_service_date(feed_paths: Iterable[Path]) -> datetime:
    calendars: list[tuple[pd.DataFrame, pd.DataFrame]] = []
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

    return datetime.combine(today, datetime.min.time())


def load_graph(path: Path) -> nx.MultiDiGraph:
    G = nx.read_graphml(path)

    mapping: dict[object, object] = {}
    for node in G.nodes:
        try:
            mapping[node] = int(node)
        except (TypeError, ValueError):
            pass
    if mapping:
        G = nx.relabel_nodes(G, mapping)

    for _, data in G.nodes(data=True):
        for key in ("x", "y"):
            if key in data:
                data[key] = float(data[key])

    for _, _, data in G.edges(data=True):
        for key in ("walk_time_s", "travel_time", "length"):
            if key in data and data[key] not in (None, ""):
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

    return G


def graph_crs(G: nx.MultiDiGraph) -> object:
    return G.graph.get("crs") or "EPSG:4326"


def nearest_node(G: nx.MultiDiGraph, x: float, y: float) -> tuple[object, float]:
    best_node: object | None = None
    best_d2 = float("inf")
    for node, data in G.nodes(data=True):
        dx = float(data["x"]) - x
        dy = float(data["y"]) - y
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_node = node
            best_d2 = d2
    if best_node is None:
        raise ValueError("Il grafo non contiene nodi validi")
    return best_node, math.sqrt(best_d2)


def select_extraurban_routes_spatial(
    stops_gdf: gpd.GeoDataFrame,
    stop_times: pd.DataFrame,
    trips: pd.DataFrame,
    boundary: gpd.GeoDataFrame,
    buffer_m: float,
) -> set[str]:
    selection_area = boundary.geometry.unary_union.buffer(buffer_m)
    selected_stop_ids = set(
        stops_gdf.loc[stops_gdf.geometry.intersects(selection_area), "stop_id"].astype(str)
    )
    selected_trip_ids = set(
        stop_times.loc[stop_times["stop_id"].isin(selected_stop_ids), "trip_id"].astype(str)
    )
    return set(
        trips.loc[trips["trip_id"].isin(selected_trip_ids), "route_id"].astype(str)
    )


def load_feed(
    spec: FeedSpec,
    service_date: datetime,
    time_start_s: int,
    time_end_s: int,
    graph_crs_value: object,
    boundary: gpd.GeoDataFrame,
    stop_buffer_m: float,
) -> gpd.GeoDataFrame:
    with zipfile.ZipFile(spec.path) as zf:
        routes = read_gtfs_table(zf, "routes.txt")
        trips = read_gtfs_table(zf, "trips.txt")
        stop_times = read_gtfs_table(zf, "stop_times.txt")
        stops = read_gtfs_table(zf, "stops.txt")
        calendar = read_gtfs_table(zf, "calendar.txt", required=False)
        calendar_dates = read_gtfs_table(zf, "calendar_dates.txt", required=False)

    active_services = calendar_active_services(calendar, calendar_dates, service_date)

    stops_gdf = gpd.GeoDataFrame(
        stops.copy(),
        geometry=gpd.points_from_xy(
            pd.to_numeric(stops["stop_lon"], errors="coerce"),
            pd.to_numeric(stops["stop_lat"], errors="coerce"),
        ),
        crs="EPSG:4326",
    ).dropna(subset=["geometry"])
    stops_gdf = stops_gdf.to_crs(graph_crs_value)

    routes = routes.copy()
    routes["route_short_norm"] = routes["route_short_name"].map(normalize_route)

    if spec.route_names is not None:
        wanted = {normalize_route(x) for x in spec.route_names}
        selected_routes = routes[routes["route_short_norm"].isin(wanted)].copy()
        if selected_routes.empty:
            available = sorted(routes["route_short_name"].astype(str).unique())
            raise ValueError(
                f"Feed {spec.label}: nessuna linea trovata tra {sorted(wanted)}. "
                f"Linee disponibili: {available[:80]}"
            )
        selected_route_ids = set(selected_routes["route_id"].astype(str))
    elif spec.spatial_selection:
        selected_route_ids = select_extraurban_routes_spatial(
            stops_gdf, stop_times, trips, boundary, stop_buffer_m
        )
        selected_routes = routes[routes["route_id"].isin(selected_route_ids)].copy()
        if selected_routes.empty:
            raise ValueError(
                f"Feed {spec.label}: nessuna linea con fermate entro {stop_buffer_m:g} m dal confine"
            )
    else:
        selected_routes = routes.copy()
        selected_route_ids = set(selected_routes["route_id"].astype(str))

    trips_sel = trips[trips["route_id"].isin(selected_route_ids)].copy()
    if active_services:
        trips_sel = trips_sel[trips_sel["service_id"].isin(active_services)]
    if trips_sel.empty:
        raise ValueError(
            f"Feed {spec.label}: nessuna corsa attiva il {service_date.date()}"
        )

    st = stop_times[stop_times["trip_id"].isin(trips_sel["trip_id"])].copy()
    st["dep_s"] = st["departure_time"].map(hhmmss_to_seconds)
    st = st[(st["dep_s"] >= time_start_s) & (st["dep_s"] <= time_end_s)].copy()
    if st.empty:
        raise ValueError(
            f"Feed {spec.label}: nessun passaggio nella fascia selezionata"
        )

    trip_route = trips_sel[["trip_id", "route_id"]].merge(
        selected_routes[["route_id", "route_short_name"]],
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
            linee=(
                "route_short_name",
                lambda values: ",".join(
                    sorted({str(v) for v in values if str(v).strip()})
                ),
            ),
        )
        .reset_index()
    )
    counts["frequenza_media_min"] = np.where(
        counts["passaggi"] > 1,
        (counts["ultima_departure_s"] - counts["prima_departure_s"])
        / 60
        / (counts["passaggi"] - 1),
        np.nan,
    )
    counts["prima_corsa"] = counts["prima_departure_s"].map(seconds_to_hhmm)
    counts["ultima_corsa"] = counts["ultima_departure_s"].map(seconds_to_hhmm)

    selected_stop_ids = set(st["stop_id"].astype(str))
    result = stops_gdf[stops_gdf["stop_id"].isin(selected_stop_ids)].copy()
    result = result.merge(counts, on="stop_id", how="left")
    result["feed_source"] = spec.label

    if spec.spatial_selection:
        area = boundary.geometry.unary_union.buffer(stop_buffer_m)
        result = result[result.geometry.intersects(area)].copy()

    return result


def aggregate_coincident_stops(
    stops: gpd.GeoDataFrame,
    merge_distance_m: float,
) -> gpd.GeoDataFrame:
    if stops.empty:
        return stops

    remaining = set(stops.index)
    clusters: list[list[int]] = []

    while remaining:
        seed = remaining.pop()
        seed_geom = stops.at[seed, "geometry"]
        nearby = {
            idx
            for idx in list(remaining)
            if seed_geom.distance(stops.at[idx, "geometry"]) <= merge_distance_m
        }
        remaining.difference_update(nearby)
        clusters.append([seed, *sorted(nearby)])

    rows: list[dict[str, object]] = []
    for cluster_id, indices in enumerate(clusters, start=1):
        subset = stops.loc[indices]
        geometry = subset.geometry.unary_union.centroid
        urban = subset[subset["feed_source"] == "urbano"]
        extra = subset[subset["feed_source"] == "extraurbano"]

        stop_names = [x for x in subset["stop_name"].astype(str) if x.strip()]
        stop_name = max(stop_names, key=len) if stop_names else ""

        rows.append(
            {
                "stop_cluster_id": cluster_id,
                "stop_name": stop_name,
                "stop_ids": ",".join(sorted(set(subset["stop_id"].astype(str)))),
                "feed_sources": ",".join(sorted(set(subset["feed_source"].astype(str)))),
                "linee_urbane": ",".join(
                    sorted(
                        {
                            item
                            for value in urban.get("linee", pd.Series(dtype=str)).astype(str)
                            for item in value.split(",")
                            if item.strip()
                        }
                    )
                ),
                "linee_extraurbane": ",".join(
                    sorted(
                        {
                            item
                            for value in extra.get("linee", pd.Series(dtype=str)).astype(str)
                            for item in value.split(",")
                            if item.strip()
                        }
                    )
                ),
                "passaggi_urbani": int(pd.to_numeric(urban.get("passaggi"), errors="coerce").fillna(0).sum())
                if not urban.empty
                else 0,
                "passaggi_extraurbani": int(
                    pd.to_numeric(extra.get("passaggi"), errors="coerce").fillna(0).sum()
                )
                if not extra.empty
                else 0,
                "frequenza_urbana_min": float(
                    pd.to_numeric(urban.get("frequenza_media_min"), errors="coerce").min()
                )
                if not urban.empty
                else np.nan,
                "frequenza_extraurbana_min": float(
                    pd.to_numeric(extra.get("frequenza_media_min"), errors="coerce").min()
                )
                if not extra.empty
                else np.nan,
                "geometry": geometry,
            }
        )

    result = gpd.GeoDataFrame(rows, geometry="geometry", crs=stops.crs)
    result["passaggi_totali"] = (
        result["passaggi_urbani"] + result["passaggi_extraurbani"]
    )
    result["tipo_servizio"] = np.select(
        [
            (result["passaggi_urbani"] > 0) & (result["passaggi_extraurbani"] > 0),
            result["passaggi_urbani"] > 0,
            result["passaggi_extraurbani"] > 0,
        ],
        ["misto", "urbano", "extraurbano"],
        default="",
    )
    return result


def build_best_stop_lookup(
    G: nx.MultiDiGraph,
    stops: gpd.GeoDataFrame,
    mask: pd.Series,
) -> tuple[dict[object, float], dict[object, int]]:
    selected = stops[mask].copy()
    if selected.empty:
        return {}, {}

    selected["graph_node"] = [
        nearest_node(G, geom.x, geom.y)[0] for geom in selected.geometry
    ]

    reverse_graph = G.reverse(copy=False)
    travel_time: dict[object, float] = {}
    nearest_cluster: dict[object, int] = {}

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

    G = load_graph(Path(args.graph))
    g_crs = graph_crs(G)

    if args.sections_layer:
        sections = gpd.read_file(args.sections, layer=args.sections_layer)
    else:
        sections = gpd.read_file(args.sections)
    sections = sections.to_crs(g_crs)

    boundary = gpd.read_file(args.boundary).to_crs(g_crs)

    service_date = (
        datetime.strptime(args.date, "%Y-%m-%d")
        if args.date
        else choose_common_service_date(
            [Path(args.urban_gtfs), Path(args.extraurban_gtfs)]
        )
    )

    start_s = hhmmss_to_seconds(args.time_start)
    end_s = hhmmss_to_seconds(args.time_end)

    feeds = [
        FeedSpec(
            label="urbano",
            path=Path(args.urban_gtfs),
            route_names=tuple(args.urban_routes),
            spatial_selection=False,
        ),
        FeedSpec(
            label="extraurbano",
            path=Path(args.extraurban_gtfs),
            route_names=None,
            spatial_selection=args.extraurban_selection == "spatial",
        ),
    ]

    raw_stops = pd.concat(
        [
            load_feed(
                spec,
                service_date,
                start_s,
                end_s,
                g_crs,
                boundary,
                args.stop_buffer_m,
            )
            for spec in feeds
        ],
        ignore_index=True,
    )
    raw_stops = gpd.GeoDataFrame(raw_stops, geometry="geometry", crs=g_crs)

    stops = aggregate_coincident_stops(raw_stops, args.merge_stops_m)
    stops["graph_node"] = [nearest_node(G, geom.x, geom.y)[0] for geom in stops.geometry]
    stops["snap_dist_m"] = [nearest_node(G, geom.x, geom.y)[1] for geom in stops.geometry]

    travel_any, nearest_any = build_best_stop_lookup(
        G, stops, pd.Series(True, index=stops.index)
    )
    travel_urban, nearest_urban = build_best_stop_lookup(
        G, stops, stops["passaggi_urbani"] > 0
    )
    travel_extra, nearest_extra = build_best_stop_lookup(
        G, stops, stops["passaggi_extraurbani"] > 0
    )

    stop_by_cluster = stops.set_index("stop_cluster_id")
    centroids = sections.copy()
    centroids.geometry = sections.geometry.representative_point()

    records: list[dict[str, object]] = []
    for index, row in centroids.iterrows():
        node, snap_dist = nearest_node(G, row.geometry.x, row.geometry.y)

        def stop_data(
            travel_lookup: dict[object, float],
            cluster_lookup: dict[object, int],
        ) -> tuple[float, pd.Series | None]:
            seconds = travel_lookup.get(node, float("inf"))
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
                "centroid_snap_dist_m": snap_dist,
                "tempo_fermata_qualsiasi_min": any_min,
                "tempo_fermata_urbana_min": urban_min,
                "tempo_fermata_extraurbana_min": extra_min,
                "fermata_migliore": any_stop["stop_name"] if any_stop is not None else "",
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
    centroids_out = centroids.join(access)

    gpkg = out_dir / "accessibilita_gtfs_multifeed_povo.gpkg"
    if gpkg.exists():
        gpkg.unlink()

    sections_out.to_file(gpkg, layer="sezioni_accessibilita_gtfs", driver="GPKG")
    centroids_out.to_file(gpkg, layer="centroidi_sezioni_gtfs", driver="GPKG")
    stops.to_file(gpkg, layer="fermate_gtfs_aggregate", driver="GPKG")
    raw_stops.to_file(gpkg, layer="fermate_gtfs_originali", driver="GPKG")

    sections_out.drop(columns="geometry").to_csv(
        out_dir / "sezioni_accessibilita_gtfs.csv", index=False
    )
    stops.drop(columns="geometry").to_csv(
        out_dir / "fermate_gtfs_aggregate.csv", index=False
    )
    raw_stops.drop(columns="geometry").to_csv(
        out_dir / "fermate_gtfs_originali.csv", index=False
    )

    summary: dict[str, object] = {
        "data_servizio": service_date.date().isoformat(),
        "fascia_oraria": f"{args.time_start}-{args.time_end}",
        "linee_urbane": ",".join(args.urban_routes),
        "numero_fermate_originali": int(len(raw_stops)),
        "numero_fermate_aggregate": int(len(stops)),
        "numero_fermate_urbane": int((stops["passaggi_urbani"] > 0).sum()),
        "numero_fermate_extraurbane": int((stops["passaggi_extraurbani"] > 0).sum()),
        "numero_fermate_miste": int((stops["tipo_servizio"] == "misto").sum()),
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
        out_dir / "sintesi_accessibilita_gtfs.csv", index=False
    )

    print(f"Elaborazione completata: {out_dir.resolve()}")
    print(f"Data di servizio: {service_date.date()}")
    print(f"Fermate aggregate: {len(stops)}")
    print(f"Sezioni analizzate: {len(sections_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
