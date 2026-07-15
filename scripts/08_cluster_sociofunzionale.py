#!/usr/bin/env python3
"""
Cluster socio-funzionale delle sezioni di Povo.

Input:
    GeoJSON FeatureCollection con le variabili territoriali.

Output:
    - GeoJSON con i campi:
        cluster_v2
        profilo_cluster_v2
    - CSV con i profili medi dei cluster
    - CSV con l'assegnazione di ogni sezione

Esempio:
    python 08_cluster_sociofunzionale.py \
        --input 1.json \
        --output-dir output_cluster_sociofunzionale \
        --clusters 4
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler


DEFAULT_FEATURES: List[str] = [
    "pop_riferimento",
    "fam_riferimento",
    "abi_riferimento",
    "dislivello_sezione_m",
    "srv__servizi_5min",
    "srv__servizi_15min",
    "srv__t_associazioni_e_gruppi_min",
    "srv__t_cultura_e_tempo_libero_min",
    "srv__t_ristorazione_e_agriturismi_min",
    "srv__t_servizi_e_attivit_economiche_min",
    "gtfs__tempo_fermata_qualsiasi_min",
    "gtfs__passaggi_totali_fermata",
]

LOG_FEATURES = [
    "pop_riferimento",
    "fam_riferimento",
    "abi_riferimento",
    "dislivello_sezione_m",
    "srv__servizi_5min",
    "srv__servizi_15min",
    "gtfs__passaggi_totali_fermata",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clusterizza le sezioni territoriali e genera un GeoJSON."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="GeoJSON o JSON FeatureCollection di input.",
    )
    parser.add_argument(
        "--output-dir",
        default="output_cluster_sociofunzionale",
        help="Cartella di output.",
    )
    parser.add_argument(
        "--clusters",
        type=int,
        default=4,
        help="Numero di cluster da produrre. Default: 4.",
    )
    return parser.parse_args()


def read_geojson(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("type") != "FeatureCollection":
        raise ValueError("Il file deve essere un GeoJSON FeatureCollection.")

    if not data.get("features"):
        raise ValueError("Il GeoJSON non contiene feature.")

    return data


def properties_dataframe(geojson: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [feature.get("properties", {}) for feature in geojson["features"]]
    )


def validate_features(df: pd.DataFrame, features: List[str]) -> None:
    missing = [name for name in features if name not in df.columns]
    if missing:
        raise ValueError(
            "Mancano le seguenti variabili richieste:\n- "
            + "\n- ".join(missing)
        )


def prepare_matrix(df: pd.DataFrame, features: List[str]) -> np.ndarray:
    x = df[features].apply(pd.to_numeric, errors="coerce").copy()

    # Winsorization 1%-99% per ridurre l'effetto degli outlier.
    for column in x.columns:
        valid = x[column].dropna()
        if valid.empty:
            continue
        lower, upper = valid.quantile([0.01, 0.99])
        x[column] = x[column].clip(lower, upper)

    # Trasformazione logaritmica delle quantità molto asimmetriche.
    for column in LOG_FEATURES:
        if column in x.columns:
            x[column] = np.log1p(x[column].clip(lower=0))

    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
        ]
    )

    return pipeline.fit_transform(x)


def build_cluster_profiles(
    df: pd.DataFrame,
    features: List[str],
    cluster_column: str,
) -> pd.DataFrame:
    profile = df.groupby(cluster_column)[features].mean(numeric_only=True)
    profile["n_sezioni"] = df.groupby(cluster_column).size()
    return profile


def assign_profile_names(profile: pd.DataFrame) -> Dict[int, str]:
    """
    Assegna etichette interpretative ai cluster sulla base dei valori medi.
    """

    residential = (
        profile["pop_riferimento"].rank(pct=True)
        + profile["fam_riferimento"].rank(pct=True)
        + profile["abi_riferimento"].rank(pct=True)
    ) / 3

    services = (
        profile["srv__servizi_5min"].rank(pct=True)
        + profile["srv__servizi_15min"].rank(pct=True)
        + profile["srv__t_cultura_e_tempo_libero_min"].rank(
            pct=True, ascending=False
        )
        + profile["srv__t_servizi_e_attivit_economiche_min"].rank(
            pct=True, ascending=False
        )
    ) / 4

    transport = (
        profile["gtfs__tempo_fermata_qualsiasi_min"].rank(
            pct=True, ascending=False
        )
        + profile["gtfs__passaggi_totali_fermata"].rank(pct=True)
    ) / 2

    morphology = profile["dislivello_sezione_m"].rank(
        pct=True, ascending=False
    )

    names: Dict[int, str] = {}
    remaining = set(profile.index.tolist())

    central = (services + transport).idxmax()
    names[int(central)] = "centralita_servita"
    remaining.remove(central)

    if remaining:
        peripheral_score = (
            (1 - services)
            + (1 - transport)
            + (1 - morphology)
        )
        peripheral = peripheral_score.loc[list(remaining)].idxmax()
        names[int(peripheral)] = (
            "area_periferica_morfologicamente_svantaggiata"
        )
        remaining.remove(peripheral)

    if remaining:
        residential_cluster = residential.loc[list(remaining)].idxmax()
        names[int(residential_cluster)] = "nucleo_residenziale"
        remaining.remove(residential_cluster)

    for cluster_id in remaining:
        names[int(cluster_id)] = "area_mista_di_transizione"

    return names


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.clusters < 2:
        raise ValueError("--clusters deve essere almeno 2.")

    geojson = read_geojson(input_path)
    df = properties_dataframe(geojson)

    validate_features(df, DEFAULT_FEATURES)

    matrix = prepare_matrix(df, DEFAULT_FEATURES)

    model = AgglomerativeClustering(
        n_clusters=args.clusters,
        linkage="ward",
    )
    labels = model.fit_predict(matrix)

    df["cluster_v2"] = labels + 1

    silhouette = silhouette_score(matrix, labels)

    profile = build_cluster_profiles(
        df=df,
        features=DEFAULT_FEATURES,
        cluster_column="cluster_v2",
    )

    profile_names = assign_profile_names(profile)
    df["profilo_cluster_v2"] = df["cluster_v2"].map(profile_names)

    profile["profilo_cluster_v2"] = profile.index.map(profile_names)
    profile["silhouette"] = silhouette
    profile = profile.reset_index()

    # Aggiunge i risultati alle proprietà del GeoJSON.
    for index, feature in enumerate(geojson["features"]):
        properties = feature.setdefault("properties", {})
        properties["cluster_v2"] = int(df.loc[index, "cluster_v2"])
        properties["profilo_cluster_v2"] = str(
            df.loc[index, "profilo_cluster_v2"]
        )

    geojson_path = output_dir / "sezioni_povo_cluster_sociofunzionali.geojson"
    profiles_path = output_dir / "profili_cluster_sociofunzionali.csv"
    assignments_path = output_dir / "assegnazione_cluster_sezioni.csv"
    metadata_path = output_dir / "metadati_cluster.json"

    with geojson_path.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    profile.to_csv(profiles_path, index=False)

    assignment_columns = [
        "cluster_v2",
        "profilo_cluster_v2",
        *DEFAULT_FEATURES,
    ]
    df[assignment_columns].to_csv(assignments_path, index=False)

    metadata = {
        "input": str(input_path),
        "numero_sezioni": int(len(df)),
        "numero_cluster": int(args.clusters),
        "metodo": "AgglomerativeClustering",
        "linkage": "ward",
        "scaling": "RobustScaler",
        "imputazione": "mediana",
        "winsorization": "1%-99%",
        "silhouette": float(silhouette),
        "variabili": DEFAULT_FEATURES,
    }

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print("Elaborazione completata")
    print(f"Sezioni: {len(df)}")
    print(f"Cluster: {args.clusters}")
    print(f"Silhouette: {silhouette:.3f}")
    print(f"GeoJSON: {geojson_path}")
    print(f"Profili: {profiles_path}")
    print(f"Assegnazioni: {assignments_path}")
    print(f"Metadati: {metadata_path}")


if __name__ == "__main__":
    main()
