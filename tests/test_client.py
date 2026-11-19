"""Comprueba el cálculo de densidad y los errores visibles en el dashboard."""

from unittest.mock import Mock

import pytest

from api.client import PredictionAPIError, predict_neighborhood


@pytest.fixture
def neighborhood_record():
    """Datos simples de un barrio para simular una selección en el dashboard."""
    return {
        "localidad": "CHAPINERO",
        "estrato_predominante": 6,
        "v_ref_2025": 7_000_000,
        "cagr_15_25": 0.12,
        "num_estaciones_transmilenio": 3,
        "area_km2": 2,
        "num_listings_airbnb": 100,
    }


def test_prediction_uses_existing_and_new_listings_for_density(
    monkeypatch,
    neighborhood_record,
):
    """Envía a la API la densidad que resulta del escenario elegido.

    ``requests.post`` se sustituye por una respuesta simulada para no levantar
    la API. Se comprueba que el cliente devuelva la predicción y que calcule
    ``(100 anuncios existentes + 20 nuevos) / 2 km² = 60`` en el JSON enviado.
    """
    response = Mock(ok=True)
    response.json.return_value = {"prediction": 7_500_000}
    post = Mock(return_value=response)
    monkeypatch.setattr("api.client.requests.post", post)

    prediction = predict_neighborhood(neighborhood_record, new_listings=20)

    assert prediction == 7_500_000
    payload = post.call_args.kwargs["json"]
    assert payload["densidad_airbnb_km2"] == 60


def test_prediction_rejects_non_positive_area(neighborhood_record):
    """Informa un error comprensible si no se puede dividir por el área.

    El área del barrio se cambia a cero y se comprueba que el cliente detenga
    el cálculo antes de hacer una solicitud HTTP.
    """
    neighborhood_record["area_km2"] = 0

    with pytest.raises(PredictionAPIError, match="área.*mayor que cero"):
        predict_neighborhood(neighborhood_record, new_listings=20)
