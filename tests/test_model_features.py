"""Comprueba cómo las entradas del dashboard se preparan para XGBoost."""

import pandas as pd
import pytest

from api.model.features import (
    build_prediction_features,
    comparable_new_listings_limit,
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


def test_comparable_new_listings_limit_always_allows_five_and_rounds_up():
    """Calcula un máximo total basado en barrios similares y redondea hacia arriba.

    Si el máximo observado en el grupo comparable es 40, el 25 por ciento de
    expansión permite como máximo 50 alojamientos totales. Para un barrio que
    ya tiene 45, quedarían 5 nuevos. Si ya tiene 51, conserva al menos 5
    nuevos para que el deslizador nunca se bloquee completamente.
    """
    profiles = [
        {
            "estrato_predominante": 3,
            "v_ref_2025": 100,
            "num_listings_airbnb": 40,
        },
        {
            "estrato_predominante": 3,
            "v_ref_2025": 110,
            "num_listings_airbnb": 30,
        },
    ]

    selected = {
        "estrato_predominante": 3,
        "v_ref_2025": 105,
        "num_listings_airbnb": 45,
    }
    assert comparable_new_listings_limit(selected, profiles) == 5

    selected["num_listings_airbnb"] = 51
    assert comparable_new_listings_limit(selected, profiles) == 5
