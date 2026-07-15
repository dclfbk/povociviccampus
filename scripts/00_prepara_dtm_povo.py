#!/usr/bin/env python3
"""Prepara il DTM della Circoscrizione di Povo.

Input attesi:
- uno o piu GeoTIFF DTM con coordinate ETRS89 / UTM 32N ma CRS non dichiarato;
- un confine vettoriale della Circoscrizione (GeoJSON, GPKG, SHP...).

Output:
- dtm_povo.tif
- pendenza_gradi_povo.tif
- pendenza_percentuale_povo.tif
- esposizione_povo.tif
- hillshade_povo.tif
- statistiche_dtm_povo.csv
- confine_povo_25832.gpkg

Esempio:
    python prepara_dtm_povo.py \
      --dtm-dir /mnt/data \
      --boundary '/mnt/data/circoscrizione(3).geojson' \
      --out-dir /mnt/data/output_dtm_povo
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from contextlib import ExitStack
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.features import geometry_mask
from rasterio.fill import fillnodata
from rasterio.io import MemoryFile
from rasterio.mask import mask
from rasterio.merge import merge

DTM_CRS = CRS.from_epsg(25832)  # ETRS89 / UTM zone 32N
OUT_NODATA = -9999.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mosaico, ritaglio e derivati morfometrici del DTM di Povo."
    )
    parser.add_argument(
        "--dtm-dir",
        type=Path,
        required=True,
        help="Cartella contenente i GeoTIFF DTM.",
    )
    parser.add_argument(
        "--pattern",
        default="dtm*_wor.tif",
        help="Pattern dei DTM, default: dtm*_wor.tif",
    )
    parser.add_argument(
        "--boundary",
        type=Path,
        required=True,
        help="Confine della Circoscrizione.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Cartella di output.",
    )
    parser.add_argument(
        "--all-touched",
        action="store_true",
        help="Include ogni pixel toccato dal confine nel ritaglio.",
    )
    return parser.parse_args()


def write_raster(
    path: Path,
    data: np.ndarray,
    transform: rasterio.Affine,
    crs: CRS,
    nodata: float,
    dtype: str = "float32",
) -> None:
    """Scrive un GeoTIFF compresso, tiled e con overviews."""
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "compress": "deflate",
        "predictor": 3 if np.issubdtype(np.dtype(dtype), np.floating) else 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "BIGTIFF": "IF_SAFER",
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype(dtype, copy=False), 1)
        factors = [2, 4, 8, 16]
        valid_factors = [f for f in factors if min(data.shape) // f >= 1]
        if valid_factors:
            dst.build_overviews(valid_factors, rasterio.enums.Resampling.average)
            dst.update_tags(ns="rio_overview", resampling="average")


def circular_aspect(dz_dx: np.ndarray, dz_dy: np.ndarray) -> np.ndarray:
    """Aspetto in gradi: 0/360=N, 90=E, 180=S, 270=W."""
    aspect = np.degrees(np.arctan2(dz_dy, -dz_dx))
    return np.mod(90.0 - aspect, 360.0)


def hillshade(
    slope_rad: np.ndarray,
    aspect_deg: np.ndarray,
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0,
) -> np.ndarray:
    """Calcola un hillshade 0-255."""
    azimuth_math = np.radians(360.0 - azimuth_deg + 90.0)
    altitude = np.radians(altitude_deg)
    aspect = np.radians(aspect_deg)
    shaded = (
        np.sin(altitude) * np.cos(slope_rad)
        + np.cos(altitude) * np.sin(slope_rad) * np.cos(azimuth_math - aspect)
    )
    return np.clip(255.0 * shaded, 0.0, 255.0)


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    dtm_files = sorted(args.dtm_dir.glob(args.pattern))
    if not dtm_files:
        raise FileNotFoundError(
            f"Nessun DTM trovato in {args.dtm_dir} con pattern {args.pattern!r}."
        )
    if not args.boundary.exists():
        raise FileNotFoundError(f"Confine non trovato: {args.boundary}")

    print(f"DTM trovati: {len(dtm_files)}")
    for path in dtm_files:
        print(f"  - {path.name}")

    boundary = gpd.read_file(args.boundary)
    if boundary.empty:
        raise ValueError("Il file del confine non contiene geometrie.")
    if boundary.crs is None:
        raise ValueError("Il file del confine non dichiara un CRS.")

    boundary = boundary[boundary.geometry.notna() & ~boundary.geometry.is_empty].copy()
    boundary = boundary.to_crs(DTM_CRS)
    boundary["geometry"] = boundary.geometry.make_valid()
    boundary = boundary.explode(index_parts=False).reset_index(drop=True)
    boundary = boundary.dissolve().reset_index(drop=True)
    boundary.to_file(args.out_dir / "confine_povo_25832.gpkg", driver="GPKG")

    with ExitStack() as stack:
        sources = []
        for path in dtm_files:
            src = stack.enter_context(rasterio.open(path))
            if src.crs not in (None, DTM_CRS):
                raise ValueError(
                    f"{path.name}: CRS inatteso {src.crs}; previsto assente o EPSG:25832."
                )
            if not math.isclose(abs(src.transform.a), 1.0, rel_tol=0, abs_tol=1e-6):
                print(
                    f"Attenzione: {path.name} ha risoluzione X {src.transform.a}",
                    file=sys.stderr,
                )
            sources.append(src)

        mosaic, mosaic_transform = merge(
            sources,
            nodata=OUT_NODATA,
            dtype="float32",
            method="first",
        )

    mosaic_profile = {
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "count": 1,
        "dtype": "float32",
        "crs": DTM_CRS,
        "transform": mosaic_transform,
        "nodata": OUT_NODATA,
    }

    # Ritaglio del mosaico sul confine, senza creare un file intermedio.
    with MemoryFile() as memfile:
        with memfile.open(**mosaic_profile) as tmp:
            tmp.write(mosaic)
            clipped, clipped_transform = mask(
                tmp,
                boundary.geometry,
                crop=True,
                nodata=OUT_NODATA,
                filled=True,
                all_touched=args.all_touched,
            )

    dem = clipped[0].astype("float32")
    valid = np.isfinite(dem) & (dem != OUT_NODATA)
    if not valid.any():
        raise ValueError("Il confine non interseca i DTM forniti.")

    # Ricrea con precisione la maschera geometrica per evitare valori fuori confine.
    inside = geometry_mask(
        boundary.geometry,
        out_shape=dem.shape,
        transform=clipped_transform,
        invert=True,
        all_touched=args.all_touched,
    )
    valid &= inside
    dem[~valid] = OUT_NODATA

    # Per i derivati riempiamo temporaneamente i NoData, poi ripristiniamo la maschera.
    fill_input = np.where(valid, dem, 0.0).astype("float32")
    fill_mask = valid.astype("uint8")
    dem_filled = fillnodata(fill_input, mask=fill_mask, max_search_distance=100)

    xres = abs(clipped_transform.a)
    yres = abs(clipped_transform.e)
    dz_dy, dz_dx = np.gradient(dem_filled.astype("float64"), yres, xres)

    slope_rad = np.arctan(np.hypot(dz_dx, dz_dy))
    slope_deg = np.degrees(slope_rad)
    slope_pct = 100.0 * np.tan(slope_rad)
    aspect_deg = circular_aspect(dz_dx, dz_dy)
    shade = hillshade(slope_rad, aspect_deg)

    for arr in (slope_deg, slope_pct, aspect_deg, shade):
        arr[~valid] = OUT_NODATA

    write_raster(
        args.out_dir / "dtm_povo.tif",
        dem,
        clipped_transform,
        DTM_CRS,
        OUT_NODATA,
    )
    write_raster(
        args.out_dir / "pendenza_gradi_povo.tif",
        slope_deg.astype("float32"),
        clipped_transform,
        DTM_CRS,
        OUT_NODATA,
    )
    write_raster(
        args.out_dir / "pendenza_percentuale_povo.tif",
        slope_pct.astype("float32"),
        clipped_transform,
        DTM_CRS,
        OUT_NODATA,
    )
    write_raster(
        args.out_dir / "esposizione_povo.tif",
        aspect_deg.astype("float32"),
        clipped_transform,
        DTM_CRS,
        OUT_NODATA,
    )
    write_raster(
        args.out_dir / "hillshade_povo.tif",
        shade.astype("float32"),
        clipped_transform,
        DTM_CRS,
        OUT_NODATA,
    )

    valid_dem = dem[valid].astype("float64")
    valid_slope = slope_deg[valid].astype("float64")
    pixel_area = xres * yres
    stats = {
        "crs": "EPSG:25832",
        "risoluzione_x_m": xres,
        "risoluzione_y_m": yres,
        "pixel_validi": int(valid.sum()),
        "area_raster_valida_m2": float(valid.sum() * pixel_area),
        "quota_min_m": float(np.min(valid_dem)),
        "quota_media_m": float(np.mean(valid_dem)),
        "quota_mediana_m": float(np.median(valid_dem)),
        "quota_max_m": float(np.max(valid_dem)),
        "pendenza_media_gradi": float(np.mean(valid_slope)),
        "pendenza_mediana_gradi": float(np.median(valid_slope)),
        "pendenza_p90_gradi": float(np.percentile(valid_slope, 90)),
        "pendenza_max_gradi": float(np.max(valid_slope)),
    }

    with (args.out_dir / "statistiche_dtm_povo.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.writer(fh)
        writer.writerow(["indicatore", "valore"])
        writer.writerows(stats.items())

    print("\nOutput creati:")
    for path in sorted(args.out_dir.iterdir()):
        print(f"  - {path.name}")
    print("\nStatistiche principali:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        raise SystemExit(1)
