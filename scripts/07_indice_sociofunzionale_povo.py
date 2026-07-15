#!/usr/bin/env python3
"""Costruisce un indice composito e una classificazione socio-funzionale delle sezioni di Povo.

Input attesi:
- sezioni ISTAT + DTM (GeoPackage del passaggio 03)
- accessibilita ai servizi (GeoPackage del passaggio 05)
- accessibilita GTFS multifeed (GeoPackage del passaggio 06 v3)

Lo script e' volutamente tollerante rispetto ai nomi delle colonne: cerca automaticamente
le varianti piu probabili e documenta nei metadati quali campi sono stati utilizzati.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def norm_name(value: str) -> str:
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    lookup = {norm_name(c): c for c in columns}
    for cand in candidates:
        hit = lookup.get(norm_name(cand))
        if hit is not None:
            return hit
    return None


def read_layer(path: Path, layer: str | None) -> gpd.GeoDataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    if layer:
        return gpd.read_file(path, layer=layer)
    return gpd.read_file(path)


def choose_key(*frames: gpd.GeoDataFrame) -> str:
    candidates = ["SEZ21_ID", "sez21_id", "sezione_id", "section_id", "id"]
    for candidate in candidates:
        actuals = [first_existing(f.columns, [candidate]) for f in frames]
        if all(a is not None for a in actuals):
            return candidate
    common = set(frames[0].columns)
    for frame in frames[1:]:
        common &= set(frame.columns)
    common -= {"geometry"}
    if not common:
        raise ValueError("Nessuna chiave comune trovata tra i layer")
    return sorted(common)[0]


def to_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(
        series.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip(),
        errors="coerce",
    )


def min_of_matching(df: pd.DataFrame, patterns: Iterable[str]) -> tuple[pd.Series, list[str]]:
    cols = []
    normalized = {c: norm_name(c) for c in df.columns}
    for c, n in normalized.items():
        if any(re.search(p, n) for p in patterns):
            cols.append(c)
    if not cols:
        return pd.Series(np.nan, index=df.index), []
    vals = pd.concat([to_numeric(df[c]) for c in cols], axis=1)
    return vals.min(axis=1, skipna=True), cols


def sum_of_matching(df: pd.DataFrame, patterns: Iterable[str]) -> tuple[pd.Series, list[str]]:
    cols = []
    normalized = {c: norm_name(c) for c in df.columns}
    for c, n in normalized.items():
        if any(re.search(p, n) for p in patterns):
            cols.append(c)
    if not cols:
        return pd.Series(0.0, index=df.index), []
    vals = pd.concat([to_numeric(df[c]) for c in cols], axis=1)
    return vals.fillna(0).sum(axis=1), cols


def robust_z(series: pd.Series) -> pd.Series:
    s = to_numeric(series)
    median = s.median(skipna=True)
    mad = (s - median).abs().median(skipna=True)
    if pd.isna(mad) or mad == 0:
        std = s.std(skipna=True)
        if pd.isna(std) or std == 0:
            return pd.Series(0.0, index=s.index)
        return (s - s.mean(skipna=True)) / std
    return 0.67448975 * (s - median) / mad


def percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    s = to_numeric(series)
    out = s.rank(pct=True, method="average") * 100
    if not higher_is_better:
        out = 100 - out
    return out.fillna(50.0)


def safe_mean(columns: list[pd.Series]) -> pd.Series:
    return pd.concat(columns, axis=1).mean(axis=1, skipna=True).fillna(50.0)


def classify_quartile(score: pd.Series) -> pd.Series:
    q = score.rank(pct=True)
    return pd.cut(
        q,
        bins=[0, 0.25, 0.50, 0.75, 1.0],
        labels=["molto_bassa", "bassa", "media", "alta"],
        include_lowest=True,
    ).astype(str)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sections", required=True, type=Path)
    parser.add_argument("--sections-layer", default="sezioni_istat_dtm")
    parser.add_argument("--services", required=True, type=Path)
    parser.add_argument("--services-layer", default="sezioni_accessibilita")
    parser.add_argument("--gtfs", required=True, type=Path)
    parser.add_argument("--gtfs-layer", default="sezioni_accessibilita_gtfs")
    parser.add_argument("--clusters", type=int, default=4)
    parser.add_argument("--out-dir", type=Path, default=Path("output_indice_sociofunzionale"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    base = read_layer(args.sections, args.sections_layer)
    srv = read_layer(args.services, args.services_layer)
    gtfs = read_layer(args.gtfs, args.gtfs_layer)

    key_hint = choose_key(base, srv, gtfs)
    key_base = first_existing(base.columns, [key_hint])
    key_srv = first_existing(srv.columns, [key_hint])
    key_gtfs = first_existing(gtfs.columns, [key_hint])
    if not all([key_base, key_srv, key_gtfs]):
        raise ValueError("Impossibile risolvere la chiave delle sezioni nei tre layer")

    base[key_base] = base[key_base].astype(str)
    srv[key_srv] = srv[key_srv].astype(str)
    gtfs[key_gtfs] = gtfs[key_gtfs].astype(str)

    srv_tab = pd.DataFrame(srv.drop(columns="geometry"))
    gtfs_tab = pd.DataFrame(gtfs.drop(columns="geometry"))
    srv_tab = srv_tab.rename(columns={key_srv: key_base})
    gtfs_tab = gtfs_tab.rename(columns={key_gtfs: key_base})

    # prefissi per evitare collisioni
    srv_tab = srv_tab.rename(columns={c: f"srv__{c}" for c in srv_tab.columns if c != key_base})
    gtfs_tab = gtfs_tab.rename(columns={c: f"gtfs__{c}" for c in gtfs_tab.columns if c != key_base})

    gdf = base.merge(srv_tab, on=key_base, how="left", validate="1:1")
    gdf = gdf.merge(gtfs_tab, on=key_base, how="left", validate="1:1")

    used: dict[str, object] = {"join_key": key_base}

    pop_col = first_existing(gdf.columns, [
        "pop_riferimento", "popolazione", "pop21", "p1", "residenti", "population"
    ])
    dens_col = first_existing(gdf.columns, [
        "densita_pop_km2", "dens_pop_km2", "densita_abitativa", "population_density"
    ])
    slope_col = first_existing(gdf.columns, [
        "slope_deg_mean", "pendenza_gradi_mean", "pendenza_media_gradi", "slope_mean"
    ])
    relief_col = first_existing(gdf.columns, [
        "dislivello_m", "quota_range", "elev_range", "dtm_range", "elevation_range"
    ])

    if pop_col:
        gdf["popolazione_rif"] = to_numeric(gdf[pop_col]).fillna(0)
    else:
        gdf["popolazione_rif"] = 0.0
    if dens_col:
        gdf["densita_pop_rif"] = to_numeric(gdf[dens_col])
    else:
        area_km2 = gdf.geometry.to_crs(25832).area / 1_000_000
        gdf["densita_pop_rif"] = gdf["popolazione_rif"] / area_km2.replace(0, np.nan)

    gdf["pendenza_media_gradi"] = to_numeric(gdf[slope_col]) if slope_col else np.nan
    gdf["dislivello_sezione_m"] = to_numeric(gdf[relief_col]) if relief_col else np.nan
    used.update({"population": pop_col, "density": dens_col, "slope": slope_col, "relief": relief_col})

    # Servizi: tempi minimi e conteggi entro soglia, indipendentemente dal nome esatto delle categorie.
    srv_time, srv_time_cols = min_of_matching(gdf, [
        r"^srv__.*tempo.*serv", r"^srv__.*time.*serv", r"^srv__.*minuti.*serv"
    ])
    if not srv_time_cols:
        srv_time, srv_time_cols = min_of_matching(gdf, [r"^srv__.*tempo.*min", r"^srv__.*nearest.*min"])

    srv_5, srv_5_cols = sum_of_matching(gdf, [r"^srv__.*entro_?5", r"^srv__.*5_min", r"^srv__.*raggiung.*5"])
    srv_10, srv_10_cols = sum_of_matching(gdf, [r"^srv__.*entro_?10", r"^srv__.*10_min", r"^srv__.*raggiung.*10"])
    srv_15, srv_15_cols = sum_of_matching(gdf, [r"^srv__.*entro_?15", r"^srv__.*15_min", r"^srv__.*raggiung.*15"])

    # Evita di sommare flag binari generici insieme ai conteggi se il risultato e' solo 0/1.
    gdf["tempo_servizio_min"] = srv_time
    gdf["servizi_5_min"] = srv_5
    gdf["servizi_10_min"] = srv_10
    gdf["servizi_15_min"] = srv_15
    used["service_time_columns"] = srv_time_cols
    used["service_5_columns"] = srv_5_cols
    used["service_10_columns"] = srv_10_cols
    used["service_15_columns"] = srv_15_cols

    # GTFS: tempo alla fermata migliore e offerta associata.
    gtfs_time_col = first_existing(gdf.columns, [
        "gtfs__tempo_fermata_qualsiasi_min", "gtfs__tempo_fermata_migliore_min",
        "gtfs__tempo_fermata_min", "gtfs__walk_time_min"
    ])
    gtfs_pass_col = first_existing(gdf.columns, [
        "gtfs__passaggi_totali", "gtfs__numero_passaggi", "gtfs__corse_totali"
    ])
    gtfs_freq_col = first_existing(gdf.columns, [
        "gtfs__frequenza_totale_min", "gtfs__frequenza_media_min",
        "gtfs__headway_min", "gtfs__frequenza_urbana_min"
    ])

    if gtfs_time_col is None:
        gtfs_time, gtfs_time_cols = min_of_matching(gdf, [r"^gtfs__.*tempo.*fermata.*min"])
    else:
        gtfs_time = to_numeric(gdf[gtfs_time_col])
        gtfs_time_cols = [gtfs_time_col]
    gdf["tempo_fermata_min"] = gtfs_time
    gdf["passaggi_totali"] = to_numeric(gdf[gtfs_pass_col]) if gtfs_pass_col else np.nan
    gdf["frequenza_media_min"] = to_numeric(gdf[gtfs_freq_col]) if gtfs_freq_col else np.nan
    used.update({
        "gtfs_time_columns": gtfs_time_cols,
        "gtfs_passages": gtfs_pass_col,
        "gtfs_frequency": gtfs_freq_col,
    })

    # Cinque dimensioni, tutte 0-100 e orientate in senso positivo.
    gdf["score_residenza"] = safe_mean([
        percentile_score(gdf["popolazione_rif"], True),
        percentile_score(gdf["densita_pop_rif"], True),
    ])

    terrain_parts = []
    if gdf["pendenza_media_gradi"].notna().any():
        terrain_parts.append(percentile_score(gdf["pendenza_media_gradi"], False))
    if gdf["dislivello_sezione_m"].notna().any():
        terrain_parts.append(percentile_score(gdf["dislivello_sezione_m"], False))
    gdf["score_facilita_territoriale"] = safe_mean(terrain_parts or [pd.Series(50.0, index=gdf.index)])

    service_parts = []
    if gdf["tempo_servizio_min"].notna().any():
        service_parts.append(percentile_score(gdf["tempo_servizio_min"], False))
    for c in ["servizi_5_min", "servizi_10_min", "servizi_15_min"]:
        if gdf[c].notna().any() and gdf[c].max(skipna=True) > 0:
            service_parts.append(percentile_score(gdf[c], True))
    gdf["score_servizi"] = safe_mean(service_parts or [pd.Series(50.0, index=gdf.index)])

    transit_parts = []
    if gdf["tempo_fermata_min"].notna().any():
        transit_parts.append(percentile_score(gdf["tempo_fermata_min"], False))
    if gdf["passaggi_totali"].notna().any():
        transit_parts.append(percentile_score(gdf["passaggi_totali"], True))
    if gdf["frequenza_media_min"].notna().any():
        transit_parts.append(percentile_score(gdf["frequenza_media_min"], False))
    gdf["score_trasporto_pubblico"] = safe_mean(transit_parts or [pd.Series(50.0, index=gdf.index)])

    # Accessibilita complessiva: servizi 40%, TPL 35%, facilita territoriale 25%.
    gdf["indice_accessibilita"] = (
        0.40 * gdf["score_servizi"]
        + 0.35 * gdf["score_trasporto_pubblico"]
        + 0.25 * gdf["score_facilita_territoriale"]
    )

    # Indice civico-territoriale: accessibilita 65%, intensita residenziale 35%.
    gdf["indice_civico_territoriale"] = (
        0.65 * gdf["indice_accessibilita"]
        + 0.35 * gdf["score_residenza"]
    )
    gdf["classe_accessibilita"] = classify_quartile(gdf["indice_accessibilita"])
    gdf["classe_civico_territoriale"] = classify_quartile(gdf["indice_civico_territoriale"])

    # Clustering socio-funzionale su cinque dimensioni interpretabili.
    features = [
        "score_residenza", "score_servizi", "score_trasporto_pubblico",
        "score_facilita_territoriale", "indice_accessibilita"
    ]
    X = gdf[features].replace([np.inf, -np.inf], np.nan).fillna(50.0)
    n_clusters = max(2, min(args.clusters, len(gdf)))
    Xs = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=n_clusters, n_init=30, random_state=42)
    raw_labels = km.fit_predict(Xs)
    gdf["cluster_id"] = raw_labels + 1

    profiles = gdf.groupby("cluster_id")[features].mean().round(1)
    overall = gdf[features].mean()

    def label_cluster(row: pd.Series) -> str:
        res = row["score_residenza"] - overall["score_residenza"]
        srv = row["score_servizi"] - overall["score_servizi"]
        tpl = row["score_trasporto_pubblico"] - overall["score_trasporto_pubblico"]
        acc = row["indice_accessibilita"] - overall["indice_accessibilita"]
        terr = row["score_facilita_territoriale"] - overall["score_facilita_territoriale"]
        if srv > 8 and tpl > 8 and acc > 8:
            return "centralita_accessibile"
        if res > 8 and acc <= 8:
            return "nucleo_residenziale"
        if tpl > 8 and res < -5:
            return "polo_attrattore_connesso"
        if acc < -8 or terr < -8:
            return "area_periferica_o_morfologicamente_svantaggiata"
        return "area_mista_di_transizione"

    label_map = {int(idx): label_cluster(row) for idx, row in profiles.iterrows()}
    # rende univoci eventuali nomi duplicati
    counts: dict[str, int] = {}
    for cid in sorted(label_map):
        name = label_map[cid]
        counts[name] = counts.get(name, 0) + 1
        if counts[name] > 1:
            label_map[cid] = f"{name}_{counts[name]}"
    gdf["profilo_sociofunzionale"] = gdf["cluster_id"].map(label_map)

    # Output
    gpkg = args.out_dir / "indice_sociofunzionale_povo.gpkg"
    geojson = args.out_dir / "indice_sociofunzionale_povo.geojson"
    csv = args.out_dir / "indice_sociofunzionale_povo.csv"
    profile_csv = args.out_dir / "profili_cluster.csv"
    summary_csv = args.out_dir / "sintesi_indici.csv"
    metadata_json = args.out_dir / "metadati_indice.json"

    gdf.to_file(gpkg, layer="sezioni_indice_sociofunzionale", driver="GPKG")
    gdf.to_file(geojson, driver="GeoJSON")
    pd.DataFrame(gdf.drop(columns="geometry")).to_csv(csv, index=False)

    profiles_out = profiles.copy()
    profiles_out["profilo_sociofunzionale"] = [label_map[int(i)] for i in profiles_out.index]
    profiles_out["numero_sezioni"] = gdf.groupby("cluster_id").size()
    profiles_out.to_csv(profile_csv)

    summary = pd.DataFrame({
        "indicatore": [
            "numero_sezioni", "popolazione_totale", "indice_accessibilita_medio",
            "indice_civico_territoriale_medio", "numero_cluster"
        ],
        "valore": [
            len(gdf), gdf["popolazione_rif"].sum(), gdf["indice_accessibilita"].mean(),
            gdf["indice_civico_territoriale"].mean(), n_clusters
        ],
    })
    summary.to_csv(summary_csv, index=False)

    metadata = {
        "input": {
            "sections": str(args.sections),
            "services": str(args.services),
            "gtfs": str(args.gtfs),
        },
        "fields_used": used,
        "weights": {
            "indice_accessibilita": {
                "servizi": 0.40,
                "trasporto_pubblico": 0.35,
                "facilita_territoriale": 0.25,
            },
            "indice_civico_territoriale": {
                "accessibilita": 0.65,
                "intensita_residenziale": 0.35,
            },
        },
        "cluster_labels": label_map,
        "notes": [
            "Gli score sono percentili 0-100, orientati in modo che valori alti siano migliori.",
            "Il clustering e' esplorativo e deve essere validato cartograficamente e sul territorio.",
            "L'indice non misura direttamente i city users finche' non vengono forniti dati di affluenza o attrattori pesati.",
        ],
    }
    metadata_json.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Elaborazione completata: {args.out_dir.resolve()}")
    print(f"Sezioni analizzate: {len(gdf)}")
    print(f"Cluster generati: {n_clusters}")
    print(f"Output principale: {gpkg.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
