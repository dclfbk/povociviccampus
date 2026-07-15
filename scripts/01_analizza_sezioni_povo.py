#!/usr/bin/env python3
"""Integra dati censuari e morfometria DTM per le sezioni di Povo.

Input principali:
- GeoJSON/GPKG/SHP delle sezioni censuarie, gia corredate o meno di attributi ISTAT;
- DTM ritagliato di Povo;
- raster della pendenza in gradi e/o percentuale.

Output:
- sezioni_povo_terrain.gpkg
- sezioni_povo_terrain.geojson
- sezioni_povo_terrain.csv
- sintesi_sezioni_povo.csv

Esempio:
    python analizza_sezioni_povo.py \
      --sections povo_sezioni_istat_accessibilita_gtfs.geojson \
      --dtm output_dtm_povo/dtm_povo.tif \
      --slope-deg output_dtm_povo/pendenza_gradi_povo.tif \
      --slope-pct output_dtm_povo/pendenza_percentuale_povo.tif \
      --out-dir output_sezioni_povo
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask

TARGET_CRS = "EPSG:25832"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Calcola indicatori censuari e statistiche DTM per sezione censuaria."
    )
    p.add_argument("--sections", type=Path, required=True)
    p.add_argument("--dtm", type=Path, required=True)
    p.add_argument("--slope-deg", type=Path)
    p.add_argument("--slope-pct", type=Path)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument(
        "--population-field",
        default="pop_riferimento",
        help="Campo popolazione preferito; fallback automatico su P1 e POP21.",
    )
    return p.parse_args()


def choose_population(gdf: gpd.GeoDataFrame, preferred: str) -> pd.Series:
    candidates = [preferred, "P1", "POP21"]
    result = pd.Series(np.nan, index=gdf.index, dtype="float64")
    for field in candidates:
        if field in gdf.columns:
            values = pd.to_numeric(gdf[field], errors="coerce")
            result = result.fillna(values)
    return result.fillna(0.0)


def valid_values(arr: np.ndarray, nodata: float | int | None) -> np.ndarray:
    data = np.asarray(arr, dtype="float64").ravel()
    keep = np.isfinite(data)
    if nodata is not None and np.isfinite(nodata):
        keep &= data != nodata
    return data[keep]


def zonal_stats(gdf: gpd.GeoDataFrame, raster_path: Path, prefix: str) -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    with rasterio.open(raster_path) as src:
        if src.crs is None:
            raise ValueError(f"Il raster {raster_path} non dichiara un CRS")
        work = gdf.to_crs(src.crs)
        for geom in work.geometry:
            if geom is None or geom.is_empty:
                vals = np.array([], dtype="float64")
            else:
                try:
                    out, _ = mask(src, [geom], crop=True, filled=True, nodata=src.nodata)
                    vals = valid_values(out[0], src.nodata)
                except ValueError:
                    vals = np.array([], dtype="float64")

            if vals.size == 0:
                rows.append({
                    f"{prefix}_n": 0,
                    f"{prefix}_min": np.nan,
                    f"{prefix}_p25": np.nan,
                    f"{prefix}_mean": np.nan,
                    f"{prefix}_median": np.nan,
                    f"{prefix}_p75": np.nan,
                    f"{prefix}_max": np.nan,
                    f"{prefix}_std": np.nan,
                })
            else:
                rows.append({
                    f"{prefix}_n": int(vals.size),
                    f"{prefix}_min": float(np.min(vals)),
                    f"{prefix}_p25": float(np.percentile(vals, 25)),
                    f"{prefix}_mean": float(np.mean(vals)),
                    f"{prefix}_median": float(np.median(vals)),
                    f"{prefix}_p75": float(np.percentile(vals, 75)),
                    f"{prefix}_max": float(np.max(vals)),
                    f"{prefix}_std": float(np.std(vals)),
                })
    return pd.DataFrame(rows, index=gdf.index)


def safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    return num.div(den.where(den != 0))


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    gdf = gpd.read_file(args.sections)
    if gdf.empty:
        raise ValueError("Il file delle sezioni non contiene geometrie")
    if gdf.crs is None:
        raise ValueError("Il file delle sezioni non dichiara un CRS")

    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf = gdf.to_crs(TARGET_CRS)
    gdf["geometry"] = gdf.geometry.make_valid()

    # Geometria e popolazione
    gdf["area_m2"] = gdf.geometry.area
    gdf["area_km2"] = gdf["area_m2"] / 1_000_000.0
    gdf["perimetro_m"] = gdf.geometry.length
    gdf["pop_ref"] = choose_population(gdf, args.population_field)
    gdf["dens_pop_km2"] = safe_div(gdf["pop_ref"], gdf["area_km2"])

    # Indicatori censuari semplici e non ambigui
    if "FAM21" in gdf.columns:
        gdf["famiglie"] = pd.to_numeric(gdf["FAM21"], errors="coerce")
        gdf["dim_media_fam"] = safe_div(gdf["pop_ref"], gdf["famiglie"])
    if "ABI21" in gdf.columns:
        gdf["abitazioni"] = pd.to_numeric(gdf["ABI21"], errors="coerce")
        gdf["abitazioni_km2"] = safe_div(gdf["abitazioni"], gdf["area_km2"])
        if "FAM21" in gdf.columns:
            gdf["fam_per_abitazione"] = safe_div(gdf["famiglie"], gdf["abitazioni"])
    if "EDI21" in gdf.columns:
        gdf["edifici"] = pd.to_numeric(gdf["EDI21"], errors="coerce")
        gdf["edifici_km2"] = safe_div(gdf["edifici"], gdf["area_km2"])
        if "ABI21" in gdf.columns:
            gdf["abitazioni_edificio"] = safe_div(gdf["abitazioni"], gdf["edifici"])

    # Statistiche morfometriche per sezione
    stats_frames = [zonal_stats(gdf, args.dtm, "quota_m")]
    if args.slope_deg:
        stats_frames.append(zonal_stats(gdf, args.slope_deg, "pend_deg"))
    if args.slope_pct:
        stats_frames.append(zonal_stats(gdf, args.slope_pct, "pend_pct"))
    for frame in stats_frames:
        for col in frame.columns:
            gdf[col] = frame[col]

    # Escursione altimetrica interna alla sezione
    if {"quota_m_min", "quota_m_max"}.issubset(gdf.columns):
        gdf["dislivello_m"] = gdf["quota_m_max"] - gdf["quota_m_min"]

    # Classi descrittive della pendenza mediana, utili in QGIS
    if "pend_deg_median" in gdf.columns:
        bins = [-np.inf, 5, 10, 20, 30, np.inf]
        labels = ["quasi pianeggiante", "debole", "moderata", "forte", "molto forte"]
        gdf["classe_pendenza"] = pd.cut(
            gdf["pend_deg_median"], bins=bins, labels=labels, right=False
        ).astype("string")

    # Identificatore stabile
    id_candidates = ["SEZ21_ID", "SEZ21", "fid"]
    id_field = next((c for c in id_candidates if c in gdf.columns), None)
    if id_field is None:
        gdf["section_id"] = np.arange(1, len(gdf) + 1).astype(str)
    else:
        gdf["section_id"] = gdf[id_field].astype("string")

    # Output vettoriali
    gpkg = args.out_dir / "sezioni_povo_terrain.gpkg"
    geojson = args.out_dir / "sezioni_povo_terrain.geojson"
    csv_path = args.out_dir / "sezioni_povo_terrain.csv"
    summary_path = args.out_dir / "sintesi_sezioni_povo.csv"

    gdf.to_file(gpkg, layer="sezioni", driver="GPKG")
    gdf.to_crs(4326).to_file(geojson, driver="GeoJSON")

    table = pd.DataFrame(gdf.drop(columns="geometry"))
    table.to_csv(csv_path, index=False)

    summary = [
        ("numero_sezioni", len(gdf)),
        ("popolazione_riferimento", float(gdf["pop_ref"].sum())),
        ("area_totale_km2", float(gdf.geometry.union_all().area / 1_000_000.0)),
        ("densita_media_ponderata_ab_km2", float(gdf["pop_ref"].sum() / (gdf.geometry.union_all().area / 1_000_000.0))),
    ]
    if "quota_m_min" in gdf.columns:
        summary.extend([
            ("quota_min_m", float(gdf["quota_m_min"].min())),
            ("quota_max_m", float(gdf["quota_m_max"].max())),
            ("quota_mediana_sezioni_m", float(gdf["quota_m_median"].median())),
        ])
    if "pend_deg_median" in gdf.columns:
        summary.append(("pendenza_mediana_sezioni_gradi", float(gdf["pend_deg_median"].median())))

    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["indicatore", "valore"])
        writer.writerows(summary)

    print(f"Creati:\n- {gpkg}\n- {geojson}\n- {csv_path}\n- {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
