#!/usr/bin/env python3
"""Integra sezioni censuarie di Povo, dati ISTAT 2023 e indicatori DTM.

Mantiene tutte le geometrie; unisce i dati ISTAT tramite SEZ21_ID; usa i campi
POP21/FAM21/ABI21/EDI21 del GeoJSON come fallback; calcola statistiche zonali
su quota e pendenza e produce GeoPackage, GeoJSON e CSV.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask

KEY = "SEZ21_ID"
FALLBACKS = {"pop_riferimento": ("P1", "POP21"), "fam_riferimento": ("PF1", "FAM21"),
             "abi_riferimento": ("A1", "ABI21"), "edi_riferimento": ("E1", "EDI21")}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sections", default="sezioni_censimento(1).geojson")
    p.add_argument("--istat", default="R04_Trentino-Alto Adige_2023_sezioni(1).xlsx")
    p.add_argument("--dtm", required=True, help="DTM ritagliato/mosaicato")
    p.add_argument("--slope-deg", required=True, help="Raster della pendenza in gradi")
    p.add_argument("--slope-pct", default=None, help="Raster opzionale della pendenza percentuale")
    p.add_argument("--out-dir", default="output_sezioni_povo")
    return p.parse_args()


def norm_key(s: pd.Series) -> pd.Series:
    return s.astype("string").str.replace(r"\.0$", "", regex=True).str.strip()


def first_existing(df: pd.DataFrame, names: Iterable[str]) -> pd.Series:
    out = pd.Series(pd.NA, index=df.index, dtype="Float64")
    for name in names:
        if name in df.columns:
            vals = pd.to_numeric(df[name], errors="coerce").astype("Float64")
            out = out.fillna(vals)
    return out


def zonal_stats(gdf: gpd.GeoDataFrame, raster_path: Path, prefix: str) -> pd.DataFrame:
    rows = []
    with rasterio.open(raster_path) as src:
        work = gdf.to_crs(src.crs)
        nodata = src.nodata
        for geom in work.geometry:
            try:
                arr, _ = mask(src, [geom.__geo_interface__], crop=True, filled=False)
                values = arr[0]
                if np.ma.isMaskedArray(values):
                    values = values.compressed()
                else:
                    values = values.ravel()
                    if nodata is not None:
                        values = values[values != nodata]
                values = values[np.isfinite(values)]
            except ValueError:
                values = np.array([], dtype=float)
            if values.size:
                rows.append({
                    f"{prefix}_min": float(np.min(values)),
                    f"{prefix}_mean": float(np.mean(values)),
                    f"{prefix}_median": float(np.median(values)),
                    f"{prefix}_max": float(np.max(values)),
                    f"{prefix}_std": float(np.std(values)),
                    f"{prefix}_n": int(values.size),
                })
            else:
                rows.append({f"{prefix}_{x}": np.nan for x in ("min", "mean", "median", "max", "std")})
                rows[-1][f"{prefix}_n"] = 0
    return pd.DataFrame(rows, index=gdf.index)


def slope_class(v: float) -> str:
    if pd.isna(v): return "dato non disponibile"
    if v < 3: return "quasi pianeggiante (<3°)"
    if v < 8: return "debole (3–8°)"
    if v < 15: return "moderata (8–15°)"
    if v < 25: return "elevata (15–25°)"
    if v < 35: return "molto elevata (25–35°)"
    return "estrema (≥35°)"


def main() -> None:
    a = parse_args()
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    sections = gpd.read_file(a.sections)
    if KEY not in sections.columns: raise KeyError(f"Manca {KEY} nel GeoJSON")
    sections[KEY] = norm_key(sections[KEY])

    istat = pd.read_excel(a.istat)
    if KEY not in istat.columns: raise KeyError(f"Manca {KEY} nel file ISTAT")
    istat[KEY] = norm_key(istat[KEY])
    istat = istat.drop_duplicates(KEY, keep="first")
    istat["match_istat_2023"] = True

    merged = sections.merge(istat, on=KEY, how="left", suffixes=("_geo", "_istat"))
    merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=sections.crs)
    merged["match_istat_2023"] = merged["match_istat_2023"].fillna(False).astype(bool)

    for target, candidates in FALLBACKS.items():
        merged[target] = first_existing(merged, candidates)

    metric = merged.to_crs(25832)
    merged["area_m2"] = metric.area
    merged["area_km2"] = merged["area_m2"] / 1_000_000
    merged["perimetro_m"] = metric.length
    merged["dens_pop_km2"] = merged["pop_riferimento"] / merged["area_km2"].replace(0, np.nan)
    merged["persone_famiglia"] = merged["pop_riferimento"] / merged["fam_riferimento"].replace(0, np.nan)

    for path, prefix in [(Path(a.dtm), "quota_m"), (Path(a.slope_deg), "pend_deg")]:
        merged = pd.concat([merged, zonal_stats(merged, path, prefix)], axis=1)
    if a.slope_pct:
        merged = pd.concat([merged, zonal_stats(merged, Path(a.slope_pct), "pend_pct")], axis=1)

    merged["dislivello_m"] = merged["quota_m_max"] - merged["quota_m_min"]
    merged["classe_pendenza"] = merged["pend_deg_median"].map(slope_class)

    # Output metrici, adatti a QGIS e a ulteriori analisi.
    output_gdf = merged.to_crs(25832)
    gpkg = out / "sezioni_povo_istat_dtm.gpkg"
    geojson = out / "sezioni_povo_istat_dtm.geojson"
    csv = out / "sezioni_povo_istat_dtm.csv"
    output_gdf.to_file(gpkg, layer="sezioni_istat_dtm", driver="GPKG")
    output_gdf.to_crs(4326).to_file(geojson, driver="GeoJSON")
    pd.DataFrame(output_gdf.drop(columns="geometry")).to_csv(csv, index=False)

    no_match = output_gdf.loc[~output_gdf["match_istat_2023"], [KEY, "POP21", "FAM21", "ABI21", "EDI21"]]
    no_match.to_csv(out / "sezioni_senza_match_istat.csv", index=False)

    summary = pd.DataFrame([{
        "sezioni_totali": len(output_gdf),
        "sezioni_con_match_istat": int(output_gdf["match_istat_2023"].sum()),
        "sezioni_senza_match_istat": int((~output_gdf["match_istat_2023"]).sum()),
        "popolazione_riferimento": float(output_gdf["pop_riferimento"].sum(skipna=True)),
        "crs_output_gpkg": "EPSG:25832",
    }])
    summary.to_csv(out / "sintesi_elaborazione.csv", index=False)
    metadata = {
        "chiave_join": KEY,
        "crs_sezioni_input": str(sections.crs),
        "crs_output_metric": "EPSG:25832",
        "file_input": {"sections": a.sections, "istat": a.istat, "dtm": a.dtm,
                       "slope_deg": a.slope_deg, "slope_pct": a.slope_pct},
        "fallback": FALLBACKS,
    }
    (out / "metadati_elaborazione.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Elaborazione completata. Output in: {out.resolve()}")


if __name__ == "__main__":
    main()
