"""Rutas que permiten comprobar la API y pedir una predicción al modelo."""

from fastapi import FastAPI, HTTPException

from api.app.schemas import HealthResponse, PredictionRequest, PredictionResponse
from api.model.predictor import (
    ModelConfigurationError,
    load_model_bundle,
    predict_2026,
)


app = FastAPI(
    title="Urban AI Prediction API",
    description="Estima el valor de referencia del suelo para 2026 en Bogotá.",
    version="1.0.0",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Comprueba que se puede cargar el modelo y devuelve su identificador.

    El resultado 200 significa que API y modelo están listos; 503 indica que
    no se encontró el paquete o que su configuración no sirve para este proyecto.
    """
    try:
        _, metadata = load_model_bundle()
    except (FileNotFoundError, ModelConfigurationError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return HealthResponse(status="ready", model_version=metadata["model_version"])


@app.post("/api/v1/predict", response_model=PredictionResponse)
def predict(input_data: PredictionRequest) -> PredictionResponse:
    """Recibe las seis variables, llama al modelo y devuelve su estimación.

    FastAPI valida primero el tipo y el rango general de cada campo. La función
    devuelve 422 cuando una variable es inválida o queda fuera del rango
    observado, y 503 si el modelo no está disponible o no coincide con la API.
    """
    try:
        prediction = predict_2026(input_data.model_dump())
    except (FileNotFoundError, ModelConfigurationError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    _, metadata = load_model_bundle()
    return PredictionResponse(
        prediction=prediction,
        model_version=metadata["model_version"],
    )
