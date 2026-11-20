"""Carga el modelo de MLflow y atiende predicciones sin volver a entrenarlo."""

import json
from functools import lru_cache

import numpy as np
import mlflow.pyfunc

from api.model.config import (
    MODEL_MANIFEST_NAME,
    MODEL_URI,
    PACKAGED_MODEL_DIR,
)
from api.model.features import (
    build_feature_metadata,
    build_prediction_features,
    peer_density_ceiling,
    validate_observed_ranges,
)


class ModelConfigurationError(RuntimeError):
    """El modelo descargado tiene campos de entrada distintos a los esperados."""


@lru_cache(maxsize=1)
def load_model_bundle() -> tuple[object, dict]:
    """Carga el modelo descargado o lo obtiene usando la URI de MLflow.

    La copia local se busca primero. Si no está, se usa ``MLFLOW_MODEL_URI``
    y las credenciales de Databricks configuradas en el entorno. El resultado
    se guarda en memoria para no descargarlo o abrirlo en cada solicitud.
    """
    if (PACKAGED_MODEL_DIR / "MLmodel").is_file():
        manifest_path = PACKAGED_MODEL_DIR / MODEL_MANIFEST_NAME
        if not manifest_path.is_file():
            raise FileNotFoundError(
                "El paquete MLflow existe, pero falta "
                f"{MODEL_MANIFEST_NAME}. Ejecuta `python -m api.export_model`."
            )
        with manifest_path.open(encoding="utf-8") as file:
            metadata = json.load(file)
        if "neighborhood_profiles" not in metadata:
            metadata["neighborhood_profiles"] = build_feature_metadata()[
                "neighborhood_profiles"
            ]
        model = mlflow.pyfunc.load_model(str(PACKAGED_MODEL_DIR))
    elif MODEL_URI:
        model = mlflow.pyfunc.load_model(MODEL_URI)
        metadata = build_feature_metadata()
        metadata["model_uri"] = MODEL_URI
        metadata["model_version"] = MODEL_URI
        _validate_model_signature(model, metadata["feature_columns"])
    else:
        raise FileNotFoundError(
            "No se encontró un modelo MLflow empaquetado ni se configuró "
            "MLFLOW_MODEL_URI. Sigue las instrucciones de docs/MLFLOW.md."
        )

    _validate_model_signature(model, metadata["feature_columns"])
    return model, metadata


def predict_2026(input_data: dict) -> float:
    """Comprueba rangos, ordena las variables y pide al modelo el valor 2026."""
    model, metadata = load_model_bundle()
    validate_observed_ranges(input_data, metadata["feature_ranges"])
    max_peer_density = peer_density_ceiling(
        input_data,
        metadata["neighborhood_profiles"],
    )
    if input_data["densidad_airbnb_km2"] > max_peer_density:
        raise ValueError(
            "La densidad Airbnb supera el máximo observado entre barrios "
            f"comparables para el estrato {input_data['estrato_predominante']}: "
            f"{max_peer_density:.4f} propiedades/km²."
        )
    features = build_prediction_features(
        input_data,
        metadata["feature_columns"],
        metadata["locality_categories"],
    )
    if "num_estaciones_transmilenio" in features.columns:
        features["num_estaciones_transmilenio"] = (
            features["num_estaciones_transmilenio"].round().astype("int64")
        )
    prediction = float(np.asarray(model.predict(features)).reshape(-1)[0])
    if not np.isfinite(prediction):
        raise ValueError("XGBoost devolvió una predicción no válida.")
    return prediction


def _validate_model_signature(model, expected_columns: list[str]) -> None:
    """Verifica que los nombres y el orden de entrada coincidan con MLflow."""
    input_schema = model.metadata.get_input_schema()
    if input_schema is None:
        raise ModelConfigurationError(
            "El modelo de MLflow no contiene una firma de entrada; "
            "vuelve a registrarlo con una firma o un ejemplo de entrada."
        )
    actual_columns = input_schema.input_names()
    if actual_columns != expected_columns:
        raise ModelConfigurationError(
            "Las variables de entrada del modelo MLflow no coinciden con "
            f"el contrato local. Esperadas: {expected_columns}; "
            f"recibidas: {actual_columns}."
        )
