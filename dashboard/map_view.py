
from pathlib import Path

import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go


# Ruta de los datos
BASE_DIR = Path(__file__).resolve().parent.parent
GPKG_PATH = BASE_DIR / "data" / "matriz_barrios_unificada.gpkg"


def create_map():

    # Cargar información geográfica
    gdf = gpd.read_file(
        GPKG_PATH,
        layer="matriz_barrios_unificada"
    ).reset_index(drop=True)

    # Identificador único por sector
    gdf["sector_id"] = gdf.index.astype(str)

    # Sector seleccionado para el prototipo
    seleccionado = (
        (gdf["localidad"] == "CHAPINERO") &
        (gdf["barrio"] == "LOS ROSALES")
    )

    # GeoJSON
    geojson = gdf.__geo_interface__

    # Centro geográfico aproximado
    points = gdf.geometry.representative_point()

    center_lat = points.y.mean()
    center_lon = points.x.mean()

    # Mapa base
    fig = px.choropleth_map(
        gdf,
        geojson=geojson,
        locations="sector_id",
        featureidkey="properties.sector_id",
        color="densidad_airbnb_km2",
        color_continuous_scale=[
            "#DCEAF7",
            "#A9CBE8",
            "#6D9FCC",
            "#376B9C",
            "#163B65"
        ],
        map_style="carto-darkmatter",
        center={
            "lat": center_lat,
            "lon": center_lon
        },
        zoom=10,
        opacity=0.85,
        hover_name="barrio",
        hover_data={
            "localidad": True,
            "densidad_airbnb_km2": ":.2f",
            "num_listings_airbnb": True,
            "sector_id": False
        },
        labels={
            "localidad": "Localidad",
            "densidad_airbnb_km2": "Anuncios/km²",
            "num_listings_airbnb": "Anuncios Airbnb"
        }
    )

    # Resaltar sector seleccionado
    if seleccionado.any():

        fig.add_trace(
            go.Choroplethmap(
                geojson=geojson,
                locations=gdf.loc[
                    seleccionado, "sector_id"
                ],
                z=[1] * seleccionado.sum(),
                featureidkey="properties.sector_id",
                colorscale=[
                    [0, "#EF4444"],
                    [1, "#EF4444"]
                ],
                showscale=False,
                marker_opacity=0.95,
                marker_line_color="#FFFFFF",
                marker_line_width=1.5,
                hovertemplate=(
                    "<b>LOS ROSALES</b><br>"
                    "Localidad: Chapinero<br>"
                    "Anuncios Airbnb: 46<br>"
                    "Densidad: 111,99 anuncios/km²"
                    "<extra></extra>"
                )
            )
        )

    # Diseño del mapa
    fig.update_layout(
        paper_bgcolor="#1B2638",
        plot_bgcolor="#1B2638",
        font_color="#F1F5F9",
        margin=dict(l=0, r=0, t=5, b=0),
        height=650,
        coloraxis_colorbar=dict(
            title="Anuncios/km²",
            thickness=14
        )
    )

    return fig
