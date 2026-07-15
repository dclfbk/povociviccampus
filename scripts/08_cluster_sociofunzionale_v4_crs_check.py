#!/usr/bin/env python3
"""
08_cluster_sociofunzionale_v3.py

Clusterizza le sezioni territoriali di Povo a partire dall'output dello
script 07 v2 e genera un GeoJSON pronto per uMap.

Il modello utilizza quattro profili:

- Centralità locale ben servita
- Nucleo prevalentemente residenziale
- Area mista e di transizione
- Area periferica o penalizzata dalla morfologia

Oltre ai campi tecnici, lo script aggiunge campi leggibili e già formattati
per i popup pubblici, con numeri arrotondati e unità di misura.

Esempio:

python 08_cluster_sociofunzionale_v3.py \
  --input "output_indice_sociofunzionale_v2/indice_sociofunzionale_povo_v2.geojson" \
  --output-dir "output_cluster_sociofunzionale_v3"
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.impute import SimpleImputer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler


FEATURES: List[str] = [
    "popolazione_rif",
    "famiglie_rif",
    "abitazioni_rif",
    "dislivello_sezione_m",
    "servizi_5_min",
    "servizi_15_min",
    "tempo_associazioni_min",
    "tempo_cultura_min",
    "tempo_ristorazione_min",
    "tempo_attivita_economiche_min",
    "tempo_fermata_min",
    "passaggi_totali",
]

LOG_FEATURES = [
    "popolazione_rif",
    "famiglie_rif",
    "abitazioni_rif",
    "dislivello_sezione_m",
    "servizi_5_min",
    "servizi_15_min",
    "passaggi_totali",
]

PUBLIC_LABELS = {
    "centralita_servita": "Centralità locale ben servita",
    "nucleo_residenziale": "Nucleo prevalentemente residenziale",
    "area_mista_di_transizione": "Area mista e di transizione",
    "area_periferica_morfologicamente_svantaggiata":
        "Area periferica o penalizzata dalla morfologia",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clusterizza le sezioni socio-funzionali e genera un GeoJSON "
            "leggibile per uMap."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="GeoJSON prodotto dallo script 07 v2.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output_cluster_sociofunzionale_v3"),
        help="Cartella di output.",
    )
    parser.add_argument(
        "--clusters",
        type=int,
        default=4,
        help="Numero di cluster. Per la mappa pubblica usare 4.",
    )
    return parser.parse_args()


def load_geojson(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"File non trovato: {path}")

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


def validate_geojson_coordinates(geojson: dict) -> None:
    """
    uMap e GeoJSON RFC 7946 richiedono coordinate WGS84 in ordine lon, lat.
    Questo controllo intercetta coordinate metriche/proiettate prima dell'output.
    """
    coordinates = []

    def collect(value):
        if not isinstance(value, list):
            return
        if len(value) >= 2 and all(isinstance(x, (int, float)) for x in value[:2]):
            coordinates.append((float(value[0]), float(value[1])))
            return
        for item in value:
            collect(item)

    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        collect(geometry.get("coordinates"))

    if not coordinates:
        raise ValueError("Il GeoJSON non contiene coordinate geometriche valide.")

    xs = [xy[0] for xy in coordinates]
    ys = [xy[1] for xy in coordinates]

    if (
        min(xs) < -180
        or max(xs) > 180
        or min(ys) < -90
        or max(ys) > 90
    ):
        raise ValueError(
            "Le coordinate del GeoJSON non sono in EPSG:4326. "
            "Rieseguire lo script 07 corretto, che esporta il GeoJSON in WGS84."
        )


def numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    text = series.astype(str).str.strip()
    mask = text.str.contains(",", regex=False)
    text.loc[mask] = (
        text.loc[mask]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(text, errors="coerce")


def validate_features(df: pd.DataFrame) -> None:
    missing = [name for name in FEATURES if name not in df.columns]
    if missing:
        raise ValueError(
            "Mancano le seguenti variabili richieste:\n- "
            + "\n- ".join(missing)
        )


def prepare_matrix(df: pd.DataFrame) -> np.ndarray:
    x = pd.DataFrame(index=df.index)

    for column in FEATURES:
        x[column] = numeric(df[column])

    # Winsorization 1%-99% per ridurre l'effetto degli outlier.
    for column in x.columns:
        valid = x[column].dropna()
        if valid.empty:
            continue
        lower, upper = valid.quantile([0.01, 0.99])
        x[column] = x[column].clip(lower, upper)

    # Trasformazione logaritmica delle quantità più asimmetriche.
    for column in LOG_FEATURES:
        x[column] = np.log1p(x[column].clip(lower=0))

    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
        ]
    )

    return pipeline.fit_transform(x)


def cluster_profiles(
    df: pd.DataFrame,
    cluster_column: str,
) -> pd.DataFrame:
    numeric_frame = pd.DataFrame(index=df.index)
    for column in FEATURES:
        numeric_frame[column] = numeric(df[column])

    numeric_frame[cluster_column] = df[cluster_column]
    profile = numeric_frame.groupby(cluster_column)[FEATURES].mean()
    profile["n_sezioni"] = df.groupby(cluster_column).size()
    return profile


def assign_profile_names(profile: pd.DataFrame) -> Dict[int, str]:
    """
    Assegna un'etichetta interpretativa ai quattro cluster.
    """

    residential = (
        profile["popolazione_rif"].rank(pct=True)
        + profile["famiglie_rif"].rank(pct=True)
        + profile["abitazioni_rif"].rank(pct=True)
    ) / 3

    services = (
        profile["servizi_5_min"].rank(pct=True)
        + profile["servizi_15_min"].rank(pct=True)
        + profile["tempo_cultura_min"].rank(pct=True, ascending=False)
        + profile["tempo_attivita_economiche_min"].rank(
            pct=True, ascending=False
        )
    ) / 4

    transport = (
        profile["tempo_fermata_min"].rank(pct=True, ascending=False)
        + profile["passaggi_totali"].rank(pct=True)
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


def format_number(
    value: object,
    decimals: int = 0,
    suffix: str = "",
    missing: str = "Dato non disponibile",
) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return missing

    if not math.isfinite(number):
        return missing

    if decimals == 0:
        text = f"{number:.0f}"
    else:
        text = f"{number:.{decimals}f}"

    text = text.replace(".", ",")
    return f"{text}{suffix}"


def format_score(value: object) -> str:
    return format_number(value, decimals=1, suffix=" su 100")


def format_minutes(value: object) -> str:
    return format_number(value, decimals=1, suffix=" min")


def format_count(value: object, singular: str, plural: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Dato non disponibile"

    if not math.isfinite(number):
        return "Dato non disponibile"

    rounded = int(round(number))
    label = singular if rounded == 1 else plural
    return f"{rounded} {label}"


def add_public_fields(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    result["profilo_pubblico"] = result["profilo_cluster_v3"].map(
        PUBLIC_LABELS
    )

    result["residenti_label"] = result["popolazione_rif"].apply(
        lambda v: format_count(v, "residente", "residenti")
    )
    result["famiglie_label"] = result["famiglie_rif"].apply(
        lambda v: format_count(v, "famiglia", "famiglie")
    )
    result["abitazioni_label"] = result["abitazioni_rif"].apply(
        lambda v: format_count(v, "abitazione", "abitazioni")
    )

    result["densita_label"] = result.get(
        "densita_pop_rif",
        pd.Series(np.nan, index=result.index),
    ).apply(
        lambda v: format_number(v, decimals=0, suffix=" ab./km²")
    )

    result["dislivello_label"] = result["dislivello_sezione_m"].apply(
        lambda v: format_number(v, decimals=0, suffix=" m")
    )

    result["pendenza_label"] = result.get(
        "classe_pendenza",
        pd.Series("Dato non disponibile", index=result.index),
    ).fillna("Dato non disponibile")

    result["facilita_territoriale_label"] = result.get(
        "score_facilita_territoriale",
        pd.Series(np.nan, index=result.index),
    ).apply(format_score)

    result["servizi_5min_label"] = result["servizi_5_min"].apply(
        lambda v: format_count(v, "servizio", "servizi")
    )
    result["servizi_10min_label"] = result.get(
        "servizi_10_min",
        pd.Series(np.nan, index=result.index),
    ).apply(
        lambda v: format_count(v, "servizio", "servizi")
    )
    result["servizi_15min_label"] = result["servizi_15_min"].apply(
        lambda v: format_count(v, "servizio", "servizi")
    )

    result["tempo_associazioni_label"] = result[
        "tempo_associazioni_min"
    ].apply(format_minutes)
    result["tempo_cultura_label"] = result[
        "tempo_cultura_min"
    ].apply(format_minutes)
    result["tempo_ristorazione_label"] = result[
        "tempo_ristorazione_min"
    ].apply(format_minutes)
    result["tempo_attivita_economiche_label"] = result[
        "tempo_attivita_economiche_min"
    ].apply(format_minutes)

    result["tempo_fermata_label"] = result[
        "tempo_fermata_min"
    ].apply(format_minutes)
    result["passaggi_label"] = result["passaggi_totali"].apply(
        lambda v: format_count(v, "passaggio", "passaggi")
    )

    result["accessibilita_label"] = result.get(
        "indice_accessibilita",
        pd.Series(np.nan, index=result.index),
    ).apply(format_score)

    result["indice_sociofunzionale_label"] = result.get(
        "indice_sociofunzionale",
        result.get(
            "indice_civico_territoriale",
            pd.Series(np.nan, index=result.index),
        ),
    ).apply(format_score)

    result["nota_metodologica"] = (
        "I tempi pedonali sono calcolati lungo la rete stradale e "
        "sentieristica, tenendo conto della pendenza. Il profilo combina "
        "residenza, morfologia, accessibilità ai servizi e trasporto pubblico."
    )

    return result


def main() -> int:
    args = parse_args()

    if args.clusters != 4:
        raise ValueError(
            "Questa versione pubblica assegna etichette interpretative "
            "a quattro cluster. Usare --clusters 4."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    geojson = load_geojson(args.input)
    validate_geojson_coordinates(geojson)
    df = properties_dataframe(geojson)
    validate_features(df)

    matrix = prepare_matrix(df)

    model = AgglomerativeClustering(
        n_clusters=args.clusters,
        linkage="ward",
    )
    labels = model.fit_predict(matrix)

    df["cluster_v3"] = labels + 1

    silhouette = silhouette_score(matrix, labels)

    profile = cluster_profiles(df, "cluster_v3")
    profile_names = assign_profile_names(profile)

    df["profilo_cluster_v3"] = df["cluster_v3"].map(profile_names)
    df = add_public_fields(df)

    profile["profilo_cluster_v3"] = profile.index.map(profile_names)
    profile["profilo_pubblico"] = profile[
        "profilo_cluster_v3"
    ].map(PUBLIC_LABELS)
    profile["silhouette"] = silhouette
    profile = profile.reset_index()

    # Scrive i nuovi campi nel GeoJSON.
    fields_to_write = [
        "cluster_v3",
        "profilo_cluster_v3",
        "profilo_pubblico",
        "residenti_label",
        "famiglie_label",
        "abitazioni_label",
        "densita_label",
        "pendenza_label",
        "dislivello_label",
        "facilita_territoriale_label",
        "servizi_5min_label",
        "servizi_10min_label",
        "servizi_15min_label",
        "tempo_associazioni_label",
        "tempo_cultura_label",
        "tempo_ristorazione_label",
        "tempo_attivita_economiche_label",
        "tempo_fermata_label",
        "passaggi_label",
        "accessibilita_label",
        "indice_sociofunzionale_label",
        "nota_metodologica",
    ]

    for index, feature in enumerate(geojson["features"]):
        properties = feature.setdefault("properties", {})
        for field in fields_to_write:
            value = df.loc[index, field]
            if isinstance(value, np.generic):
                value = value.item()
            properties[field] = value

    geojson_path = (
        args.output_dir
        / "sezioni_povo_cluster_sociofunzionali_v3.geojson"
    )
    profile_path = (
        args.output_dir
        / "profili_cluster_sociofunzionali_v3.csv"
    )
    assignment_path = (
        args.output_dir
        / "assegnazione_cluster_sezioni_v3.csv"
    )
    metadata_path = (
        args.output_dir
        / "metadati_cluster_sociofunzionali_v3.json"
    )
    popup_path = (
        args.output_dir
        / "popup_umap.txt"
    )

    with geojson_path.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    profile.to_csv(profile_path, index=False)

    assignment_columns = [
        "cluster_v3",
        "profilo_cluster_v3",
        "profilo_pubblico",
        *FEATURES,
    ]
    df[assignment_columns].to_csv(assignment_path, index=False)

    metadata = {
        "input": str(args.input),
        "numero_sezioni": int(len(df)),
        "numero_cluster": int(args.clusters),
        "metodo": "AgglomerativeClustering",
        "linkage": "ward",
        "scaling": "RobustScaler",
        "imputazione": "mediana",
        "winsorization": "1%-99%",
        "silhouette": float(silhouette),
        "variabili_clustering": FEATURES,
        "campo_categorico_umap": "profilo_pubblico",
        "campo_tecnico_cluster": "cluster_v3",
    }

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    popup = """# {profilo_pubblico}

## Popolazione

Residenti: {residenti_label}
Famiglie: {famiglie_label}
Abitazioni: {abitazioni_label}

## Morfologia e percorribilità

Profilo di pendenza: {pendenza_label}
Dislivello interno: {dislivello_label}
Facilità territoriale: {facilita_territoriale_label}

## Servizi raggiungibili a piedi

Entro 5 minuti: {servizi_5min_label}
Entro 10 minuti: {servizi_10min_label}
Entro 15 minuti: {servizi_15min_label}

Cultura e tempo libero: {tempo_cultura_label}
Associazioni e gruppi: {tempo_associazioni_label}
Ristorazione: {tempo_ristorazione_label}
Attività economiche: {tempo_attivita_economiche_label}

## Trasporto pubblico

Fermata più accessibile: {gtfs__fermata_migliore}
Tempo a piedi: {tempo_fermata_label}
Linee alla fermata: {gtfs__linee_urbane_migliore}
Passaggi nella fascia analizzata: {passaggi_label}

## Sintesi

Accessibilità territoriale: {accessibilita_label}
Indice socio-funzionale: {indice_sociofunzionale_label}

---
{nota_metodologica}
"""
    popup_path.write_text(popup, encoding="utf-8")

    print(f"Elaborazione completata: {args.output_dir.resolve()}")
    print(f"Sezioni: {len(df)}")
    print(f"Cluster: {args.clusters}")
    print(f"Silhouette: {silhouette:.3f}")
    print(f"Campo categorico uMap: profilo_pubblico")
    print(f"GeoJSON: {geojson_path.resolve()}")
    print(f"Popup uMap: {popup_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
