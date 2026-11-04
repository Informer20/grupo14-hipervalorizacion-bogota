
from pathlib import Path
from functools import lru_cache

import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go


# Ruta de los datos
BASE_DIR = Path(__file__).resolve().parent.parent
GPKG_PATH = BASE_DIR / "data" / "matriz_barrios_unificada.gpkg"


@lru_cache(maxsize=1)
def load_geodata():
    return gpd.read_file(
        GPKG_PATH,
        layer="matriz_barrios_unificada",
    ).reset_index(drop=True)


def create_map(localidad=None, barrio=None):
    gdf = load_geodata().copy()
    gdf["sector_id"] = gdf.index.astype(str)

    geojson = gdf.__geo_interface__
    points = gdf.geometry.representative_point()
    center_lat, center_lon = points.y.mean(), points.x.mean()

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
            "densidad_airbnb_km2": "Anuncios Airbnb/km²",
            "num_listings_airbnb": "Anuncios Airbnb"
        }
    )

    if localidad and barrio:
        seleccionado = gdf[
            (gdf["localidad"] == localidad) & (gdf["barrio"] == barrio)
        ]
    else:
        seleccionado = gdf.iloc[0:0]

    if not seleccionado.empty:
        fig.add_trace(
            go.Choroplethmap(
                geojson=geojson,
                locations=seleccionado["sector_id"],
                z=[1] * len(seleccionado),
                featureidkey="properties.sector_id",
                colorscale=[
                    [0, "rgba(0,0,0,0)"],
                    [1, "rgba(0,0,0,0)"]
                ],
                showscale=False,
                marker_opacity=1,
                marker_line_color="#EF4444",
                marker_line_width=2.5,
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font_color="#f1f5f9",
        margin=dict(l=0, r=0, t=5, b=0),
        height=520,
        coloraxis_colorbar=dict(
            title="",
            thickness=14
        )
    )

    return fig
