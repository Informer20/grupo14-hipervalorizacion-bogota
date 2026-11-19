"""Comprueba las respuestas HTTP de la API sin conectar a Databricks."""

from fastapi.testclient import TestClient

from api.app import main


def test_health_reports_ready_model(monkeypatch):
    """Verifica el estado exitoso de salud cuando hay un modelo disponible.

    Se reemplaza la carga real por un modelo simulado, se consulta ``/health``
    y se comprueba que la API responda 200 y comunique la versión cargada.
    """
    monkeypatch.setattr(
        main,
        "load_model_bundle",
        lambda: (object(), {"model_version": "test-model"}),
    )
    client = TestClient(main.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "model_version": "test-model",
    }


def test_health_reports_model_unavailable(monkeypatch):
    """Verifica que ``/health`` responda 503 si no se encuentra el modelo.

    La carga simulada genera el mismo tipo de error que ocurre cuando todavía
    no se exportó un paquete y la respuesta permite identificar el servicio
    como no disponible, en vez de indicar que está listo.
    """
    def missing_model():
        raise FileNotFoundError("missing model")

    monkeypatch.setattr(main, "load_model_bundle", missing_model)
    client = TestClient(main.app)

    response = client.get("/health")

    assert response.status_code == 503


def test_predict_returns_numeric_prediction(monkeypatch):
    """Comprueba la solicitud completa de predicción desde el punto de vista HTTP.

    Se envían las seis variables como JSON y se simulan el predictor y la carga
    del modelo. Los asserts confirman el código 200, el valor numérico devuelto,
    el identificador de modelo, el nombre de la variable estimada y que el
    predictor haya recibido los mismos datos enviados por el cliente.
    """
    expected_input = {
        "localidad": "CHAPINERO",
        "estrato_predominante": 6,
        "v_ref_2025": 7_000_000,
        "cagr_15_25": 0.12,
        "num_estaciones_transmilenio": 3,
        "densidad_airbnb_km2": 250,
    }
    received = {}

    def fake_predict(input_data):
        received.update(input_data)
        return 7_500_000.0

    monkeypatch.setattr(main, "predict_2026", fake_predict)
    monkeypatch.setattr(
        main,
        "load_model_bundle",
        lambda: (object(), {"model_version": "test-model"}),
    )
    client = TestClient(main.app)

    response = client.post("/api/v1/predict", json=expected_input)

    assert response.status_code == 200
    assert response.json() == {
        "prediction": 7_500_000.0,
        "model_version": "test-model",
        "target": "v_ref_2026",
    }
    assert received == expected_input


def test_predict_rejects_invalid_scenario_payload():
    """Rechaza un valor de densidad negativo antes de ejecutar el predictor.

    El JSON contiene el resto de campos válidos, por lo que el 422 confirma
    que FastAPI aplica la restricción de densidad mínima cero.
    """
    client = TestClient(main.app)
    invalid_input = {
        "localidad": "CHAPINERO",
        "estrato_predominante": 6,
        "v_ref_2025": 7_000_000,
        "cagr_15_25": 0.12,
        "num_estaciones_transmilenio": 3,
        "densidad_airbnb_km2": -1,
    }

    response = client.post("/api/v1/predict", json=invalid_input)

    assert response.status_code == 422


def test_predict_rejects_values_outside_observed_ranges(monkeypatch):
    """Convierte a HTTP 422 el error de una variable fuera del rango observado.

    El predictor simulado genera un ``ValueError`` y los asserts verifican
    tanto el código de validación como el detalle que recibe el cliente.
    """
    def out_of_range_prediction(input_data):
        raise ValueError("densidad fuera del rango observado")

    monkeypatch.setattr(main, "predict_2026", out_of_range_prediction)
    client = TestClient(main.app)
    valid_shape = {
        "localidad": "CHAPINERO",
        "estrato_predominante": 6,
        "v_ref_2025": 7_000_000,
        "cagr_15_25": 0.12,
        "num_estaciones_transmilenio": 3,
        "densidad_airbnb_km2": 250,
    }

    response = client.post("/api/v1/predict", json=valid_shape)

    assert response.status_code == 422
    assert response.json()["detail"] == "densidad fuera del rango observado"


def test_predict_rejects_non_text_locality():
    """Rechaza una localidad numérica en lugar de convertirla a texto.

    La solicitud mantiene válidos los demás campos; el código 422 demuestra
    que el tipo de la localidad se valida al recibir el JSON.
    """
    client = TestClient(main.app)
    invalid_input = {
        "localidad": 12,
        "estrato_predominante": 6,
        "v_ref_2025": 7_000_000,
        "cagr_15_25": 0.12,
        "num_estaciones_transmilenio": 3,
        "densidad_airbnb_km2": 250,
    }

    response = client.post("/api/v1/predict", json=invalid_input)

    assert response.status_code == 422


def test_predict_rejects_unexpected_input_field():
    """Rechaza campos que la API no reconoce, como un barrio adicional.

    La respuesta 422 avisa al cliente de que el formato enviado debe ajustarse
    a los campos que consume actualmente el modelo.
    """
    client = TestClient(main.app)
    invalid_input = {
        "localidad": "CHAPINERO",
        "estrato_predominante": 6,
        "v_ref_2025": 7_000_000,
        "cagr_15_25": 0.12,
        "num_estaciones_transmilenio": 3,
        "densidad_airbnb_km2": 250,
        "barrio": "CHICO NORTE",
    }

    response = client.post("/api/v1/predict", json=invalid_input)

    assert response.status_code == 422
