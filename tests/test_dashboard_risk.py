"""Comprueba los umbrales observados y los colores del semáforo predicho."""

import pandas as pd
import pytest

from dashboard.risk import (
    calculate_growth_percent,
    classify_risk,
    observed_growth_thresholds,
)


def test_growth_percent_compares_prediction_with_observed_2025_value():
    """Mide cuánto cambia la predicción respecto al último valor observado.

    Se usa un valor de 2025 de 100 y una predicción de 2026 de 107,5. El
    resultado esperado es un crecimiento de 7,5%, no una resta de 7,5 unidades
    ni el CAGR histórico. ``approx`` admite la pequeña diferencia de precisión
    que aparece al representar porcentajes con números decimales en Python.
    """
    assert calculate_growth_percent(107.5, 100) == pytest.approx(7.5)


def test_risk_is_classified_from_predicted_growth_against_2025():
    """Comprueba los límites y el sentido de las tres zonas del semáforo.

    Con umbrales de 5% y 10%, 5% queda en verde porque el primer límite se
    incluye; 7,5% queda en amarillo porque está entre los límites; y 10,1%
    queda en rojo porque supera el segundo. También se comprueba -2%: una
    predicción inferior al valor de 2025 es crecimiento negativo y debe quedar
    en verde, no tratarse como error ni como un riesgo alto.
    """
    assert classify_risk(5, 5, 10)[2] == "verde"
    assert classify_risk(7.5, 5, 10)[2] == "amarilla"
    assert classify_risk(10.1, 5, 10)[2] == "roja"
    assert classify_risk(-2, 5, 10)[2] == "verde"


def test_risk_thresholds_must_be_finite_and_in_increasing_order():
    """Impide mostrar un color engañoso si los umbrales están invertidos.

    El primer umbral (verde) se fija en 10 y el segundo (amarillo) en 5. Como
    esa configuración no deja un intervalo coherente entre verde y amarillo,
    la función debe devolver un aviso, el estilo visual de configuración
    inválida y el estado ``sin clasificar`` en lugar de asignar un color.
    """
    message, style, zone = classify_risk(7, 10, 5)

    assert "verde menor que amarillo" in message
    assert style == "risk-alert invalid"
    assert zone == "sin clasificar"


def test_default_thresholds_are_growth_percentiles_from_neighborhood_data():
    """Deriva los umbrales iniciales de barrios observados, no de números fijos.

    El ejemplo contiene tres barrios de una localidad, cada uno con el mismo
    peso de área y CAGR de 3%, 6% y 9%. Los percentiles 33 y 67 caen en 5% y
    7%, respectivamente; el assert comprueba que esos valores alimenten por
    defecto el semáforo, mientras que los valores de entrada del dashboard
    siguen pudiendo modificarse por el usuario.
    """
    geodata = pd.DataFrame(
        {
            "localidad": ["A", "A", "A"],
            "barrio": ["UNO", "DOS", "TRES"],
            "area_km2": [1, 1, 1],
            "cagr_15_25": [0.03, 0.06, 0.09],
        }
    )

    assert observed_growth_thresholds(geodata) == (5.0, 7.0)
