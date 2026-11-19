"""Interfaz Dash: filtros, mapa, métricas, semáforo y solicitud de predicción."""

import os
from pathlib import Path

import dash
from dash import Input, Output, State, dcc, html, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from api.client import PredictionAPIError, predict_neighborhood
from api.model.features import (
    build_feature_metadata,
    max_new_listings_for_density,
    peer_density_ceiling,
)
from map_view import create_map, load_geodata
from risk import (
    calculate_growth_percent,
    classify_risk,
    observed_growth_thresholds,
)


ASSETS_DIR = Path(__file__).resolve().parent
GDF = load_geodata()
LOCALIDADES = sorted(GDF["localidad"].dropna().unique().tolist())
DEFAULT_LOCALIDAD = "CHAPINERO" if "CHAPINERO" in LOCALIDADES else LOCALIDADES[0]
DEFAULT_BARRIOS = sorted(
    GDF.loc[GDF["localidad"] == DEFAULT_LOCALIDAD, "barrio"]
    .dropna()
    .unique()
    .tolist()
)
DEFAULT_BARRIO = "LOS ROSALES" if "LOS ROSALES" in DEFAULT_BARRIOS else DEFAULT_BARRIOS[0]
MAX_SCENARIO_NEW_LISTINGS = 1000
SCENARIO_NEW_LISTINGS_STEP = 50

COLORS = {
    "background": "#0b0f19",
    "panel": "#0f172a",
    "blue": "#3b82f6",
    "text": "#f1f5f9",
    "muted": "#94a3b8",
    "green": "#22c55e",
    "yellow": "#eab308",
    "red": "#ef4444",
}

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    assets_folder=str(ASSETS_DIR),
)
app.title = "Análisis territorial | Bogotá"


def create_empty_chart():
    """Crea la gráfica vacía con el tema oscuro y las unidades del tablero."""
    figure = go.Figure()
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": COLORS["text"]},
        margin={"l": 48, "r": 8, "t": 22, "b": 24},
        autosize=True,
        showlegend=False,
        yaxis={
            "title": {
                "text": "Millones de pesos/m²",
                "font": {"size": 9},
                "standoff": 2,
            },
            "tickfont": {"size": 8},
            "tickformat": ".1f",
            "gridcolor": "#253449",
            "rangemode": "tozero",
        },
        xaxis={"tickfont": {"size": 9}},
    )
    return figure


def format_integer(value):
    """Muestra un valor numérico entero con separadores de miles en español."""
    return f"{int(round(float(value))):,}".replace(",", ".")


def format_currency(value):
    """Muestra un precio por metro cuadrado o el texto de dato pendiente."""
    if value is None:
        return "Pendiente"
    return f"$ {format_integer(value)}"


DEFAULT_GREEN_THRESHOLD, DEFAULT_YELLOW_THRESHOLD = observed_growth_thresholds(GDF)


def build_diagnosis(
    record,
    risk_zone,
    new_listings,
    predicted_value=None,
    predicted_growth_percent=None,
):
    """Redacta el resumen del barrio y, si existe, del escenario predicho."""
    diagnosis = (
        f"En el barrio {record['barrio'].title()}, localidad de "
        f"{record['localidad'].title()}, predomina el estrato "
        f"{format_integer(record['estrato_predominante'])} y su área es de "
        f"{record['area_km2']:.2f} km². Actualmente se registran "
        f"{format_integer(record['num_listings_airbnb'])} anuncios de Airbnb, "
        f"una densidad de {record['densidad_airbnb_km2']:.2f} propiedades por km² "
        f"y {format_integer(record['num_estaciones_transmilenio'])} estaciones de "
        f"TransMilenio. Su valor de referencia en 2025 fue de "
        f"{format_currency(record['v_ref_2025'])} por m² y el CAGR histórico "
        f"2015–2025 es de {record['cagr_15_25'] * 100:.2f}%."
    )
    if predicted_value is not None:
        scenario_listings = int(record["num_listings_airbnb"]) + int(new_listings)
        scenario_density = scenario_listings / record["area_km2"]
        diagnosis += (
            f" Para el escenario de {format_integer(new_listings)} nuevos "
            f"alojamientos (total considerado: "
            f"{format_integer(scenario_listings)}, equivalente a "
            f"{scenario_density:.2f} propiedades por km²), XGBoost estima un "
            f"valor de referencia para 2026 de {format_currency(predicted_value)} "
            f"por m². Esto equivale a un crecimiento predicho de "
            f"{predicted_growth_percent:.2f}% frente a 2025, clasificado en "
            f"zona {risk_zone} según los umbrales definidos."
        )
    else:
        diagnosis += (
            " Ejecuta la predicción para calcular el crecimiento de 2026 frente "
            "a 2025 y clasificarlo en el semáforo."
        )
    return diagnosis


def aggregate_neighborhood(localidad, barrio):
    """Reúne las métricas de los sectores que componen el barrio seleccionado."""
    selected = GDF[
        (GDF["localidad"] == localidad) & (GDF["barrio"] == barrio)
    ]
    if selected.empty:
        return None

    area = selected["area_km2"].fillna(0).sum()
    listings = selected["num_listings_airbnb"].fillna(0).sum()
    record = {
        "localidad": localidad,
        "barrio": barrio,
        "estrato_predominante": selected["estrato_predominante"].mode().iloc[0],
        "area_km2": area,
        "num_listings_airbnb": listings,
        "densidad_airbnb_km2": listings / area if area else 0,
        "num_estaciones_transmilenio": selected[
            "num_estaciones_transmilenio"
        ].fillna(0).sum(),
    }

    weights = selected["area_km2"].fillna(0)
    total_area = weights.sum()
    for column in ("v_ref_2015", "v_ref_2025", "cagr_15_25"):
        values = selected[column].fillna(0)
        record[column] = (
            (values * weights).sum() / total_area
            if total_area
            else values.mean()
        )
    return record


def create_price_chart(record, predicted_value=None):
    """Compara el valor de referencia de 2025 con la predicción opcional."""
    labels = ["2025 referencia"]
    values = [record["v_ref_2025"] / 1_000_000]
    colors = [COLORS["blue"]]

    if predicted_value is not None:
        labels.append("2026 predicho")
        values.append(predicted_value / 1_000_000)
        colors.append("#f59e0b")

    figure = create_empty_chart()
    figure.add_trace(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"$ {value:.2f} M".replace(".", ",") for value in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x}<br>$ %{y:.2f} millones/m²<extra></extra>",
        )
    )
    figure.update_layout(yaxis={"range": [0, max(values) * 1.3]})
    return figure


def create_details(record, new_listings):
    """Crea la ficha con las métricas del barrio y los anuncios del escenario."""
    details = [
        ("Localidad", record["localidad"].title()),
        ("Barrio", record["barrio"].title()),
        ("Estrato predominante", format_integer(record["estrato_predominante"])),
        ("Área por kilómetro cuadrado", f'{record["area_km2"]:.2f} km²'),
        ("Anuncios Airbnb existentes", format_integer(record["num_listings_airbnb"])),
        ("Nuevos alojamientos del escenario", format_integer(new_listings)),
        ("Densidad Airbnb", f'{record["densidad_airbnb_km2"]:.2f} propiedades/km²'),
        ("Estaciones de TransMilenio", format_integer(record["num_estaciones_transmilenio"])),
        ("Valor de referencia 2015", f'{format_currency(record["v_ref_2015"])} /m²'),
        ("Valor de referencia 2025", f'{format_currency(record["v_ref_2025"])} /m²'),
        (
            "Valor de referencia 2026 predicho",
            f'{format_currency(record.get("v_ref_2026_predicho"))} /m²',
        ),
        (
            "Crecimiento predicho 2026 vs. 2025",
            (
                f'{record["crecimiento_predicho_2026_pct"]:.2f}%'
                if record.get("crecimiento_predicho_2026_pct") is not None
                else "Pendiente"
            ),
        ),
        ("CAGR histórico 2015–2025", f'{record["cagr_15_25"] * 100:.2f}%'),
    ]
    return [
        dbc.Col(
            html.Div(
                [
                    html.P(label, className="detail-label"),
                    html.P(value, className="detail-value"),
                ],
                className="detail-item",
            ),
            xs=6,
            sm=6,
            lg=4,
        )
        for label, value in details
    ]


sidebar = dbc.Card(
    dbc.CardBody(
        [
            html.H5("Panel de control de simulación"),
            html.P(
                "Selecciona un territorio y ajusta los parámetros del escenario.",
                className="section-description",
            ),
            html.Label("Localidad"),
            dcc.Dropdown(
                id="localidad-select",
                options=[{"label": item.title(), "value": item} for item in LOCALIDADES],
                value=DEFAULT_LOCALIDAD,
                clearable=False,
                className="dark-dropdown",
            ),
            html.Br(),
            html.Label("Barrio"),
            dcc.Dropdown(
                id="barrio-select",
                options=[{"label": item.title(), "value": item} for item in DEFAULT_BARRIOS],
                value=DEFAULT_BARRIO,
                clearable=False,
                className="dark-dropdown",
            ),
            html.Hr(),
            html.H5("Nuevos alojamientos"),
            html.P(
                "El máximo se calcula con barrios comparables por estrato, localidad y valor de referencia.",
                className="section-description",
            ),
            html.H4(id="new-listings-label", className="slider-value"),
            dcc.Slider(
                id="new-listings",
                min=0,
                max=1000,
                step=50,
                value=0,
                marks={
                    0: {"label": "0", "style": {"color": "#ffffff"}},
                    500: {"label": "500", "style": {"color": "#ffffff"}},
                    1000: {"label": "1.000", "style": {"color": "#ffffff"}},
                },
                className="new-listings-slider",
                tooltip={"placement": "bottom", "always_visible": False},
            ),
            html.Hr(),
            html.Div(
                [
                    html.H5("Semáforo de riesgo predicho"),
                    html.P(
                        (
                            "Clasifica el crecimiento que predice el modelo para 2026 "
                            "frente al valor observado de 2025. Los valores iniciales "
                            f"({DEFAULT_GREEN_THRESHOLD:.1f}% y "
                            f"{DEFAULT_YELLOW_THRESHOLD:.1f}%) son los percentiles "
                            "33 y 67 del crecimiento histórico observado; puedes cambiarlos."
                        ),
                        className="section-description",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label("Verde: hasta (%)"),
                                    dbc.Input(
                                        id="green-threshold",
                                        className="threshold-input green",
                                        type="number",
                                        step="any",
                                        value=DEFAULT_GREEN_THRESHOLD,
                                    ),
                                ],
                                xs=6,
                                md=6,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Amarillo: máximo (%)"),
                                    dbc.Input(
                                        id="yellow-threshold",
                                        className="threshold-input yellow",
                                        type="number",
                                        step="any",
                                        value=DEFAULT_YELLOW_THRESHOLD,
                                    ),
                                ],
                                xs=6,
                                md=6,
                            ),
                        ],
                        className="g-2",
                    ),
                    html.Div(id="risk-alert", className="risk-alert", role="status"),
                    html.P(
                        "Verde: hasta el primer umbral; amarillo: entre umbrales; rojo: por encima del segundo.",
                        className="prototype-note",
                    ),
                    dbc.Button(
                        "Ejecutar predicción",
                        id="run-prediction",
                        color="primary",
                        className="w-100 prediction-button",
                        disabled=False,
                    ),
                    html.P(
                        id="prediction-status",
                        className="prediction-status",
                        role="status",
                    ),
                    html.Div(
                        [
                            dbc.Spinner(size="sm", color="info"),
                            html.Span("Calculando predicción..."),
                        ],
                        id="prediction-loading",
                        className="prediction-loading",
                        role="status",
                        style={"display": "none"},
                    ),
                    html.P(
                        "La predicción usa las variables del territorio y el escenario seleccionados.",
                        className="prototype-note",
                    ),
                ],
                className="risk-panel",
            ),
        ]
    ),
    className="main-card h-100",
)

map_card = dbc.Card(
    dbc.CardBody(
        [
            dbc.Row(
                [
                    dbc.Col(html.H5("Densidad de alojamientos turísticos"), width=8),
                    dbc.Col(
                        dbc.Badge("Propiedades/km²", color="primary"),
                        width=4,
                        className="text-end",
                    ),
                ]
            ),
            html.P(
                "Bogotá D.C. | Sectores catastrales",
                className="section-description",
            ),
            dcc.Graph(
                id="territorial-map",
                figure=create_map(
                    DEFAULT_LOCALIDAD,
                    DEFAULT_BARRIO
                ),
                style={"height": "520px"}
            ),
        ]
    ),
    className="main-card map-card",
)

diagnosis_card = dbc.Card(
    dbc.CardBody(
        [
            html.H5("Diagnóstico y contexto del barrio"),
            html.P(
                "Selecciona un territorio para consultar su contexto.",
                id="selected-territory",
                className="section-description",
            ),
            html.P(id="diagnosis-text", className="diagnosis-text"),
        ]
    ),
    className="main-card",
)

indicators_card = dbc.Card(
    dbc.CardBody(
        [
            html.H5("Indicadores del territorio"),
            html.P(id="indicator-location", className="section-description"),
            dbc.Row(id="territory-details", className="g-2"),
        ]
    ),
    className="main-card indicators-card",
)

chart_card = dbc.Card(
    dbc.CardBody(
        [
            html.H5("Valor de referencia por m²"),
            html.P(
                "Comparación de valores de referencia de 2025 y 2026.",
                className="section-description",
            ),
            dcc.Graph(
                id="price-chart",
                figure=create_empty_chart(),
                config={"displayModeBar": False},
                style={"height": "100%", "flex": "1 1 auto", "minHeight": 0},
            ),
            html.P(
                "Valores de referencia disponibles en la matriz; no son predicciones.",
                className="prototype-note",
            ),
        ]
    ),
    className="main-card chart-card",
)

app.layout = html.Div(
    [
        dcc.Store(id="prediction-result-store"),
        dbc.Container(
            [
                html.Div(
                    [
                        html.H3("Análisis de presión turística e inmobiliaria"),
                        html.P(
                            "Exploración territorial de los alojamientos turísticos y el contexto inmobiliario de Bogotá.",
                            className="section-description",
                        ),
                    ],
                    className="page-heading",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(sidebar, className="dashboard-column left-panel"),
                            width=12,
                            lg=3,
                        ),
                        dbc.Col(
                            html.Div(
                                [map_card, diagnosis_card],
                                className="dashboard-column center-panel",
                            ),
                            width=12,
                            lg=6,
                        ),
                        dbc.Col(
                            html.Div(
                                [indicators_card, chart_card],
                                className="dashboard-column right-panel",
                            ),
                            width=12,
                            lg=3,
                        ),
                    ],
                    className="g-3 dashboard-row",
                ),
            ],
            fluid=True,
            className="dashboard-container",
        ),
    ],
    className="app-background",
)


@app.callback(
    Output("barrio-select", "options"),
    Output("barrio-select", "value"),
    Output("new-listings", "max"),
    Output("new-listings", "value"),
    Output("new-listings", "marks"),
    Input("localidad-select", "value"),
    Input("barrio-select", "value"),
    State("new-listings", "value"),
)
def update_neighborhood_options(localidad, current_barrio, current_new_listings):
    """Actualiza barrios y limita el deslizador a densidades comparables."""
    barrios = sorted(
        GDF.loc[GDF["localidad"] == localidad, "barrio"].dropna().unique().tolist()
    )
    selected = current_barrio if current_barrio in barrios else (barrios[0] if barrios else None)
    record = aggregate_neighborhood(localidad, selected) if selected else None
    if record and record["area_km2"] > 0:
        profiles = build_feature_metadata()["neighborhood_profiles"]
        max_density = peer_density_ceiling(record, profiles)
        allowed_new_listings = max_new_listings_for_density(
            record,
            max_density,
            MAX_SCENARIO_NEW_LISTINGS,
        )
        allowed_new_listings = (
            allowed_new_listings // SCENARIO_NEW_LISTINGS_STEP
        ) * SCENARIO_NEW_LISTINGS_STEP
    else:
        allowed_new_listings = 0

    clamped_new_listings = min(
        int(current_new_listings or 0),
        allowed_new_listings,
    )
    marks = {0: {"label": "0", "style": {"color": "#ffffff"}}}
    if allowed_new_listings > 0:
        marks[allowed_new_listings] = {
            "label": format_integer(allowed_new_listings),
            "style": {"color": "#ffffff"},
        }
    return (
        [{"label": barrio.title(), "value": barrio} for barrio in barrios],
        selected,
        allowed_new_listings,
        clamped_new_listings,
        marks,
    )


@app.callback(
    Output("territorial-map", "figure"),
    Output("selected-territory", "children"),
    Output("indicator-location", "children"),
    Output("diagnosis-text", "children"),
    Output("territory-details", "children"),
    Output("price-chart", "figure"),
    Output("new-listings-label", "children"),
    Output("risk-alert", "children"),
    Output("risk-alert", "className"),
    Output("prediction-status", "children"),
    Input("localidad-select", "value"),
    Input("barrio-select", "value"),
    Input("green-threshold", "value"),
    Input("yellow-threshold", "value"),
    Input("new-listings", "value"),
    Input("prediction-result-store", "data"),
    State("new-listings", "max"),
)
def update_dashboard(
    localidad,
    barrio,
    green_limit,
    yellow_limit,
    new_listings,
    prediction_result,
    max_new_listings,
):
    """Actualiza el contexto y reclasifica el último escenario predicho."""
    if not localidad or not barrio:
        return (
            create_empty_chart(),
            "Sin territorio seleccionado",
            "",
            "No hay datos para la selección.",
            [],
            create_empty_chart(),
            "",
            "Selecciona un territorio para ver el diagnóstico.",
            "risk-alert",
            "",
        )

    record = aggregate_neighborhood(localidad, barrio)
    if record is None:
        return (
            create_map(localidad, barrio),
            "Sin datos para el territorio seleccionado",
            "",
            "No hay datos disponibles para este territorio.",
            [],
            create_empty_chart(),
            (
                f"{format_integer(new_listings)} alojamientos nuevos "
                f"(máximo permitido: {format_integer(max_new_listings)})"
            ),
            "No se puede calcular el semáforo sin datos.",
            "risk-alert invalid",
            "",
        )

    locality_name = localidad.title()
    neighborhood_name = barrio.title()
    matching_result = (
        prediction_result
        and prediction_result.get("localidad") == localidad
        and prediction_result.get("barrio") == barrio
        and prediction_result.get("new_listings") == int(new_listings or 0)
    )
    predicted_value = (
        float(prediction_result["prediction"])
        if matching_result and "prediction" in prediction_result
        else None
    )
    predicted_growth_percent = (
        calculate_growth_percent(predicted_value, record["v_ref_2025"])
        if predicted_value is not None and record["v_ref_2025"] > 0
        else None
    )
    if predicted_growth_percent is not None:
        risk_message, risk_class, risk_zone = classify_risk(
            predicted_growth_percent,
            green_limit,
            yellow_limit,
        )
    else:
        threshold_message, threshold_class, threshold_zone = classify_risk(
            0,
            green_limit,
            yellow_limit,
        )
        if threshold_zone == "sin clasificar":
            risk_message, risk_class, risk_zone = (
                threshold_message,
                threshold_class,
                threshold_zone,
            )
        else:
            risk_message = (
                "Ejecuta la predicción para clasificar el crecimiento de 2026."
            )
            risk_class = "risk-alert"
            risk_zone = "pendiente"

    if predicted_value is not None:
        record["v_ref_2026_predicho"] = predicted_value
        record["crecimiento_predicho_2026_pct"] = predicted_growth_percent
    diagnosis = build_diagnosis(
        record,
        risk_zone,
        new_listings or 0,
        predicted_value,
        predicted_growth_percent,
    )
    if matching_result and prediction_result.get("error"):
        current_status = prediction_result["error"]
    elif predicted_value is not None:
        current_status = (
            f"Predicción XGBoost para {neighborhood_name}: "
            f"{format_currency(predicted_value)} por m²."
        )
    else:
        current_status = ""

    return (
        create_map(localidad, barrio, predicted_value),
        f"{neighborhood_name} | {locality_name}",
        f"{neighborhood_name} · {locality_name}",
        diagnosis,
        create_details(record, new_listings or 0),
        create_price_chart(record, predicted_value),
        (
            f"{format_integer(new_listings or 0)} alojamientos nuevos "
            f"(máximo comparable: {format_integer(max_new_listings)})"
        ),
        risk_message,
        risk_class,
        current_status,
    )


@app.callback(
    Output("prediction-result-store", "data"),
    Input("run-prediction", "n_clicks"),
    State("localidad-select", "value"),
    State("barrio-select", "value"),
    State("new-listings", "value"),
    prevent_initial_call=True,
    running=[
        (Output("run-prediction", "disabled"), True, False),
        (
            Output("prediction-loading", "style"),
            {"display": "flex"},
            {"display": "none"},
        ),
    ],
)
def run_prediction(
    n_clicks,
    localidad,
    barrio,
    num_listings_airbnb,
):
    """Solicita una predicción y la guarda para mostrarla y clasificarla."""
    if not n_clicks:
        return no_update

    if not localidad or not barrio:
        return {
            "error": "Selecciona una localidad y un barrio antes de ejecutar la predicción."
        }

    record = aggregate_neighborhood(localidad, barrio)
    if record is None:
        return {"error": "No se encontraron datos para el territorio seleccionado."}

    try:
        prediction = predict_neighborhood(record, num_listings_airbnb or 0)
    except PredictionAPIError as error:
        return {
            "localidad": localidad,
            "barrio": barrio,
            "new_listings": int(num_listings_airbnb or 0),
            "error": f"No se pudo predecir: {error}",
        }

    prediction_result = {
        "localidad": localidad,
        "barrio": barrio,
        "new_listings": int(num_listings_airbnb or 0),
        "prediction": prediction,
    }
    return prediction_result


if __name__ == "__main__":
    app.run(
        debug=os.getenv("DASH_DEBUG", "true").lower() == "true",
        host=os.getenv("URBAN_AI_DASH_HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8050")),
    )
