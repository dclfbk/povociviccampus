#!/usr/bin/env python3
"""Calcola l'accessibilita pedonale ai servizi sulle sezioni censuarie di Povo.

Input principali:
- rete GraphML prodotta dallo script 04, con peso `walk_time_s` sugli archi;
- sezioni censuarie prodotte dallo script 03;
- punti dei servizi in GeoJSON/GPKG/CSV.

Output:
- sezioni arricchite con tempi minimi e numero di servizi raggiungibili;
- servizi agganciati alla rete;
- tabelle CSV di sintesi.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import Point

DEFAULT_THRESHOLDS = (5, 10, 15)
CATEGORY_CANDIDATES = (
    "map category",
    "map_category",
    "category",
    "categoria",
    "macro_categoria",
    "macro category",
    "tipo",
)
NAME_CANDIDATES = ("name", "nome", "denominazione", "title", "titolo")
LAT_CANDIDATES = ("latitude", "lat", "y")
LON_CANDIDATES = ("longitude", "lon", "lng", "x")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph", required=True, help="GraphML prodotto dallo script 04")
    p.add_argument("--sections", required=True, help="GPKG/GeoJSON delle sezioni prodotto dallo script 03")
    p.add_argument("--sections-layer", default=None, help="Layer del GPKG delle sezioni")
    p.add_argument("--services", required=True, help="GeoJSON/GPKG/CSV con i servizi")
    p.add_argument("--services-layer", default=None, help="Layer del GPKG dei servizi")
    p.add_argument("--category-field", default=None, help="Campo categoria; se omesso viene individuato automaticamente")
    p.add_argument("--name-field", default=None, help="Campo nome; se omesso viene individuato automaticamente")
    p.add_argument("--lat-field", default=None, help="Campo latitudine per input CSV")
    p.add_argument("--lon-field", default=None, help="Campo longitudine per input CSV")
    p.add_argument("--services-crs", default="EPSG:4326", help="CRS dei punti CSV, default EPSG:4326")
    p.add_argument("--thresholds", default="5,10,15", help="Soglie in minuti, separate da virgola")
    p.add_argument("--max-snap-m", type=float, default=250.0, help="Distanza massima accettata dal nodo di rete")
    p.add_argument("--out-dir", default="output_accessibilita_servizi", help="Cartella di output")
    return p.parse_args()


def normalize_col(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def detect_field(columns: Iterable[str], candidates: Iterable[str], explicit: str | None) -> str | None:
    cols = list(columns)
    if explicit:
        if explicit not in cols:
            raise ValueError(f"Campo richiesto non trovato: {explicit}")
        return explicit
    lookup = {normalize_col(c): c for c in cols}
    for cand in candidates:
        if normalize_col(cand) in lookup:
            return lookup[normalize_col(cand)]
    return None


def read_vector(path: Path, layer: str | None = None) -> gpd.GeoDataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path)
        return gpd.GeoDataFrame(df)
    return gpd.read_file(path, layer=layer)


def prepare_services(args: argparse.Namespace, graph_crs) -> tuple[gpd.GeoDataFrame, str, str]:
    path = Path(args.services)
    services = read_vector(path, args.services_layer)

    name_field = detect_field(services.columns, NAME_CANDIDATES, args.name_field)
    category_field = detect_field(services.columns, CATEGORY_CANDIDATES, args.category_field)

    if name_field is None:
        services["nome_servizio"] = [f"servizio_{i+1}" for i in range(len(services))]
        name_field = "nome_servizio"
    if category_field is None:
        services["categoria_servizio"] = "tutti"
        category_field = "categoria_servizio"

    if "geometry" not in services.columns or services.geometry.isna().all():
        lat_field = detect_field(services.columns, LAT_CANDIDATES, args.lat_field)
        lon_field = detect_field(services.columns, LON_CANDIDATES, args.lon_field)
        if not lat_field or not lon_field:
            raise ValueError("Il CSV non contiene geometrie e non sono state individuate colonne lat/lon")
        lat = pd.to_numeric(services[lat_field], errors="coerce")
        lon = pd.to_numeric(services[lon_field], errors="coerce")
        valid = lat.notna() & lon.notna()
        services = services.loc[valid].copy()
        services = gpd.GeoDataFrame(
            services,
            geometry=gpd.points_from_xy(lon.loc[valid], lat.loc[valid]),
            crs=args.services_crs,
        )
    elif services.crs is None:
        raise ValueError("Il file dei servizi ha geometrie ma non dichiara il CRS")

    services = services[services.geometry.notna() & ~services.geometry.is_empty].copy()
    services = services[services.geometry.geom_type == "Point"].copy()
    services = services.to_crs(graph_crs)
    services["service_name"] = services[name_field].astype(str).str.strip()
    services["service_category"] = (
        services[category_field]
        .fillna("non_classificato")
        .astype(str)
        .str.strip()
        .replace("", "non_classificato")
    )
    return services, name_field, category_field


def representative_points(sections: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = sections.copy()
    out["geometry"] = out.geometry.representative_point()
    return out


def snap_points(points: gpd.GeoDataFrame, graph: nx.MultiDiGraph, max_snap_m: float) -> gpd.GeoDataFrame:
    out = points.copy()
    xs = out.geometry.x.to_numpy()
    ys = out.geometry.y.to_numpy()
    nearest, dist = ox.distance.nearest_nodes(graph, X=xs, Y=ys, return_dist=True)
    out["network_node"] = nearest
    out["snap_distance_m"] = dist
    out["snap_valid"] = out["snap_distance_m"] <= max_snap_m
    return out


def clean_category(value: str) -> str:
    s = normalize_col(value)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:40] or "non_classificato"


def node_min_times_to_targets(
    graph: nx.MultiDiGraph,
    target_nodes: list[int],
    weight: str = "walk_time_s",
) -> dict[int, float]:
    if not target_nodes:
        return {}
    reverse = graph.reverse(copy=False)
    return nx.multi_source_dijkstra_path_length(reverse, target_nodes, weight=weight)


def reachable_service_counts(
    graph: nx.MultiDiGraph,
    origin_node: int,
    service_nodes: list[int],
    thresholds_min: tuple[int, ...],
    weight: str = "walk_time_s",
) -> dict[int, int]:
    if not service_nodes:
        return {t: 0 for t in thresholds_min}
    cutoff_s = max(thresholds_min) * 60
    lengths = nx.single_source_dijkstra_path_length(graph, origin_node, cutoff=cutoff_s, weight=weight)
    values = [lengths[n] for n in service_nodes if n in lengths]
    return {t: sum(v <= t * 60 for v in values) for t in thresholds_min}


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    thresholds = tuple(sorted({int(x.strip()) for x in args.thresholds.split(",") if x.strip()}))
    if not thresholds:
        thresholds = DEFAULT_THRESHOLDS

    graph = ox.load_graphml(args.graph)
    graph_crs = graph.graph.get("crs")
    if graph_crs is None:
        raise ValueError("Il GraphML non dichiara il CRS")

    # Converte esplicitamente il peso a float dopo il caricamento GraphML.
    missing_weight = 0
    for _, _, _, data in graph.edges(keys=True, data=True):
        try:
            data["walk_time_s"] = float(data["walk_time_s"])
        except (KeyError, TypeError, ValueError):
            data["walk_time_s"] = math.inf
            missing_weight += 1

    sections = gpd.read_file(args.sections, layer=args.sections_layer)
    if sections.crs is None:
        raise ValueError("Il file delle sezioni non dichiara il CRS")
    sections = sections.to_crs(graph_crs)
    sections = sections.reset_index(drop=True)
    sections["section_uid"] = np.arange(1, len(sections) + 1)

    services, _, _ = prepare_services(args, graph_crs)
    services = services.reset_index(drop=True)
    services["service_uid"] = np.arange(1, len(services) + 1)

    section_points = representative_points(sections)
    section_points = snap_points(section_points, graph, args.max_snap_m)
    services = snap_points(services, graph, args.max_snap_m)

    valid_services = services[services["snap_valid"]].copy()
    categories = sorted(valid_services["service_category"].dropna().unique().tolist())

    # Campi complessivi.
    all_nodes = valid_services["network_node"].astype(int).tolist()
    all_min = node_min_times_to_targets(graph, all_nodes)
    sections["tempo_min_servizio_min"] = [
        all_min.get(int(n), np.nan) / 60.0 if valid else np.nan
        for n, valid in zip(section_points["network_node"], section_points["snap_valid"])
    ]

    for t in thresholds:
        sections[f"servizi_{t}min"] = 0

    for i, row in section_points.iterrows():
        if not bool(row["snap_valid"]):
            continue
        counts = reachable_service_counts(graph, int(row["network_node"]), all_nodes, thresholds)
        for t, count in counts.items():
            sections.at[i, f"servizi_{t}min"] = count

    # Campi per categoria.
    category_map = {}
    for category in categories:
        slug = clean_category(category)
        # evita collisioni tra nomi normalizzati uguali
        base = slug
        suffix = 2
        while slug in category_map.values():
            slug = f"{base}_{suffix}"
            suffix += 1
        category_map[category] = slug

        cat_services = valid_services[valid_services["service_category"] == category]
        cat_nodes = cat_services["network_node"].astype(int).tolist()
        cat_min = node_min_times_to_targets(graph, cat_nodes)
        sections[f"t_{slug}_min"] = [
            cat_min.get(int(n), np.nan) / 60.0 if valid else np.nan
            for n, valid in zip(section_points["network_node"], section_points["snap_valid"])
        ]
        for t in thresholds:
            sections[f"n_{slug}_{t}m"] = 0
        for i, row in section_points.iterrows():
            if not bool(row["snap_valid"]):
                continue
            counts = reachable_service_counts(graph, int(row["network_node"]), cat_nodes, thresholds)
            for t, count in counts.items():
                sections.at[i, f"n_{slug}_{t}m"] = count

    sections["section_node"] = section_points["network_node"].astype("Int64")
    sections["section_snap_m"] = section_points["snap_distance_m"]
    sections["section_snap_ok"] = section_points["snap_valid"]

    gpkg = out_dir / "accessibilita_servizi_povo.gpkg"
    sections.to_file(gpkg, layer="sezioni_accessibilita", driver="GPKG")
    services.to_file(gpkg, layer="servizi_agganciati", driver="GPKG")
    section_points.to_file(gpkg, layer="centroidi_sezioni", driver="GPKG")

    sections.drop(columns="geometry").to_csv(out_dir / "sezioni_accessibilita_servizi.csv", index=False)
    services.drop(columns="geometry").to_csv(out_dir / "servizi_agganciati.csv", index=False)

    summary = pd.DataFrame(
        [
            {"indicatore": "numero_sezioni", "valore": len(sections)},
            {"indicatore": "numero_servizi", "valore": len(services)},
            {"indicatore": "servizi_agganciati", "valore": int(services["snap_valid"].sum())},
            {"indicatore": "servizi_non_agganciati", "valore": int((~services["snap_valid"]).sum())},
            {"indicatore": "sezioni_agganciate", "valore": int(section_points["snap_valid"].sum())},
            {"indicatore": "archi_senza_walk_time_s", "valore": missing_weight},
        ]
    )
    summary.to_csv(out_dir / "sintesi_accessibilita.csv", index=False)

    with open(out_dir / "mappa_categorie.json", "w", encoding="utf-8") as f:
        json.dump(category_map, f, ensure_ascii=False, indent=2)

    print(f"Elaborazione completata: {out_dir.resolve()}")
    print(f"Servizi validi sulla rete: {len(valid_services)} / {len(services)}")
    print(f"Categorie elaborate: {len(categories)}")


if __name__ == "__main__":
    main()
