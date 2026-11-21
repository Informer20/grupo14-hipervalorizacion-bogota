# Imagen de Python compatible con MLflow, GeoPandas y XGBoost.
FROM python:3.12-slim

# En producción Dash escucha el puerto de Railway; el modelo no se entrena aquí.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DASH_DEBUG=false \
    URBAN_AI_DASH_HOST=0.0.0.0 \
    URBAN_AI_USE_SYSTEM_PYTHON=1 \
    URBAN_AI_SKIP_DEPENDENCY_INSTALL=1

WORKDIR /app

# XGBoost requiere la biblioteca OpenMP del sistema operativo.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Instala las dependencias de la aplicación una sola vez al construir la imagen.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copia API, dashboard y matriz; el paquete MLflow se incluye si fue exportado.
COPY api/ ./api/
COPY dashboard/ ./dashboard/
COPY data/matriz_barrios_unificada.gpkg ./data/matriz_barrios_unificada.gpkg
COPY run_dashboard.py ./

# Railway entrega el puerto en PORT; la aplicación lo lee al arrancar.
EXPOSE 8050

# El lanzador inicia la API local y luego el dashboard.
CMD ["python", "run_dashboard.py"]
