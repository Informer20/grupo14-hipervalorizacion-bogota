"""Comprueba que el servicio no envíe al modelo combinaciones no observadas."""

import pytest

from api.model import predictor


def test_predictor_rejects_density_above_comparable_neighborhoods(monkeypatch):
    """Rechaza la densidad aunque siga dentro del máximo global de la ciudad.

    El escenario tiene estrato y valor 2025 conocidos, pero su densidad supera
    la de sus pares de estrato y precio. El modelo simulado debe no recibir la
    fila porque la validación condicional ocurre antes de llamar a ``predict``.
    """
    class Model:
        def predict(self, features):
            raise AssertionError("El modelo no debe recibir este escenario.")

    metadata = {
        "feature_ranges": {
            "estrato_predominante": {"min": 0, "max": 6},
            "v_ref_2025": {"min": 1, "max": 1000},
            "cagr_15_25": {"min": -1, "max": 1},
            "num_estaciones_transmilenio": {"min": 0, "max": 10},
            "densidad_airbnb_km2": {"min": 0, "max": 1000},
        },
        "neighborhood_profiles": [
            {
                "localidad": "LOCALIDAD A",
                "barrio": "UNO",
                "estrato_predominante": 1,
                "v_ref_2025": 100,
                "densidad_airbnb_km2": 5,
            },
            {
                "localidad": "LOCALIDAD A",
                "barrio": "DOS",
                "estrato_predominante": 1,
                "v_ref_2025": 105,
                "densidad_airbnb_km2": 8,
            },
            {
                "localidad": "LOCALIDAD B",
                "barrio": "TRES",
                "estrato_predominante": 1,
                "v_ref_2025": 95,
                "densidad_airbnb_km2": 10,
            },
        ],
        "feature_columns": ["one"],
        "locality_categories": ["LOCALIDAD A"],
    }
    monkeypatch.setattr(predictor, "load_model_bundle", lambda: (Model(), metadata))
    input_data = {
        "localidad": "LOCALIDAD A",
        "estrato_predominante": 1,
        "v_ref_2025": 100,
        "cagr_15_25": 0.1,
        "num_estaciones_transmilenio": 1,
        "densidad_airbnb_km2": 11,
    }

    with pytest.raises(ValueError, match="máximo observado entre barrios comparables"):
        predictor.predict_2026(input_data)
