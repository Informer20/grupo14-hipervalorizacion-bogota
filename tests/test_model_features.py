"""Comprueba cómo las entradas del dashboard se preparan para XGBoost."""

import pandas as pd
import pytest

from api.model.features import (
    build_prediction_features,
    max_new_listings_for_density,
    peer_density_ceiling,
    validate_observed_ranges,
)


MODEL_COLUMNS = [
    "estrato_predominante",
    "v_ref_2025",
    "cagr_15_25",
    "num_estaciones_transmilenio",
    "densidad_airbnb_km2",
    "localidad_CHAPINERO",
]


def test_prediction_features_match_the_mlflow_input_schema():
    """Forma una fila numérica con las columnas esperadas por MLflow.

    ``input_data`` simula las variables que enviaría el dashboard para un
    barrio. Se elige una localidad conocida y se confirma que el resultado
    conserva el nombre y el orden exactos de las columnas del modelo, además
    de los cinco valores numéricos recibidos.
    """
    input_data = {
        "localidad": "ANTONIO NARINO",
        "estrato_predominante": 6,
        "v_ref_2025": 7_000_000,
        "cagr_15_25": 0.12,
        "num_estaciones_transmilenio": 3,
        "densidad_airbnb_km2": 250,
    }

    features = build_prediction_features(
        input_data,
        MODEL_COLUMNS,
        ["ANTONIO NARINO", "CHAPINERO"],
    )

    assert features.columns.tolist() == MODEL_COLUMNS
    assert features.iloc[0].tolist() == [6, 7_000_000, 0.12, 3, 250, 0]


def test_prediction_features_reject_unknown_locality():
    """Detiene la solicitud si el modelo nunca conoció esa localidad.

    El diccionario simula una solicitud válida salvo por el nombre inventado.
    El error explícito evita generar una fila de entrada potencialmente
    ambigua para el modelo.
    """
    input_data = {
        "localidad": "LOCALIDAD DESCONOCIDA",
        "estrato_predominante": 4,
        "v_ref_2025": 2_000_000,
        "cagr_15_25": 0.1,
        "num_estaciones_transmilenio": 1,
        "densidad_airbnb_km2": 10,
    }

    with pytest.raises(ValueError, match="Localidad no reconocida"):
        build_prediction_features(
            input_data,
            MODEL_COLUMNS,
            ["ANTONIO NARINO", "CHAPINERO"],
        )


def test_prediction_rejects_density_outside_observed_range():
    """Impide predecir una densidad mayor a la observada en los barrios.

    Se entrega un máximo de 250 y una solicitud con 251 propiedades/km²;
    el error debe identificar la variable que excedió el límite.
    """
    input_data = {
        "localidad": "CHAPINERO",
        "estrato_predominante": 6,
        "v_ref_2025": 7_000_000,
        "cagr_15_25": 0.12,
        "num_estaciones_transmilenio": 3,
        "densidad_airbnb_km2": 251,
    }
    observed_ranges = {
        "estrato_predominante": {"min": 1, "max": 6},
        "v_ref_2025": {"min": 500_000, "max": 8_000_000},
        "cagr_15_25": {"min": -0.1, "max": 0.5},
        "num_estaciones_transmilenio": {"min": 0, "max": 10},
        "densidad_airbnb_km2": {"min": 0, "max": 250},
    }

    with pytest.raises(ValueError, match="densidad_airbnb_km2.*fuera del rango"):
        validate_observed_ranges(input_data, observed_ranges)


def test_feature_values_are_numeric_before_calling_mlflow():
    """Comprueba que la fila preparada no conserva columnas de texto.

    Después de transformar la localidad, se verifica que cada columna
    resultante tenga un tipo numérico que pueda recibir el modelo.
    """
    input_data = {
        "localidad": "CHAPINERO",
        "estrato_predominante": 6,
        "v_ref_2025": 7_000_000,
        "cagr_15_25": 0.12,
        "num_estaciones_transmilenio": 3,
        "densidad_airbnb_km2": 250,
    }

    features = build_prediction_features(
        input_data,
        MODEL_COLUMNS,
        ["ANTONIO NARINO", "CHAPINERO"],
    )

    assert all(pd.api.types.is_numeric_dtype(dtype) for dtype in features.dtypes)


def test_feature_metadata_uses_barrio_level_ranges():
    """Confirma que los límites se calculan para localidad y barrio.

    El nivel debe coincidir con la selección del mapa; además, la densidad
    mínima no puede ser negativa ni mayor que su máximo observado.
    """
    from api.model.features import build_feature_metadata

    feature_metadata = build_feature_metadata()

    assert feature_metadata["range_level"] == "barrio-localidad"
    assert feature_metadata["feature_ranges"]["densidad_airbnb_km2"]["min"] >= 0
    assert (
        feature_metadata["feature_ranges"]["densidad_airbnb_km2"]["max"]
        >= feature_metadata["feature_ranges"]["densidad_airbnb_km2"]["min"]
    )


def test_slider_limit_accounts_for_existing_listings_and_area():
    """Limita los anuncios nuevos usando área, anuncios actuales y tope global.

    Para un barrio de 2 km² con 100 anuncios, una densidad máxima de 60
    permite 20 anuncios más; una densidad de 40 no permite añadir ninguno.
    El último caso comprueba que también se respeta el máximo general 50.
    """
    neighborhood = {
        "area_km2": 2,
        "num_listings_airbnb": 100,
    }

    assert max_new_listings_for_density(neighborhood, 60, 1000) == 20
    assert max_new_listings_for_density(neighborhood, 40, 1000) == 0
    assert max_new_listings_for_density(neighborhood, 1000, 50) == 50


def test_peer_density_ceiling_uses_stratum_and_similar_reference_values():
    """Limita la densidad a barrios con estrato y precios de referencia similares.

    Hay dos barrios comparables cercanos en la misma localidad y uno cercano
    en otra localidad, por lo que se amplía al grupo de la ciudad del mismo
    estrato. Los perfiles de precio muy distinto y de otro estrato no pueden
    subir el máximo permitido.
    """
    selected = {
        "localidad": "LOCALIDAD A",
        "estrato_predominante": 1,
        "v_ref_2025": 100,
    }
    profiles = [
        {
            "localidad": "LOCALIDAD A",
            "barrio": "BARRIO SELECCIONADO",
            "estrato_predominante": 1,
            "v_ref_2025": 100,
            "densidad_airbnb_km2": 5,
        },
        {
            "localidad": "LOCALIDAD A",
            "barrio": "BARRIO CERCANO",
            "estrato_predominante": 1,
            "v_ref_2025": 110,
            "densidad_airbnb_km2": 8,
        },
        {
            "localidad": "LOCALIDAD B",
            "barrio": "BARRIO SIMILAR",
            "estrato_predominante": 1,
            "v_ref_2025": 105,
            "densidad_airbnb_km2": 10,
        },
        {
            "localidad": "LOCALIDAD B",
            "barrio": "BARRIO DE OTRO PRECIO",
            "estrato_predominante": 1,
            "v_ref_2025": 500,
            "densidad_airbnb_km2": 1000,
        },
        {
            "localidad": "LOCALIDAD A",
            "barrio": "BARRIO DE OTRO ESTRATO",
            "estrato_predominante": 6,
            "v_ref_2025": 100,
            "densidad_airbnb_km2": 5000,
        },
    ]

    assert peer_density_ceiling(selected, profiles) == 10


def test_peer_density_ceiling_prefers_local_comparable_neighborhoods():
    """Prioriza los barrios comparables de la misma localidad cuando hay tres."""
    selected = {
        "localidad": "LOCALIDAD A",
        "estrato_predominante": 1,
        "v_ref_2025": 100,
    }
    profiles = [
        {
            "localidad": "LOCALIDAD A",
            "barrio": "SELECCIONADO",
            "estrato_predominante": 1,
            "v_ref_2025": 100,
            "densidad_airbnb_km2": 5,
        },
        {
            "localidad": "LOCALIDAD A",
            "barrio": "PAR",
            "estrato_predominante": 1,
            "v_ref_2025": 110,
            "densidad_airbnb_km2": 8,
        },
        {
            "localidad": "LOCALIDAD A",
            "barrio": "PAR 2",
            "estrato_predominante": 1,
            "v_ref_2025": 95,
            "densidad_airbnb_km2": 10,
        },
        {
            "localidad": "LOCALIDAD B",
            "barrio": "OTRO BARRIO",
            "estrato_predominante": 1,
            "v_ref_2025": 101,
            "densidad_airbnb_km2": 40,
        },
    ]

    assert peer_density_ceiling(selected, profiles) == 10
