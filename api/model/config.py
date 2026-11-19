"""Nombres, rutas y variables que conectan el dashboard con el modelo."""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Archivo geográfico del que el dashboard obtiene barrios y la API calcula rangos.
DATA_PATH = PROJECT_ROOT / "data" / "matriz_barrios_unificada.gpkg"
# Carpeta para guardar, de forma local, una copia descargada desde MLflow.
MODEL_DIR = PROJECT_ROOT / "api" / "models"
PACKAGED_MODEL_DIR = MODEL_DIR / "xgboost_mlflow"
# URI runs:/... o models:/... del modelo de MLflow que debe cargarse.
MODEL_URI = os.getenv("MLFLOW_MODEL_URI")
# Columna que el modelo aprende a estimar.
TARGET_COLUMN = "v_ref_2026"

# Las cinco columnas numéricas y la localidad se convierten al formato del modelo.
INPUT_COLUMNS = [
    "localidad",
    "estrato_predominante",
    "v_ref_2025",
    "cagr_15_25",
    "num_estaciones_transmilenio",
    "densidad_airbnb_km2",
]
LOCALITY_COLUMN = "localidad"
# Archivo auxiliar creado por este proyecto junto al modelo descargado.
MODEL_MANIFEST_NAME = "urban_ai_manifest.json"
