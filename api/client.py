"""Envía a la API los datos del barrio y del escenario elegidos en el dashboard."""

import math
import os

import requests


DEFAULT_PREDICTION_API_URL = "http://127.0.0.1:8001/api/v1/predict"
PREDICTION_API_TIMEOUT_SECONDS = 60


class PredictionAPIError(RuntimeError):
    """Error que se muestra si la API no devuelve una predicción válida."""


def predict_neighborhood(record, new_listings):
    """Solicita el valor 2026 usando características del barrio seleccionado.

    ``record`` contiene el área, los anuncios actuales y las demás métricas
    del barrio. ``new_listings`` es el número del deslizador. La función suma
    anuncios actuales y nuevos, divide por el área, envía los datos a FastAPI
    y devuelve el número predicho. Si la API falla o responde con datos
    inesperados, lanza ``PredictionAPIError`` para que el dashboard lo informe.
    """
    area = float(record["area_km2"])
    if area <= 0:
        raise PredictionAPIError(
            "El área del barrio debe ser mayor que cero para predecir."
        )

    total_listings = int(record["num_listings_airbnb"]) + int(new_listings)
    payload = {
        "localidad": str(record["localidad"]),
        "estrato_predominante": float(record["estrato_predominante"]),
        "v_ref_2025": float(record["v_ref_2025"]),
        "cagr_15_25": float(record["cagr_15_25"]),
        "num_estaciones_transmilenio": float(
            record["num_estaciones_transmilenio"]
        ),
        "densidad_airbnb_km2": total_listings / area,
    }
    endpoint = os.getenv(
        "URBAN_AI_API_URL",
        DEFAULT_PREDICTION_API_URL,
    )

    try:
        response = requests.post(
            endpoint,
            json=payload,
            timeout=PREDICTION_API_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise PredictionAPIError(
            f"No fue posible conectar con la API de predicción: {error}"
        ) from error

    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except requests.exceptions.JSONDecodeError:
            detail = response.text
        raise PredictionAPIError(
            f"La API respondió con HTTP {response.status_code}: {detail}"
        )

    try:
        prediction = float(response.json()["prediction"])
    except (requests.exceptions.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise PredictionAPIError(
            "La API respondió con un formato de predicción no válido."
        ) from error

    if not math.isfinite(prediction):
        raise PredictionAPIError("La API devolvió una predicción no válida.")
    return prediction
