"""Cálculo de umbrales observados y clasificación del crecimiento predicho."""

import numpy as np


def observed_growth_thresholds(geodata):
    """Calcula umbrales iniciales con los percentiles 33, 67 y 75 del CAGR.

    El crecimiento histórico por barrio se pondera por área. Los percentiles
    dividen los barrios observados en tres grupos de referencia; no son
    probabilidades de riesgo producidas por el modelo.
    """
    growth_rates = []
    for _, selected in geodata.groupby(["localidad", "barrio"], sort=True):
        area = selected["area_km2"].fillna(0)
        total_area = area.sum()
        cagr = selected["cagr_15_25"].fillna(0)
        weighted_cagr = (
            (cagr * area).sum() / total_area
            if total_area
            else cagr.mean()
        )
        if np.isfinite(weighted_cagr):
            growth_rates.append(float(weighted_cagr) * 100)

    if not growth_rates:
        raise ValueError("No hay valores de crecimiento observado para el semáforo.")
    green_limit, yellow_limit, red_start = np.quantile(
        growth_rates,
        [1 / 3, 2 / 3, 3 / 4],
    )
    return (
        round(float(green_limit), 1),
        round(float(yellow_limit), 1),
        round(float(red_start), 1),
    )


def calculate_growth_percent(predicted_value, observed_value):
    """Calcula el cambio porcentual de la predicción respecto al año observado."""
    observed_value = float(observed_value)
    if observed_value <= 0:
        raise ValueError("El valor observado debe ser mayor que cero.")
    return (float(predicted_value) / observed_value - 1) * 100


def classify_risk(predicted_growth_percent, green_limit, yellow_limit, red_start):
    """Clasifica el crecimiento de 2026 estimado frente al valor de 2025.

    Verde comprende valores hasta el primer umbral; amarillo, valores mayores
    al primero y hasta el segundo; rojo, valores mayores al segundo. Los
    umbrales son porcentajes configurables, no probabilidades de riesgo.
    """
    try:
        green_limit = float(green_limit)
        yellow_limit = float(yellow_limit)
        red_start = float(red_start)
    except (TypeError, ValueError):
        green_limit = yellow_limit = float("nan")
        red_start = float("nan")

    thresholds_valid = (
        np.isfinite(green_limit)
        and np.isfinite(yellow_limit)
        and np.isfinite(red_start)
        and green_limit < yellow_limit
        and red_start >= yellow_limit
    )
    if not thresholds_valid:
        return (
            "Revisa los valores: el umbral verde debe ser menor que el amarillo.",
            "risk-alert invalid",
            "sin clasificar",
        )
    if predicted_growth_percent <= green_limit:
        return (
            f"El valor de riesgo detectado es {predicted_growth_percent:.2f}%. "
            "No se emite alerta.",
            "risk-alert green",
            "verde",
        )
    if predicted_growth_percent > red_start:
        return (
            f"El valor de riesgo detectado es {predicted_growth_percent:.2f}%. "
            "Se emite una alerta roja.",
            "risk-alert red",
            "roja",
        )
    return (
        f"El valor de riesgo detectado es {predicted_growth_percent:.2f}%. "
        "Se emite una alerta amarilla.",
        "risk-alert yellow",
        "amarilla",
    )
