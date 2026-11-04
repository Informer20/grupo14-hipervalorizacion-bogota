from pathlib import Path

import dash
from dash import Input, Output, dcc, html
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from map_view import create_map, load_geodata


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
    return f"{int(round(float(value))):,}".replace(",", ".")


def format_currency(value):
    return f"$ {format_integer(value)}"


def aggregate_neighborhood(localidad, barrio):
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

    for column in ("v_ref_2015", "v_ref_2025", "v_ref_2026", "cagr_15_25"):
        values = selected[column].fillna(0)
        weights = selected["area_km2"].fillna(0)
        record[column] = (
            (values * weights).sum() / weights.sum()
            if weights.sum()
            else values.mean()
        )
    return record


def create_details(record, new_listings):
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
        ("Valor de referencia 2026", f'{format_currency(record["v_ref_2026"])} /m²'),
        ("CAGR histórico 2015–2025", f'{record["cagr_15_25"] * 100:.2f}%'),
    ]
    return [
        dbc.Col(
            html.Div(
                [
                    html.P(label, className="detail-label"),
                    html.P(value, className="detail-value"),
                ],
                className="detail-item kpi-card",
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
                "Parámetro de escenario; no altera las métricas históricas.",
                className="section-description",
            ),
            html.H4(id="new-listings-label", className="slider-value"),
            dcc.Slider(
                id="new-listings",
                min=0,
                max=1000,
                step=50,
                value=350,
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
                    html.H5("Semáforo de riesgo histórico"),
                    html.P(
                        "Clasifica el CAGR 2015–2025 del territorio seleccionado.",
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
                                        min=0,
                                        value=5,
                                    ),
                                ],
                                xs=12,
                                md=4,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Amarillo: hasta (%)"),
                                    dbc.Input(
                                        id="yellow-threshold",
                                        className="threshold-input yellow",
                                        type="number",
                                        min=0,
                                        value=15,
                                    ),
                                ],
                                xs=12,
                                md=4,
                            ),
                            dbc.Col(
                                [
                                    html.Label("Rojo: desde (%)"),
                                    dbc.Input(
                                        id="red-threshold",
                                        className="threshold-input red",
                                        type="number",
                                        min=0,
                                        value=20,
                                    ),
                                ],
                                xs=12,
                                md=4,
                            ),
                        ],
                        className="g-2",
                    ),
                    html.Div(id="risk-alert", className="risk-alert", role="status"),
                    html.P(
                        "Indicador descriptivo del crecimiento histórico; no es una predicción.",
                        className="prototype-note",
                    ),
                    dbc.Button(
                        "Ejecutar predicción",
                        id="run-prediction",
                        color="primary",
                        className="w-100 prediction-button",
                        disabled=True,
                        title="La función de predicción aún no está implementada.",
                    ),
                    html.P(
                        "El escenario todavía no ejecuta cálculos de predicción.",
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
                figure=create_map(DEFAULT_LOCALIDAD, DEFAULT_BARRIO),
                config={"displayModeBar": False, "scrollZoom": True, "responsive": True},
                style={"height": "520px"},
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
    Input("localidad-select", "value"),
    Input("barrio-select", "value"),
)
def update_neighborhood_options(localidad, current_barrio):
    barrios = sorted(
        GDF.loc[GDF["localidad"] == localidad, "barrio"].dropna().unique().tolist()
    )
    selected = current_barrio if current_barrio in barrios else (barrios[0] if barrios else None)
    return [{"label": barrio.title(), "value": barrio} for barrio in barrios], selected


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
    Input("localidad-select", "value"),
    Input("barrio-select", "value"),
    Input("green-threshold", "value"),
    Input("yellow-threshold", "value"),
    Input("red-threshold", "value"),
    Input("new-listings", "value"),
)
def update_dashboard(localidad, barrio, green_limit, yellow_limit, red_start, new_listings):
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
            f"{format_integer(new_listings)} alojamientos",
            "No se puede calcular el semáforo sin datos.",
            "risk-alert invalid",
        )

    cagr_percent = record["cagr_15_25"] * 100
    thresholds_valid = (
        green_limit is not None
        and yellow_limit is not None
        and red_start is not None
        and 0 <= green_limit < yellow_limit < red_start
    )
    if not thresholds_valid:
        risk_message = "Configura valores en orden: verde < amarillo < rojo."
        risk_class = "risk-alert invalid"
    elif cagr_percent <= green_limit:
        risk_message = (
            f"El crecimiento histórico de {cagr_percent:.2f}% se ubica en zona verde."
        )
        risk_class = "risk-alert green"
    elif cagr_percent >= red_start:
        risk_message = (
            f"El crecimiento histórico de {cagr_percent:.2f}% se ubica en zona roja."
        )
        risk_class = "risk-alert red"
    else:
        risk_message = (
            f"El crecimiento histórico de {cagr_percent:.2f}% se ubica en zona amarilla."
        )
        risk_class = "risk-alert yellow"

    locality_name = localidad.title()
    neighborhood_name = barrio.title()
    diagnosis = (
        f"En {neighborhood_name}, localidad de {locality_name}, se registran "
        f'{format_integer(record["num_listings_airbnb"])} anuncios de Airbnb y '
        f'{format_integer(record["num_estaciones_transmilenio"])} estaciones de TransMilenio. '
        f'El crecimiento anual compuesto histórico (2015–2025) es de {cagr_percent:.2f}%; '
        f'el estrato predominante es {format_integer(record["estrato_predominante"])} y la '
        f'densidad es de {record["densidad_airbnb_km2"]:.2f} propiedades por km². '
        f"El escenario contempla {format_integer(new_listings)} nuevos alojamientos; "
        "este parámetro no se incorpora a una predicción de precios."
    )

    chart = create_empty_chart()
    chart_values = [record["v_ref_2025"] / 1_000_000, record["v_ref_2026"] / 1_000_000]
    chart.add_trace(
        go.Bar(
            x=["2025", "2026"],
            y=chart_values,
            marker_color=[COLORS["blue"], "#38bdf8"],
            text=[
                f'$ {value:.2f} M'.replace(".", ",") for value in chart_values
            ],
            textposition="outside",
            cliponaxis=False,
        )
    )
    chart.update_layout(
        yaxis={
            "title": {
                "text": "Millones de pesos/m²",
                "font": {"size": 9},
                "standoff": 2,
            },
            "tickfont": {"size": 8},
            "tickformat": ".1f",
            "gridcolor": "#253449",
            "range": [0, max(chart_values) * 1.3],
        },
        xaxis={"tickfont": {"size": 9}},
    )

    return (
        create_map(localidad, barrio),
        f"{neighborhood_name} | {locality_name}",
        f"{neighborhood_name} · {locality_name}",
        diagnosis,
        create_details(record, new_listings or 0),
        chart,
        f"{format_integer(new_listings or 0)} alojamientos",
        risk_message,
        risk_class,
    )


if __name__ == "__main__":
    app.run(debug=True, port=8050)
