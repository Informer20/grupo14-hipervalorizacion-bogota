"""Construye las variables de entrada en el formato que espera el modelo MLflow."""

import json
import math
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import pandas as pd

from api.model.config import (
    DATA_PATH,
    INPUT_COLUMNS,
    LOCALITY_COLUMN,
    MODEL_MANIFEST_NAME,
    TARGET_COLUMN,
)


@lru_cache(maxsize=1)
def build_feature_metadata(data_path: Path = DATA_PATH) -> dict:
    """Calcula variables válidas, categorías y límites a partir del GeoPackage.

    Primero agrupa los sectores por localidad y barrio para que los límites
    coincidan con el nivel de los datos que envía el dashboard. También guarda
    el orden de columnas que debe tener la fila enviada al modelo.
    """
    geodata = gpd.read_file(
        data_path,
        layer="matriz_barrios_unificada",
    )
    required_columns = set(
        INPUT_COLUMNS
        + [
            TARGET_COLUMN,
            "barrio",
            "area_km2",
            "num_listings_airbnb",
        ]
    )
    missing_columns = required_columns - set(geodata.columns)
    if missing_columns:
        raise ValueError(
            f"Faltan columnas para validar las entradas del modelo: "
            f"{sorted(missing_columns)}"
        )

    observed = geodata.loc[
        geodata[TARGET_COLUMN].notna(),
        INPUT_COLUMNS
        + [
            TARGET_COLUMN,
            "barrio",
            "area_km2",
            "num_listings_airbnb",
        ],
    ].copy()
    if observed[INPUT_COLUMNS].isna().any().any():
        raise ValueError("Hay valores faltantes en las variables observadas.")

    categories = sorted(observed[LOCALITY_COLUMN].astype(str).unique().tolist())
    feature_columns = encode_model_features(observed).columns.tolist()
    neighborhood_rows = []
    for (locality, _), group in observed.groupby(
        [LOCALITY_COLUMN, "barrio"],
        sort=True,
    ):
        neighborhood = group["barrio"].iloc[0]
        area = group["area_km2"].fillna(0).sum()
        weights = group["area_km2"].fillna(0)
        total_listings = group["num_listings_airbnb"].fillna(0).sum()
        row = {
            LOCALITY_COLUMN: locality,
            "barrio": neighborhood,
            "estrato_predominante": group["estrato_predominante"].mode().iloc[0],
            "densidad_airbnb_km2": total_listings / area if area else 0,
            "num_listings_airbnb": total_listings,
            "area_km2": area,
            "v_ref_2025": (
                (group["v_ref_2025"].fillna(0) * weights).sum() / area
                if area
                else group["v_ref_2025"].mean()
            ),
            "cagr_15_25": (
                (group["cagr_15_25"].fillna(0) * weights).sum() / area
                if area
                else group["cagr_15_25"].mean()
            ),
            "num_estaciones_transmilenio": (
                group["num_estaciones_transmilenio"].fillna(0).sum()
            ),
        }
        neighborhood_rows.append(row)

    neighborhood_data = pd.DataFrame(neighborhood_rows)
    feature_ranges = {
        column: {
            "min": float(neighborhood_data[column].min()),
            "max": float(neighborhood_data[column].max()),
        }
        for column in INPUT_COLUMNS
        if column != LOCALITY_COLUMN
    }
    return {
        "target": TARGET_COLUMN,
        "input_columns": INPUT_COLUMNS,
        "feature_columns": feature_columns,
        "locality_categories": categories,
        "feature_ranges": feature_ranges,
        "observed_rows": int(len(observed)),
        "range_level": "barrio-localidad",
        "neighborhood_profiles": neighborhood_data[
            [
                LOCALITY_COLUMN,
                "barrio",
                "estrato_predominante",
                "v_ref_2025",
                "densidad_airbnb_km2",
                "num_listings_airbnb",
                "area_km2",
            ]
        ].to_dict(orient="records"),
    }


def encode_model_features(data: pd.DataFrame) -> pd.DataFrame:
    """Repite la codificación de localidad 0/1 usada al preparar XGBoost.

    Se elimina la primera localidad en orden alfabético, igual que con
    ``get_dummies(drop_first=True)`` en el notebook de entrenamiento.
    """
    features = data[INPUT_COLUMNS].copy()
    features[LOCALITY_COLUMN] = features[LOCALITY_COLUMN].astype(str)
    return pd.get_dummies(
        features,
        columns=[LOCALITY_COLUMN],
        drop_first=True,
        dtype=int,
    )


def write_model_manifest(
    model_dir: Path,
    feature_metadata: dict,
    model_uri: str,
) -> Path:
    """Guarda junto al modelo su URI, sus columnas y rangos de entrada.

    El manifiesto permite a la API reconstruir el mismo formato de variables
    sin volver a entrenar el modelo.
    """
    manifest_path = model_dir / MODEL_MANIFEST_NAME
    manifest = {
        **feature_metadata,
        "model_uri": model_uri,
        "model_version": model_uri,
    }
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
    return manifest_path


def build_prediction_features(
    input_data: dict,
    feature_columns: list[str],
    locality_categories: list[str],
) -> pd.DataFrame:
    """Convierte la solicitud de la API en una fila numérica para XGBoost.

    Usa las categorías de localidad y el orden de columnas guardados al
    preparar el modelo. Si la localidad no se conoció durante el entrenamiento,
    falla antes de enviar datos ambiguos al modelo.
    """
    locality = str(input_data[LOCALITY_COLUMN])
    if locality not in locality_categories:
        raise ValueError(f"Localidad no reconocida por el modelo: {locality}")

    row = pd.DataFrame(
        [
            {
                column: input_data[column]
                for column in INPUT_COLUMNS
                if column != LOCALITY_COLUMN
            }
        ],
    )
    for category in locality_categories[1:]:
        row[f"{LOCALITY_COLUMN}_{category}"] = int(locality == category)
    return row.reindex(columns=feature_columns, fill_value=0)


def comparable_new_listings_limit(
    neighborhood: dict,
    neighborhood_profiles: list[dict],
    absolute_limit: int = 1000,
    price_tolerance: float = 0.25,
) -> int:
    """Calcula el máximo de anuncios nuevos permitidos en el barrio.

    Busca barrios del mismo estrato cuyo valor de referencia 2025 esté dentro
    de una diferencia del 25 por ciento. Toma el máximo número de anuncios
    Airbnb observado en ese grupo, lo aumenta 25 por ciento y redondea hacia
    arriba. Si el barrio seleccionado ya tiene más anuncios, conserva al menos
    cinco nuevas disponibles para que el usuario siempre pueda simular.
    """
    reference_value = float(neighborhood["v_ref_2025"])
    stratum = float(neighborhood["estrato_predominante"])

    peers = [
        profile
        for profile in neighborhood_profiles
        if float(profile["estrato_predominante"]) == stratum
        and abs(float(profile["v_ref_2025"]) - reference_value)
        <= abs(reference_value) * price_tolerance
    ]
    if not peers:
        peers = [
            profile
            for profile in neighborhood_profiles
            if float(profile["estrato_predominante"]) == stratum
        ]
    if not peers:
        return 5

    max_observed_listings = max(
        float(profile["num_listings_airbnb"]) for profile in peers
    )
    maximum_total_listings = math.ceil(max_observed_listings * 1.25)
    allowed_new_listings = maximum_total_listings - int(
        neighborhood["num_listings_airbnb"]
    )
    return int(max(5, min(absolute_limit, allowed_new_listings)))
