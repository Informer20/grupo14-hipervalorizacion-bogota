
import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

# --------------------------------------------------
# 1. CONFIGURACIÓN GENERAL
# --------------------------------------------------

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY]
)

app.title = "UrbanEye | Bogotá"

# --------------------------------------------------
# 2. COLORES
# --------------------------------------------------

COLORS = {
    "background": "#101827",
    "panel": "#1B2638",
    "panel_light": "#253449",
    "blue": "#3286D9",
    "cyan": "#45B8D1",
    "red": "#EF4444",
    "text": "#F1F5F9",
    "muted": "#94A3B8",
    "green": "#22C55E",
    "yellow": "#EAB308"
}

# --------------------------------------------------
# 3. COMPONENTES REUTILIZABLES
# --------------------------------------------------

def create_kpi(title, value, subtitle):
    return dbc.Card(
        dbc.CardBody([
            html.P(title, className="kpi-title"),
            html.H3(value, className="kpi-value"),
            html.P(subtitle, className="kpi-subtitle")
        ]),
        className="kpi-card"
    )


# --------------------------------------------------
# 4. GRÁFICO DEMOSTRATIVO
# --------------------------------------------------

price_chart = go.Figure()

price_chart.add_trace(go.Bar(
    x=["Valor actual", "Escenario estimado"],
    y=[4250000, 5180000],
    marker_color=["#64748B", "#3286D9"],
    text=["$4,25 M", "$5,18 M"],
    textposition="outside"
))

price_chart.update_layout(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=COLORS["text"]),
    margin=dict(l=20, r=20, t=35, b=20),
    height=280,
    showlegend=False,
    yaxis=dict(
        title="Pesos por m²",
        showgrid=True,
        gridcolor="#334155"
    )
)

# --------------------------------------------------
# 5. PANEL IZQUIERDO
# --------------------------------------------------

sidebar = dbc.Card([
    dbc.CardBody([
        html.H5("Configuración del escenario"),
        html.P(
            "Selecciona el territorio y define un escenario hipotético.",
            className="section-description"
        ),

        html.Label("Localidad"),
        dcc.Dropdown(
            options=[
                {"label": "Chapinero", "value": "Chapinero"},
                {"label": "Usaquén", "value": "Usaquén"},
                {"label": "Teusaquillo", "value": "Teusaquillo"}
            ],
            value="Chapinero",
            clearable=False
        ),

        html.Br(),

        html.Label("Barrio"),
        dcc.Dropdown(
            options=[
                {"label": "Chapinero Alto", "value": "Chapinero Alto"},
                {"label": "Chicó", "value": "Chicó"},
                {"label": "El Retiro", "value": "El Retiro"}
            ],
            value="Chapinero Alto",
            clearable=False
        ),

        html.Br(),

        html.Label("Nuevos alojamientos hipotéticos"),
        html.H4("350", className="slider-value"),

        dcc.Slider(
            min=0,
            max=1000,
            step=50,
            value=350,
            marks={
                0: "0",
                500: "500",
                1000: "1.000"
            }
        ),

        html.Hr(),

        html.H5("Configuración de alertas"),
        html.P(
            "Umbrales de variación estimada",
            className="section-description"
        ),

        dbc.Row([
            dbc.Col([
                html.Label("Verde (%)"),
                dbc.Input(type="number", value=5)
            ], width=4),

            dbc.Col([
                html.Label("Amarillo (%)"),
                dbc.Input(type="number", value=15)
            ], width=4),

            dbc.Col([
                html.Label("Rojo (%)"),
                dbc.Input(type="number", value=15)
            ], width=4)
        ], className="g-2"),

        html.Br(),

        dbc.Button(
            "Simular escenario",
            color="primary",
            className="w-100",
            disabled=True
        ),

        html.P(
            "Prototipo visual. Los controles aún no ejecutan cálculos.",
            className="prototype-note"
        )
    ])
], className="main-card h-100")


# --------------------------------------------------
# 6. MAPA DEMOSTRATIVO
# --------------------------------------------------

map_card = dbc.Card([
    dbc.CardBody([
        dbc.Row([
            dbc.Col(
                html.H5("Distribución territorial Airbnb"),
                width=8
            ),
            dbc.Col(
                dbc.Badge(
                    "Densidad de anuncios",
                    color="primary"
                ),
                width=4,
                className="text-end"
            )
        ]),

        html.P(
            "Bogotá D.C. | Distribución por sectores catastrales",
            className="section-description"
        ),

        html.Div([
            html.Div([
                html.Div(className="map-placeholder-icon"),
                html.H4("Mapa territorial de Bogotá"),
                html.P(
                    "Aquí se visualizarán los sectores catastrales "
                    "según la densidad de alojamientos Airbnb."
                ),
                dbc.Badge(
                    "Mapa ilustrativo pendiente de integración",
                    color="secondary"
                )
            ], className="map-placeholder-content")
        ], className="map-placeholder")
    ])
], className="main-card map-card")


# --------------------------------------------------
# 7. PANEL DERECHO
# --------------------------------------------------

indicators = html.Div([
    html.H5("Indicadores del territorio"),
    html.P(
        "Chapinero | Chapinero Alto",
        className="section-description"
    ),

    dbc.Row([
        dbc.Col(
            create_kpi(
                "Anuncios Airbnb",
                "1.248",
                "Oferta turística"
            ),
            width=6
        ),
        dbc.Col(
            create_kpi(
                "Estaciones",
                "12",
                "TransMilenio"
            ),
            width=6
        )
    ], className="g-2"),

    html.Br(),

    create_kpi(
        "CAGR inmobiliario",
        "14,8%",
        "Crecimiento anual compuesto 2015-2025"
    )
])

chart_card = dbc.Card([
    dbc.CardBody([
        html.H5("Valor comercial por m²"),
        html.P(
            "Comparación del escenario seleccionado",
            className="section-description"
        ),
        dcc.Graph(
            figure=price_chart,
            config={"displayModeBar": False}
        ),
        html.P(
            "Valores demostrativos, no corresponden a predicciones reales.",
            className="prototype-note"
        )
    ])
], className="main-card")


# --------------------------------------------------
# 8. ESTRUCTURA GENERAL
# --------------------------------------------------

header = dbc.Navbar(
    dbc.Container([
        html.Div([
            html.Span("URBANEYE", className="brand-name"),
            html.Span(
                " | BOGOTÁ PLANNING HUB",
                className="brand-subtitle"
            )
        ]),
        dbc.Badge(
            "PROTOTIPO VISUAL",
            color="info",
            className="p-2"
        )
    ], fluid=True),
    className="top-navbar"
)

app.layout = html.Div([
    header,

    dbc.Container([
        html.Div([
            html.H3(
                "Análisis de presión turística e inmobiliaria"
            ),
            html.P(
                "Exploración territorial y escenarios de "
                "alojamiento turístico en Bogotá D.C.",
                className="section-description"
            )
        ], className="page-heading"),

        dbc.Row([
            dbc.Col(sidebar, width=12, lg=3),

            dbc.Col(map_card, width=12, lg=6),

            dbc.Col(
                [
                    indicators,
                    html.Br(),
                    chart_card
                ],
                width=12,
                lg=3
            )
        ], className="g-3")

    ], fluid=True, className="dashboard-container")

], className="app-background")


# --------------------------------------------------
# 9. EJECUTAR APLICACIÓN
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=8050)
