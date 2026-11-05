from functools import lru_cache
from pathlib import Path

import pandas as pd
from catboost import CatBoostRegressor


MODEL_PATH = Path(__file__).resolve().parent / "models" / "catboost_v_ref_2026.cbm"
FEATURE_COLUMNS = [
    "localidad",
    "estrato_predominante",
    "v_ref_2025",
    "cagr_15_25",
    "num_estaciones_transmilenio",
    "densidad_airbnb_km2",
]


@lru_cache(maxsize=1)
def load_model():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"No se encontró el modelo CatBoost en {MODEL_PATH}. "
            "Ejecuta `python .\\dashboard\\train_model.py` desde la raíz del proyecto."
        )

    model = CatBoostRegressor()
    model.load_model(str(MODEL_PATH))
    if model.feature_names_ != FEATURE_COLUMNS:
        raise ValueError(
            "Las variables del modelo guardado no coinciden con las esperadas "
            f"por el dashboard: {model.feature_names_}"
        )
    return model


def build_feature_row(record, num_listings_airbnb):
    area = float(record["area_km2"])
    if area <= 0:
        raise ValueError("El área del barrio debe ser mayor que cero para predecir.")

    return pd.DataFrame(
        [
            {
                "localidad": str(record["localidad"]),
                "estrato_predominante": float(record["estrato_predominante"]),
                "v_ref_2025": float(record["v_ref_2025"]),
                "cagr_15_25": float(record["cagr_15_25"]),
                "num_estaciones_transmilenio": float(
                    record["num_estaciones_transmilenio"]
                ),
                "densidad_airbnb_km2": int(num_listings_airbnb) / area,
            }
        ],
        columns=FEATURE_COLUMNS,
    )


def predict_2026(record, num_listings_airbnb):
    feature_row = build_feature_row(record, num_listings_airbnb)
    prediction = float(load_model().predict(feature_row)[0])
    if not pd.notna(prediction):
        raise ValueError("CatBoost devolvió una predicción no válida.")
    return prediction
