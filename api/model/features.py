"""Construye las variables de entrada en el formato que espera el modelo MLflow."""

import json
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


def validate_observed_ranges(input_data: dict, feature_ranges: dict) -> None:
    """Rechaza características numéricas fuera de los límites vistos en barrios.

    Los límites son una protección frente a escenarios extremos, no una
    garantía de que cualquier combinación dentro de ellos sea representativa.
    """
    for column, bounds in feature_ranges.items():
        value = float(input_data[column])
        if value < bounds["min"] or value > bounds["max"]:
            raise ValueError(
                f"'{column}'={value:.4f} está fuera del rango observado "
                f"[{bounds['min']:.4f}, {bounds['max']:.4f}]."
            )


def peer_density_ceiling(
    neighborhood: dict,
    neighborhood_profiles: list[dict],
    minimum_local_peers: int = 3,
    maximum_peers: int = 10,
    price_tolerance: float = 0.25,
) -> float:
    """Obtiene la mayor densidad observada en hasta diez barrios comparables.

    Primero busca barrios de la misma localidad y estrato dentro de una
    diferencia de precio del 25%. Si no encuentra al menos tres, amplía la
    comparación a toda Bogotá manteniendo el mismo estrato. Si todavía hay
    menos de tres, usa los barrios más cercanos en precio dentro de ese
    estrato. El propio barrio forma parte de la comparación cuando aparece
    en la lista de perfiles.
    """
    same_stratum = [
        profile
        for profile in neighborhood_profiles
        if float(profile["estrato_predominante"])
        == float(neighborhood["estrato_predominante"])
    ]
    same_locality = [
        profile
        for profile in same_stratum
        if profile[LOCALITY_COLUMN] == neighborhood[LOCALITY_COLUMN]
    ]
    reference_value = float(neighborhood["v_ref_2025"])
    local_price_peers = [
        profile
        for profile in same_locality
        if abs(float(profile["v_ref_2025"]) - reference_value)
        <= abs(reference_value) * price_tolerance
    ]
    city_price_peers = [
        profile
        for profile in same_stratum
        if abs(float(profile["v_ref_2025"]) - reference_value)
        <= abs(reference_value) * price_tolerance
    ]
    if len(local_price_peers) >= minimum_local_peers:
        peer_pool = local_price_peers
    elif len(city_price_peers) >= minimum_local_peers:
        peer_pool = city_price_peers
    else:
        peer_pool = same_stratum
    if not peer_pool:
        raise ValueError(
            "No hay barrios observados comparables para el estrato seleccionado."
        )

    peer_pool.sort(
        key=lambda profile: abs(
            float(profile["v_ref_2025"]) - reference_value
        )
    )
    closest_peers = peer_pool[:maximum_peers]
    return max(float(profile["densidad_airbnb_km2"]) for profile in closest_peers)


def max_new_listings_for_density(
    neighborhood: dict,
    max_density: float,
    absolute_limit: int,
) -> int:
    """Calcula cuántos anuncios nuevos permite el barrio seleccionado.

    El resultado respeta el máximo global del deslizador y evita que
    ``(anuncios existentes + nuevos) / área`` supere la densidad máxima
    observada entre barrios comparables al seleccionado.
    """
    area = float(neighborhood["area_km2"])
    if area <= 0:
        return 0

    existing_listings = int(neighborhood["num_listings_airbnb"])
    return int(
        max(
            0,
            min(
                absolute_limit,
                max_density * area - existing_listings,
            ),
        )
    )
