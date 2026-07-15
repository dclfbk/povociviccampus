#!/usr/bin/env python3
"""
07_indice_sociofunzionale_v2.py

Aggiorna gli indicatori territoriali delle sezioni di Povo combinando:

1. dati demografici e morfologici delle sezioni;
2. accessibilità pedonale ai servizi;
3. accessibilità al trasporto pubblico prodotta dallo script 06 v4.

Lo script genera un GeoPackage, un GeoJSON e un CSV. Non esegue il
clustering: la classificazione in quattro profili è demandata allo script 08.

Esempio:

python 07_indice_sociofunzionale_v2.py \
  --sections "../data/sezioni_povo_istat_dtm.gpkg" \
  --sections-layer "sezioni_istat_dtm" \
  --services "output_accessibilita_servizi/accessibilita_servizi_povo.gpkg" \
  --services-layer "sezioni_accessibilita" \
  --gtfs "output_accessibilita_gtfs_v4/accessibilita_gtfs_multifeed_povo_v4.gpkg" \
  --gtfs-layer "sezioni_accessibilita_gtfs" \
  --out-dir "output_indice_sociofunzionale_v2"
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd


def norm_name(value: object) -> str:
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    lookup = {norm_name(column): column for column in columns}
    for candidate in candidates:
        found = lookup.get(norm_name(candidate))
        if found is not None:
            return found
    return None


def read_layer(path: Path, layer: str | None) -> gpd.GeoDataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File non trovato: {path}")
    if layer:
        return gpd.read_file(path, layer=layer)
    return gpd.read_file(path)


def choose_join_key(*frames: gpd.GeoDataFrame) -> tuple[str, list[str]]:
    candidates = [
        "SEZ21_ID",
        "sez21_id",
        "sezione_id",
        "section_id",
        "id_sezione",
        "id",
    ]

    for candidate in candidates:
        actual = [first_existing(frame.columns, [candidate]) for frame in frames]
        if all(value is not None for value in actual):
            return candidate, [str(value) for value in actual]

    common_normalized = None
    normalized_maps = []
    for frame in frames:
        mapping = {
            norm_name(column): column
            for column in frame.columns
            if column != "geometry"
        }
        normalized_maps.append(mapping)
        common_normalized = (
            set(mapping)
            if common_normalized is None
            else common_normalized & set(mapping)
        )

    if not common_normalized:
        raise ValueError(
            "Nessuna chiave comune trovata. "
            "Aggiungere alle tre fonti un identificatore univoco della sezione."
        )

    normalized_key = sorted(common_normalized)[0]
    return normalized_key, [
        str(mapping[normalized_key]) for mapping in normalized_maps
    ]


def numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    text = series.astype(str).str.strip()
    # Gestisce sia 1.234,5 sia 1234.5.
    italian_mask = text.str.contains(",", regex=False)
    text.loc[italian_mask] = (
        text.loc[italian_mask]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(text, errors="coerce")


def percentile_score(
    series: pd.Series,
    higher_is_better: bool = True,
    missing_value: float = 50.0,
) -> pd.Series:
    values = numeric(series).replace([np.inf, -np.inf], np.nan)

    if values.notna().sum() <= 1 or values.nunique(dropna=True) <= 1:
        return pd.Series(missing_value, index=values.index, dtype=float)

    score = values.rank(pct=True, method="average") * 100.0
    if not higher_is_better:
        score = 100.0 - score

    return score.fillna(missing_value)


def mean_available(parts: list[pd.Series], index: pd.Index) -> pd.Series:
    if not parts:
        return pd.Series(50.0, index=index, dtype=float)
    return pd.concat(parts, axis=1).mean(axis=1, skipna=True).fillna(50.0)


def classify_absolute(score: pd.Series) -> pd.Series:
    """
    Classificazione leggibile e confrontabile nel tempo.

    Non usa quartili del campione: le soglie restano costanti quando
    vengono aggiornati dati, servizi o trasporti.
    """
    return pd.cut(
        score.clip(0, 100),
        bins=[-0.001, 25, 50, 75, 100],
        labels=["molto_bassa", "bassa", "media", "alta"],
        include_lowest=True,
    ).astype(str)


def prefixed_table(
    frame: gpd.GeoDataFrame,
    source_key: str,
    target_key: str,
    prefix: str,
) -> pd.DataFrame:
    table = pd.DataFrame(frame.drop(columns="geometry")).copy()
    table[source_key] = table[source_key].astype(str)
    table = table.rename(columns={source_key: target_key})
    return table.rename(
        columns={
            column: f"{prefix}{column}"
            for column in table.columns
            if column != target_key
        }
    )


def select_column(
    frame: pd.DataFrame,
    candidates: list[str],
    required: bool = False,
) -> str | None:
    result = first_existing(frame.columns, candidates)
    if required and result is None:
        raise ValueError(
            "Nessuna delle colonne attese è presente:\n- "
            + "\n- ".join(candidates)
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calcola gli indici territoriali aggiornati per Povo."
    )
    parser.add_argument("--sections", required=True, type=Path)
    parser.add_argument("--sections-layer", default="sezioni_istat_dtm")
    parser.add_argument("--services", required=True, type=Path)
    parser.add_argument("--services-layer", default="sezioni_accessibilita")
    parser.add_argument("--gtfs", required=True, type=Path)
    parser.add_argument("--gtfs-layer", default="sezioni_accessibilita_gtfs")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("output_indice_sociofunzionale_v2"),
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    sections = read_layer(args.sections, args.sections_layer)
    services = read_layer(args.services, args.services_layer)
    gtfs = read_layer(args.gtfs, args.gtfs_layer)

    key_name, actual_keys = choose_join_key(sections, services, gtfs)
    key_sections, key_services, key_gtfs = actual_keys

    sections[key_sections] = sections[key_sections].astype(str)

    services_table = prefixed_table(
        services,
        source_key=key_services,
        target_key=key_sections,
        prefix="srv__",
    )
    gtfs_table = prefixed_table(
        gtfs,
        source_key=key_gtfs,
        target_key=key_sections,
        prefix="gtfs__",
    )

    if services_table[key_sections].duplicated().any():
        raise ValueError("Il layer dei servizi contiene più righe per la stessa sezione.")
    if gtfs_table[key_sections].duplicated().any():
        raise ValueError("Il layer GTFS contiene più righe per la stessa sezione.")

    gdf = sections.merge(
        services_table,
        on=key_sections,
        how="left",
        validate="1:1",
    )
    gdf = gdf.merge(
        gtfs_table,
        on=key_sections,
        how="left",
        validate="1:1",
    )

    fields_used: dict[str, object] = {
        "join_key": {
            "normalized_name": key_name,
            "sections": key_sections,
            "services": key_services,
            "gtfs": key_gtfs,
        }
    }

    # ------------------------------------------------------------------
    # 1. RESIDENZA E MORFOLOGIA
    # ------------------------------------------------------------------

    population_col = select_column(
        gdf,
        [
            "pop_riferimento",
            "popolazione_rif",
            "popolazione",
            "pop21",
            "residenti",
            "population",
        ],
    )
    families_col = select_column(
        gdf,
        ["fam_riferimento", "famiglie", "fam21", "households"],
    )
    homes_col = select_column(
        gdf,
        ["abi_riferimento", "abitazioni", "abi21", "dwellings"],
    )
    area_col = select_column(
        gdf,
        ["area_m2", "superficie_m2", "area"],
    )
    slope_col = select_column(
        gdf,
        [
            "pendenza_media_gradi",
            "slope_deg_mean",
            "pendenza_gradi_mean",
            "slope_mean",
        ],
    )
    relief_col = select_column(
        gdf,
        [
            "dislivello_sezione_m",
            "dislivello_m",
            "quota_range",
            "elev_range",
            "dtm_range",
            "elevation_range",
        ],
    )

    gdf["popolazione_rif"] = (
        numeric(gdf[population_col]).fillna(0)
        if population_col
        else 0.0
    )
    gdf["famiglie_rif"] = (
        numeric(gdf[families_col]).fillna(0)
        if families_col
        else np.nan
    )
    gdf["abitazioni_rif"] = (
        numeric(gdf[homes_col]).fillna(0)
        if homes_col
        else np.nan
    )

    # Densità: usa il campo esistente solo se plausibile; altrimenti la ricalcola.
    density_col = select_column(
        gdf,
        [
            "densita_pop_rif",
            "densita_pop_km2",
            "dens_pop_km2",
            "densita_abitativa",
            "population_density",
        ],
    )

    projected = gdf.to_crs(25832)
    geometry_area_m2 = projected.geometry.area
    valid_geometry_area = geometry_area_m2.where(geometry_area_m2 >= 100)

    if area_col:
        source_area = numeric(gdf[area_col])
        # Alcuni file precedenti contenevano aree palesemente anomale.
        source_area = source_area.where(source_area >= 100)
        area_m2 = source_area.fillna(valid_geometry_area)
    else:
        area_m2 = valid_geometry_area

    gdf["area_calcolo_m2"] = area_m2
    recalculated_density = (
        gdf["popolazione_rif"]
        / (gdf["area_calcolo_m2"] / 1_000_000.0)
    ).replace([np.inf, -np.inf], np.nan)

    if density_col:
        supplied_density = numeric(gdf[density_col])
        # Valori oltre 100.000 ab/km² sono trattati come sospetti.
        supplied_density = supplied_density.where(
            supplied_density.between(0, 100_000)
        )
        gdf["densita_pop_rif"] = supplied_density.fillna(recalculated_density)
    else:
        gdf["densita_pop_rif"] = recalculated_density

    gdf["pendenza_media_gradi"] = (
        numeric(gdf[slope_col]) if slope_col else np.nan
    )
    gdf["dislivello_sezione_m"] = (
        numeric(gdf[relief_col]) if relief_col else np.nan
    )

    fields_used["residenza_morfologia"] = {
        "population": population_col,
        "families": families_col,
        "homes": homes_col,
        "area": area_col,
        "density": density_col,
        "slope": slope_col,
        "relief": relief_col,
    }

    # ------------------------------------------------------------------
    # 2. ACCESSIBILITÀ AI SERVIZI
    # ------------------------------------------------------------------

    service_5_col = select_column(
        gdf,
        [
            "srv__servizi_5min",
            "srv__servizi_5_min",
            "srv__n_servizi_5m",
            "srv__n_servizi_5_min",
        ],
        required=True,
    )
    service_10_col = select_column(
        gdf,
        [
            "srv__servizi_10min",
            "srv__servizi_10_min",
            "srv__n_servizi_10m",
            "srv__n_servizi_10_min",
        ],
        required=True,
    )
    service_15_col = select_column(
        gdf,
        [
            "srv__servizi_15min",
            "srv__servizi_15_min",
            "srv__n_servizi_15m",
            "srv__n_servizi_15_min",
        ],
        required=True,
    )

    category_time_candidates = {
        "tempo_associazioni_min": [
            "srv__t_associazioni_e_gruppi_min",
            "srv__tempo_associazioni_e_gruppi_min",
        ],
        "tempo_cultura_min": [
            "srv__t_cultura_e_tempo_libero_min",
            "srv__tempo_cultura_e_tempo_libero_min",
        ],
        "tempo_ristorazione_min": [
            "srv__t_ristorazione_e_agriturismi_min",
            "srv__tempo_ristorazione_e_agriturismi_min",
        ],
        "tempo_attivita_economiche_min": [
            "srv__t_servizi_e_attivit_economiche_min",
            "srv__tempo_servizi_e_attivita_economiche_min",
        ],
    }

    gdf["servizi_5_min"] = numeric(gdf[service_5_col]).fillna(0)
    gdf["servizi_10_min"] = numeric(gdf[service_10_col]).fillna(0)
    gdf["servizi_15_min"] = numeric(gdf[service_15_col]).fillna(0)

    time_fields_used = {}
    time_series = []
    for output_column, candidates in category_time_candidates.items():
        column = select_column(gdf, candidates)
        time_fields_used[output_column] = column
        gdf[output_column] = numeric(gdf[column]) if column else np.nan
        if column:
            time_series.append(gdf[output_column])

    if time_series:
        gdf["tempo_servizio_min"] = pd.concat(
            time_series, axis=1
        ).min(axis=1, skipna=True)
    else:
        gdf["tempo_servizio_min"] = np.nan

    fields_used["servizi"] = {
        "services_5": service_5_col,
        "services_10": service_10_col,
        "services_15": service_15_col,
        "category_times": time_fields_used,
    }

    # ------------------------------------------------------------------
    # 3. TRASPORTO PUBBLICO — OUTPUT DELLO SCRIPT 06 V4
    # ------------------------------------------------------------------

    transit_time_col = select_column(
        gdf,
        [
            "gtfs__tempo_fermata_qualsiasi_min",
            "gtfs__tempo_fermata_min",
        ],
        required=True,
    )
    passages_col = select_column(
        gdf,
        [
            "gtfs__passaggi_totali_fermata",
            "gtfs__passaggi_totali",
            "gtfs__numero_passaggi",
            "gtfs__corse_totali",
        ],
        required=True,
    )
    relation_col = select_column(
        gdf,
        ["gtfs__tipo_relazione_confine"],
    )
    internal_stop_col = select_column(
        gdf,
        ["gtfs__fermata_interna_migliore"],
    )
    urban_lines_inside_col = select_column(
        gdf,
        ["gtfs__linee_urbane_nella_circoscrizione"],
    )
    extra_lines_inside_col = select_column(
        gdf,
        ["gtfs__linee_extraurbane_nella_circoscrizione"],
    )

    gdf["tempo_fermata_min"] = numeric(gdf[transit_time_col])
    gdf["passaggi_totali"] = numeric(gdf[passages_col])

    # Copie dal nome pubblico stabile: utili nei passaggi successivi.
    if relation_col:
        gdf["relazione_fermata_confine"] = gdf[relation_col].fillna("")
    if internal_stop_col:
        gdf["fermata_migliore_interna"] = gdf[internal_stop_col]
    if urban_lines_inside_col:
        gdf["linee_urbane_circoscrizione"] = gdf[urban_lines_inside_col]
    if extra_lines_inside_col:
        gdf["linee_extraurbane_circoscrizione"] = gdf[
            extra_lines_inside_col
        ]

    fields_used["trasporto_pubblico"] = {
        "time": transit_time_col,
        "passages": passages_col,
        "boundary_relation": relation_col,
        "best_stop_internal": internal_stop_col,
        "urban_lines_inside": urban_lines_inside_col,
        "extraurban_lines_inside": extra_lines_inside_col,
    }

    # ------------------------------------------------------------------
    # 4. PUNTEGGI 0-100
    # ------------------------------------------------------------------

    residence_parts = [
        percentile_score(gdf["popolazione_rif"], higher_is_better=True),
        percentile_score(gdf["densita_pop_rif"], higher_is_better=True),
    ]
    if gdf["famiglie_rif"].notna().any():
        residence_parts.append(
            percentile_score(gdf["famiglie_rif"], higher_is_better=True)
        )
    gdf["score_residenza"] = mean_available(
        residence_parts,
        index=gdf.index,
    )

    terrain_parts = []
    if gdf["pendenza_media_gradi"].notna().any():
        terrain_parts.append(
            percentile_score(
                gdf["pendenza_media_gradi"],
                higher_is_better=False,
            )
        )
    if gdf["dislivello_sezione_m"].notna().any():
        terrain_parts.append(
            percentile_score(
                gdf["dislivello_sezione_m"],
                higher_is_better=False,
            )
        )
    gdf["score_facilita_territoriale"] = mean_available(
        terrain_parts,
        index=gdf.index,
    )

    service_parts = [
        percentile_score(gdf["servizi_5_min"], higher_is_better=True),
        percentile_score(gdf["servizi_10_min"], higher_is_better=True),
        percentile_score(gdf["servizi_15_min"], higher_is_better=True),
    ]
    for column in category_time_candidates:
        if gdf[column].notna().any():
            service_parts.append(
                percentile_score(
                    gdf[column],
                    higher_is_better=False,
                )
            )
    gdf["score_servizi"] = mean_available(
        service_parts,
        index=gdf.index,
    )

    transit_parts = [
        percentile_score(
            gdf["tempo_fermata_min"],
            higher_is_better=False,
        ),
        percentile_score(
            gdf["passaggi_totali"],
            higher_is_better=True,
        ),
    ]

    # Una fermata interna è un'informazione descrittiva importante, ma non
    # viene trasformata in un premio dominante: il tempo pedonale resta centrale.
    if internal_stop_col:
        internal_numeric = (
            gdf[internal_stop_col]
            .astype(str)
            .str.lower()
            .map({"true": 100.0, "false": 0.0, "1": 100.0, "0": 0.0})
        )
        if internal_numeric.notna().any():
            transit_parts.append(internal_numeric.fillna(50.0))

    gdf["score_trasporto_pubblico"] = mean_available(
        transit_parts,
        index=gdf.index,
    )

    # ------------------------------------------------------------------
    # 5. INDICI COMPOSITI
    # ------------------------------------------------------------------

    gdf["indice_accessibilita"] = (
        0.40 * gdf["score_servizi"]
        + 0.35 * gdf["score_trasporto_pubblico"]
        + 0.25 * gdf["score_facilita_territoriale"]
    )

    gdf["indice_sociofunzionale"] = (
        0.65 * gdf["indice_accessibilita"]
        + 0.35 * gdf["score_residenza"]
    )

    # Alias mantenuto per compatibilità con i file precedenti.
    gdf["indice_civico_territoriale"] = gdf["indice_sociofunzionale"]

    for column in [
        "score_residenza",
        "score_facilita_territoriale",
        "score_servizi",
        "score_trasporto_pubblico",
        "indice_accessibilita",
        "indice_sociofunzionale",
        "indice_civico_territoriale",
    ]:
        gdf[column] = gdf[column].clip(0, 100).round(1)

    gdf["classe_accessibilita"] = classify_absolute(
        gdf["indice_accessibilita"]
    )
    gdf["classe_sociofunzionale"] = classify_absolute(
        gdf["indice_sociofunzionale"]
    )
    gdf["classe_civico_territoriale"] = gdf[
        "classe_sociofunzionale"
    ]

    # ------------------------------------------------------------------
    # 6. OUTPUT
    # ------------------------------------------------------------------

    gpkg_path = args.out_dir / "indice_sociofunzionale_povo_v2.gpkg"
    geojson_path = args.out_dir / "indice_sociofunzionale_povo_v2.geojson"
    csv_path = args.out_dir / "indice_sociofunzionale_povo_v2.csv"
    summary_path = args.out_dir / "sintesi_indici_v2.csv"
    metadata_path = args.out_dir / "metadati_indice_v2.json"

    if gpkg_path.exists():
        gpkg_path.unlink()

    gdf.to_file(
        gpkg_path,
        layer="sezioni_indice_sociofunzionale",
        driver="GPKG",
    )
    gdf.to_file(geojson_path, driver="GeoJSON")
    pd.DataFrame(gdf.drop(columns="geometry")).to_csv(
        csv_path,
        index=False,
    )

    summary = pd.DataFrame(
        {
            "indicatore": [
                "numero_sezioni",
                "popolazione_totale",
                "indice_accessibilita_medio",
                "indice_sociofunzionale_medio",
                "sezioni_accessibilita_alta",
                "sezioni_sociofunzionale_alta",
            ],
            "valore": [
                int(len(gdf)),
                float(gdf["popolazione_rif"].sum()),
                round(float(gdf["indice_accessibilita"].mean()), 1),
                round(float(gdf["indice_sociofunzionale"].mean()), 1),
                int((gdf["classe_accessibilita"] == "alta").sum()),
                int((gdf["classe_sociofunzionale"] == "alta").sum()),
            ],
        }
    )
    summary.to_csv(summary_path, index=False)

    metadata = {
        "input": {
            "sections": str(args.sections),
            "services": str(args.services),
            "gtfs_v4": str(args.gtfs),
        },
        "fields_used": fields_used,
        "weights": {
            "indice_accessibilita": {
                "servizi": 0.40,
                "trasporto_pubblico": 0.35,
                "facilita_territoriale": 0.25,
            },
            "indice_sociofunzionale": {
                "accessibilita": 0.65,
                "residenza": 0.35,
            },
        },
        "classification": {
            "molto_bassa": "0-25",
            "bassa": "25-50",
            "media": "50-75",
            "alta": "75-100",
        },
        "notes": [
            "I punteggi sono normalizzati su scala 0-100.",
            "I tempi pedonali del GTFS derivano dal grafo corretto per pendenza.",
            "Le linee GTFS sono selezionate dallo script 06 v4 in rapporto al confine.",
            "Il clustering socio-funzionale viene eseguito separatamente dallo script 08.",
            "L'indice non misura direttamente intensità d'uso, partecipazione o city users.",
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Elaborazione completata: {args.out_dir.resolve()}")
    print(f"Sezioni analizzate: {len(gdf)}")
    print(f"Indice medio di accessibilità: {gdf['indice_accessibilita'].mean():.1f}")
    print(f"Indice socio-funzionale medio: {gdf['indice_sociofunzionale'].mean():.1f}")
    print(f"GeoJSON: {geojson_path.resolve()}")
    print(f"GeoPackage: {gpkg_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
