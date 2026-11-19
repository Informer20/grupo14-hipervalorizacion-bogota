# Urban AI // Bogotá Planning Hub

## Descripción

Tablero interactivo para explorar anuncios Airbnb, características urbanas y valores de referencia inmobiliarios de Bogotá. Permite consultar localidades y barrios, ver sectores catastrales en un mapa, ajustar un escenario de nuevos alojamientos y solicitar una predicción del valor de referencia 2026.

La aplicación Dash obtiene la información territorial y la geometría del GeoPackage local. Al presionar **Ejecutar predicción**, el dashboard consulta una API FastAPI que carga el modelo XGBoost guardado como artefacto en MLflow. El servicio no entrena el modelo al iniciar: utiliza un paquete previamente exportado o, si se configura, carga la URI de MLflow en tiempo de ejecución.

Para estimar la densidad del escenario, se suman los anuncios Airbnb existentes y los nuevos alojamientos indicados en el deslizador y se divide ese total por el área del barrio. El máximo del deslizador se calcula con barrios comparables: primero busca el mismo estrato y localidad, con valores de referencia de 2025 cercanos; si hay pocos, amplía la comparación a toda Bogotá manteniendo el estrato. La API aplica la misma restricción aunque reciba una solicitud directa. Es una protección frente a escenarios poco representados, no una prueba de que el modelo se haya validado para esa unidad de análisis: el notebook entrena con sectores y el dashboard predice con agregados de barrio.

El semáforo clasifica el crecimiento predicho para 2026 frente al valor observado de 2025. Sus umbrales iniciales son los percentiles 33 y 67 del CAGR histórico agregado por barrio; el usuario puede modificarlos. Son bandas descriptivas de crecimiento, no probabilidades de riesgo producidas por XGBoost.

## Datos

`data/matriz_barrios_unificada.gpkg` contiene los datos consolidados y geometrías usados por el dashboard. Aunque otros archivos de datos tienen referencias DVC y el remoto está configurado en S3, el GeoPackage está incluido en el repositorio para que la revisión del MVP no dependa de `dvc pull` ni de la disponibilidad temporal de AWS Academy. Para una versión final, se debe definir cómo obtener y actualizar el conjunto desde un almacenamiento persistente.

## Estructura principal

- `api/app/`: rutas de la API y validación de los datos recibidos.
- `api/model/`: preparación de variables, carga e inferencia MLflow; no contiene entrenamiento.
- `api/export_model.py`: descarga un artefacto MLflow y crea el manifiesto local.
- `api/client.py`: adaptador HTTP que llama a la API desde el dashboard.
- `api/models/`: destino local del modelo exportado, ignorado por Git.
- `dashboard/`: aplicación Dash, mapa, CSS y JavaScript.
- `dashboard/risk.py`: calcula los umbrales iniciales con los datos observados y clasifica el crecimiento predicho.
- `data/`: matriz geográfica para el mapa y validación de rangos.
- `notebooks/`: análisis y experimentos de modelos.
- `tests/`: pruebas de API, preparación de variables y cliente HTTP.
- `docs/ARQUITECTURA_Y_PRUEBAS.md`: explicación general de archivos y pruebas.
- `docs/MLFLOW.md`: guía para encontrar y descargar el modelo desde Databricks.
- `Dockerfile` y `.dockerignore`: construcción de una imagen para prueba o despliegue.

## Obtener el modelo y ejecutar localmente

El notebook de referencia guarda el artefacto `xgboost_model_bruto` dentro de la ejecución `XGB_Sin_Log`; no registra automáticamente un modelo en Model Registry. Se necesita el Run ID de esa ejecución en Databricks. Los pasos de autenticación y exportación están en [docs/MLFLOW.md](./docs/MLFLOW.md).

Después de configurar `MLFLOW_TRACKING_URI`, `DATABRICKS_HOST`, `DATABRICKS_TOKEN` y `MLFLOW_MODEL_URI`, descarga el paquete:

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m api.export_model
```

Inicia la aplicación desde la raíz del repositorio:

```powershell
python run_dashboard.py
```

El lanzador selecciona el intérprete Python, verifica las dependencias, comprueba el modelo y levanta API y dashboard. El modelo puede estar exportado en `api/models/xgboost_mlflow/` o ser accesible mediante la URI MLflow configurada. Si no se cumple ninguna de esas condiciones, el lanzador se detiene con una instrucción; no crea ni entrena un reemplazo.

Direcciones locales:

- Dashboard: `http://127.0.0.1:8050`
- Salud de la API: `http://127.0.0.1:8001/health`
- Documentación interactiva de la API: `http://127.0.0.1:8001/docs`

## Pruebas

```powershell
python -m pytest -q
python -m tox
```

Las pruebas unitarias no requieren credenciales de Databricks ni cargar el artefacto remoto. La validación del modelo real, su firma y una inferencia de extremo a extremo sí requieren acceso al artefacto. Para el propósito de cada prueba, consulta [docs/ARQUITECTURA_Y_PRUEBAS.md](./docs/ARQUITECTURA_Y_PRUEBAS.md).

## Docker y Railway

Docker empaqueta la aplicación; Railway puede construir y alojar esa imagen. No son opciones excluyentes. El Dockerfile ejecuta dashboard y API en un solo contenedor para el MVP; no entrena modelos. En Railway se puede cargar el artefacto durante el arranque con credenciales guardadas como variables privadas, o proveer un paquete exportado al contexto Docker. No se debe incluir el token de Databricks en el repositorio ni en la imagen.

Para construir y ejecutar localmente con Docker se necesita haber exportado el modelo:

```powershell
docker build -t urban-ai-bogota .
docker run --rm -p 8050:8050 -e PORT=8050 urban-ai-bogota
```

La configuración del servicio Railway y el almacenamiento definitivo de datos/modelos siguen pendientes. Consulta [docs/MLFLOW.md](./docs/MLFLOW.md) antes de desplegar.
