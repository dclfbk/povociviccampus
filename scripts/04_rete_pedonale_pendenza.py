#!/usr/bin/env python3
"""Costruisce la rete pedonale di Povo e assegna quote, pendenze e tempi di cammino.

Input principali:
- confine della Circoscrizione (GeoJSON/GPKG/SHP)
- DTM ritagliato di Povo (GeoTIFF, EPSG:25832)

Output:
- rete_pedonale_povo.graphml
- rete_pedonale_povo.gpkg (layer nodes, edges)
- rete_pedonale_archi.csv
- sintesi_rete.csv

La rete viene scaricata da OpenStreetMap tramite OSMnx. Serve una connessione Internet
al momento dell'esecuzione.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
import rasterio
from pyproj import CRS
from shapely.geometry import Polygon, MultiPolygon


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crea una rete pedonale OSM corretta per pendenza usando un DTM."
    )
    parser.add_argument(
        "--boundary",
        required=True,
        help="Confine della Circoscrizione (GeoJSON/GPKG/SHP).",
    )
    parser.add_argument(
        "--dtm",
        required=True,
        help="DTM GeoTIFF ritagliato su Povo.",
    )
    parser.add_argument(
        "--out-dir",
        default="output_rete_pedonale_povo",
        help="Cartella di output.",
    )
    parser.add_argument(
        "--buffer-m",
        type=float,
        default=300.0,
        help="Buffer metrico oltre il confine per evitare tagli della rete (default: 300).",
    )
    parser.add_argument(
        "--max-grade",
        type=float,
        default=1.5,
        help="Valore assoluto massimo della pendenza come rapporto, oltre il quale viene troncata (default: 1.5 = 150%%).",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Abilita la cache OSMnx.",
    )
    return parser.parse_args()


def to_single_polygon(gdf: gpd.GeoDataFrame) -> Polygon | MultiPolygon:
    if gdf.empty:
        raise ValueError("Il file del confine non contiene geometrie.")
    geom = gdf.geometry.union_all() if hasattr(gdf.geometry, "union_all") else gdf.unary_union
    if geom.is_empty:
        raise ValueError("La geometria del confine è vuota.")
    if not isinstance(geom, (Polygon, MultiPolygon)):
        geom = geom.convex_hull
    return geom


def sample_raster_at_points(
    raster_path: Path,
    points_gdf: gpd.GeoDataFrame,
) -> np.ndarray:
    with rasterio.open(raster_path) as src:
        if src.crs is None:
            raise ValueError(f"Il raster {raster_path} non dichiara un CRS.")

        pts = points_gdf.to_crs(src.crs)
        coords = [(geom.x, geom.y) for geom in pts.geometry]
        nodata = src.nodata
        vals = []
        for sample in src.sample(coords):
            val = float(sample[0])
            if nodata is not None and math.isclose(val, float(nodata), rel_tol=0.0, abs_tol=1e-9):
                vals.append(np.nan)
            elif not np.isfinite(val):
                vals.append(np.nan)
            else:
                vals.append(val)
        return np.asarray(vals, dtype=float)


def tobler_speed_kmh(grade: float) -> float:
    """Velocità pedonale secondo Tobler; grade è dz/dx, con segno."""
    speed = 6.0 * math.exp(-3.5 * abs(grade + 0.05))
    return max(speed, 0.5)


def add_elevation_grade_and_time(
    graph: nx.MultiDiGraph,
    dtm_path: Path,
    max_grade: float,
) -> nx.MultiDiGraph:
    nodes, _ = ox.graph_to_gdfs(graph, nodes=True, edges=True)
    elevations = sample_raster_at_points(dtm_path, nodes)

    # Piccolo fallback: riempie eventuali nodata con la mediana dei nodi validi.
    valid = elevations[np.isfinite(elevations)]
    if valid.size == 0:
        raise ValueError("Nessuna quota valida campionata dal DTM sui nodi della rete.")
    fallback = float(np.nanmedian(valid))
    elevations = np.where(np.isfinite(elevations), elevations, fallback)

    elev_by_node = dict(zip(nodes.index, elevations, strict=True))
    nx.set_node_attributes(graph, elev_by_node, "elevation")

    for u, v, key, data in graph.edges(keys=True, data=True):
        length = float(data.get("length", 0.0) or 0.0)
        if length <= 0:
            grade = 0.0
        else:
            dz = float(elev_by_node[v] - elev_by_node[u])
            grade = dz / length

        grade = float(np.clip(grade, -max_grade, max_grade))
        grade_abs = abs(grade)
        speed_kmh = tobler_speed_kmh(grade)
        speed_mps = speed_kmh / 3.6
        walk_time_s = length / speed_mps if speed_mps > 0 else np.nan

        data["grade"] = grade
        data["grade_abs"] = grade_abs
        data["slope_pct"] = grade * 100.0
        data["walk_speed_kmh"] = speed_kmh
        data["walk_time_s"] = walk_time_s
        data["walk_time_min"] = walk_time_s / 60.0 if np.isfinite(walk_time_s) else np.nan
        data["elev_u"] = float(elev_by_node[u])
        data["elev_v"] = float(elev_by_node[v])
        data["elev_gain_m"] = max(float(elev_by_node[v] - elev_by_node[u]), 0.0)
        data["elev_loss_m"] = max(float(elev_by_node[u] - elev_by_node[v]), 0.0)

    return graph


def export_outputs(graph: nx.MultiDiGraph, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    graphml_path = out_dir / "rete_pedonale_povo.graphml"
    gpkg_path = out_dir / "rete_pedonale_povo.gpkg"
    edges_csv_path = out_dir / "rete_pedonale_archi.csv"
    summary_path = out_dir / "sintesi_rete.csv"

    ox.save_graphml(graph, graphml_path)

    nodes, edges = ox.graph_to_gdfs(graph, nodes=True, edges=True, fill_edge_geometry=True)
    nodes.to_file(gpkg_path, layer="nodes", driver="GPKG")
    edges.to_file(gpkg_path, layer="edges", driver="GPKG")

    edges_csv = edges.drop(columns="geometry").reset_index()
    edges_csv.to_csv(edges_csv_path, index=False)

    total_length_km = float(edges["length"].sum() / 1000.0) if "length" in edges else np.nan
    total_walk_h = float(edges["walk_time_s"].sum() / 3600.0) if "walk_time_s" in edges else np.nan
    summary = pd.DataFrame(
        [
            {
                "nodes": graph.number_of_nodes(),
                "directed_edges": graph.number_of_edges(),
                "total_directed_length_km": total_length_km,
                "mean_grade_pct": float(edges["slope_pct"].mean()),
                "median_abs_grade_pct": float(edges["grade_abs"].median() * 100.0),
                "mean_walk_speed_kmh": float(edges["walk_speed_kmh"].mean()),
                "sum_directed_walk_time_h": total_walk_h,
                "crs": str(nodes.crs),
            }
        ]
    )
    summary.to_csv(summary_path, index=False)


def main() -> int:
    args = parse_args()
    boundary_path = Path(args.boundary)
    dtm_path = Path(args.dtm)
    out_dir = Path(args.out_dir)

    if not boundary_path.exists():
        raise FileNotFoundError(f"Confine non trovato: {boundary_path}")
    if not dtm_path.exists():
        raise FileNotFoundError(f"DTM non trovato: {dtm_path}")

    ox.settings.use_cache = bool(args.use_cache)
    ox.settings.log_console = True

    boundary = gpd.read_file(boundary_path)
    if boundary.crs is None:
        raise ValueError("Il confine non dichiara un CRS.")

    with rasterio.open(dtm_path) as src:
        if src.crs is None:
            raise ValueError("Il DTM non dichiara un CRS.")
        raster_crs = CRS.from_user_input(src.crs)

    boundary_metric = boundary.to_crs(raster_crs)
    buffered_metric = boundary_metric.copy()
    buffered_metric["geometry"] = buffered_metric.geometry.buffer(args.buffer_m)
    buffered_wgs84 = buffered_metric.to_crs(4326)
    polygon_wgs84 = to_single_polygon(buffered_wgs84)

    print("Scarico la rete pedonale da OpenStreetMap...")
    graph = ox.graph_from_polygon(
        polygon_wgs84,
        network_type="walk",
        simplify=True,
        retain_all=True,
        truncate_by_edge=True,
    )

    print("Proietto la rete nel CRS del DTM...")
    graph = ox.project_graph(graph, to_crs=raster_crs)

    print("Campiono le quote e calcolo pendenze e tempi di percorrenza...")
    graph = add_elevation_grade_and_time(graph, dtm_path, args.max_grade)

    print("Esporto i risultati...")
    export_outputs(graph, out_dir)

    print(f"Completato. Output in: {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        raise
