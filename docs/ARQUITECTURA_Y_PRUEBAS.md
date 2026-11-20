# Arquitectura de la API, el dashboard y las pruebas

## Flujo general

El dashboard carga el GeoPackage para mostrar el mapa, los filtros y el contexto del barrio. Cuando el usuario presiona **Ejecutar predicción**, el cliente HTTP prepara las variables y envía una solicitud a FastAPI. La API valida el formato, los rangos globales y la densidad máxima de barrios comparables; transforma la localidad a las columnas que exige el artefacto MLflow y llama al modelo ya entrenado.

La aplicación no entrena el modelo al iniciar. El modelo se carga desde `api/models/xgboost_mlflow/` si se exportó localmente; si esa carpeta no contiene el paquete, la API puede cargar la URI configurada en `MLFLOW_MODEL_URI`.

## Mapa de archivos

### Lanzador y dashboard

- `run_dashboard.py`: elige el intérprete Python, verifica las dependencias, comprueba que exista un modelo local o una URI MLflow, inicia Uvicorn y después Dash. Al cerrar el dashboard, detiene el proceso de la API. No entrena ni reemplaza el modelo.
- `dashboard/app.py`: crea la aplicación Dash. Define los componentes visuales y coordina tres callbacks: uno actualiza localidad, barrio y límite del deslizador; otro presenta el contexto y reclasifica el último resultado cuando cambian umbrales o selección; el tercero espera el clic del botón y solicita la predicción. La opción de carga se activa únicamente durante esa llamada.
- `dashboard/risk.py`: calcula los umbrales iniciales con los percentiles 33 y 67 del CAGR observado por barrio, y clasifica el crecimiento predicho de 2026 frente al valor de 2025.
- `dashboard/map_view.py`: lee el GeoPackage y arma el mapa coroplético y el resaltado del barrio seleccionado.
- `dashboard/style.css`: estilos y distribución visual.
- `dashboard/map_zoom.js`: limita el zoom mínimo del mapa en el navegador.

### API y datos que recibe

- `api/app/main.py`: define `GET /health` y `POST /api/v1/predict`. Salud comprueba que el paquete se pueda cargar; predicción valida la solicitud y devuelve el valor estimado.
- `api/app/schemas.py`: define los campos que acepta la API, sus tipos y restricciones generales. `localidad` debe ser texto; los números deben ser finitos y no negativos cuando corresponde; se rechazan campos adicionales.
- `api/client.py`: prepara y envía los datos del dashboard a la API. Suma los anuncios Airbnb del barrio y los nuevos del deslizador, y divide ese total por el área para calcular `densidad_airbnb_km2`. También maneja errores de conexión, respuestas HTTP y resultados mal formados.

El campo `barrio` no se envía al modelo: no es una variable de su matriz de entrenamiento. El dashboard lo usa para encontrar el registro geográfico y reunir las demás características. La API recibe `localidad` y las cinco variables numéricas del modelo.

### Carga y preparación del modelo

- `api/model/config.py`: reúne rutas, el objetivo, el nombre de las variables de entrada y la URI opcional configurada en `MLFLOW_MODEL_URI`.
- `api/model/features.py`: lee las variables observadas del GeoPackage para conocer las localidades válidas, el orden esperado de columnas, los rangos numéricos y perfiles agregados por barrio. Calcula un límite de densidad a partir de hasta diez barrios del mismo estrato y de valor de referencia similar: prioriza la localidad seleccionada, requiere al menos tres pares dentro de un margen de 25% del valor 2025 y, si son insuficientes, amplía la búsqueda a toda Bogotá dentro del mismo estrato. También codifica la localidad en variables indicadoras como en el notebook que guardó el modelo.
- `api/model/predictor.py`: carga el modelo MLflow local o remoto una sola vez, comprueba que los nombres y el orden de las columnas coincidan con los registrados en MLflow, rechaza valores fuera de los rangos generales y del máximo de densidad entre barrios comparables, y obtiene la predicción. No contiene entrenamiento.
- `api/export_model.py`: descarga el artefacto de una URI MLflow a `api/models/xgboost_mlflow/` y agrega `urban_ai_manifest.json`, con las variables, categorías y rangos del GeoPackage local.
- `api/models/.gitkeep`: mantiene el directorio de artefactos en Git. El modelo exportado se ignora en Git para no versionar binarios ni copias locales de artefactos.

El `MLmodel` del paquete es un descriptor de MLflow, no el modelo por sí solo. Al lado suele haber un archivo de modelo serializado y archivos de entorno que describen dependencias. El `urban_ai_manifest.json` lo crea este proyecto para recordar los nombres y rangos de las variables que deben coincidir entre los datos y el modelo.

## Validación de entradas y extrapolación

La API aplica tres niveles de validación:

1. **Formato y reglas generales**, en Pydantic: tipos, valores finitos, estrato entre 0 y 6, referencias positivas, conteos y densidad no negativos, y rechazo de campos inesperados.
2. **Rangos generales observados**, en `predictor.py`: compara las variables numéricas con los mínimos y máximos de los barrios agregados desde el GeoPackage.
3. **Densidad entre barrios comparables**, en `features.py` y `predictor.py`: compara el estrato y el valor 2025 con perfiles observados. El máximo dinámico del deslizador busca todos los barrios del mismo estrato cuyo valor 2025 esté dentro de ±25 %, toma el mayor número de anuncios observados, lo multiplica por 1.25 y redondea hacia arriba. Si el resultado es menor que el escenario actual, conserva al menos cinco unidades nuevas. El deslizador avanza de uno en uno y no supera 1000. Si el escenario supera el máximo dinámico, la API no llama al modelo y responde con un error `422`.

Estos límites reducen escenarios alejados de los datos observados, pero no garantizan que todas las combinaciones permitidas sean representativas o causalmente válidas. Hay además una diferencia de nivel que debe resolverse en la etapa de evaluación: el notebook registra el XGBoost entrenado con filas de sectores catastrales, mientras que el dashboard agrega las entradas por barrio. Los filtros de rangos no demuestran que un modelo entrenado por sector generalice bien a entradas agregadas por barrio. Hay que confirmar la unidad de análisis con el tutor y con el artefacto MLflow antes de presentar la simulación como validada.

El semáforo solo tiene una clasificación después de ejecutar una predicción: calcula `(valor predicho 2026 / valor observado 2025 - 1) × 100`. Verde cubre hasta el primer umbral, amarillo el intervalo entre ambos y rojo los valores superiores al segundo. Los valores iniciales son los percentiles 33 y 67 de los CAGR observados por barrio, ponderados por área; son referencias descriptivas que el usuario puede editar, no probabilidades de que ocurra un evento.

## Qué comprueba cada prueba

Las pruebas usan pytest. Las pruebas HTTP emplean `TestClient` para enviar solicitudes directamente a FastAPI sin abrir un servidor real. `monkeypatch` reemplaza temporalmente funciones en pruebas que necesitan aislar el endpoint de la carga real del modelo. Las pruebas del cliente simulan la respuesta HTTP para comprobar el contenido enviado sin depender de Databricks.

### `tests/test_api.py`

- `test_health_reports_ready_model`: el endpoint de salud responde `200` e informa la versión cargada.
- `test_health_reports_model_unavailable`: el endpoint de salud responde `503` si no hay artefacto MLflow disponible.
- `test_predict_returns_numeric_prediction`: una predicción simulada produce la estructura de respuesta esperada y el endpoint entrega al predictor los campos recibidos.
- `test_predict_rejects_invalid_scenario_payload`: una densidad negativa se rechaza con `422`.
- `test_predict_rejects_values_outside_observed_ranges`: un escenario con forma válida pero fuera del rango observado se rechaza con `422`.
- `test_predict_rejects_non_text_locality`: una localidad numérica se rechaza en vez de convertirse implícitamente a texto.
- `test_predict_rejects_unexpected_input_field`: un campo no esperado —por ejemplo, `barrio`— se rechaza para que API y cliente usen los mismos datos.

Las pruebas de endpoint aíslan la predicción usando `monkeypatch`; no comprueban las métricas ni reentrenan XGBoost.

### `tests/test_client.py`

- `test_prediction_uses_existing_and_new_listings_for_density`: comprueba que el payload del cliente suma los anuncios existentes y los nuevos y divide por el área.
- `test_prediction_rejects_non_positive_area`: verifica que no se intente calcular densidad con un área nula o negativa.

### `tests/test_model_features.py`

- `test_prediction_features_match_the_mlflow_input_schema`: utiliza una localidad conocida y comprueba que la fila tenga los nombres y orden de columnas que espera el modelo.
- `test_prediction_features_reject_unknown_locality`: rechaza localidades que no aparecen en las categorías conocidas.
- `test_feature_values_are_numeric_before_calling_mlflow`: comprueba que las variables preparadas sean numéricas.
- `test_feature_metadata_uses_barrio_level_ranges`: verifica que los límites de escenario se calculen en el mismo nivel de barrio que usa el dashboard.
- `test_slider_limit_accounts_for_existing_listings_and_area`: comprueba el límite calculado de nuevos anuncios al tener en cuenta el área, los anuncios actuales y el tope global.
- `test_comparable_new_listings_limit_always_allows_five_and_rounds_up`: comprueba que el máximo de anuncios nuevos se derive de barrios comparables, redondee hacia arriba y conserve al menos cinco nuevos.

La prueba de localidad no intenta demostrar el funcionamiento interno de `drop_first`; verifica que una solicitud conocida produzca la forma de fila que necesita el modelo. La prueba de localidad desconocida comprueba que una entrada que el modelo no vio se rechace explícitamente.

No hay un `test_training.py`: el servicio no entrena. Las pruebas comprueban los contratos alrededor de un artefacto preexistente o remoto. La carga de un artefacto MLflow real requiere disponer de una URI, credenciales y acceso; se verifica manualmente después de exportarlo con los comandos de `MLFLOW.md`.

### `tests/test_predictor.py`

- `test_predictor_rejects_density_above_comparable_neighborhoods`: confirma que la API rechace un escenario que supera a sus pares aunque siga dentro del máximo global de la ciudad, antes de llamar al modelo.

### `tests/test_dashboard_risk.py`

- `test_growth_percent_compares_prediction_with_observed_2025_value`: comprueba que el crecimiento se mida como porcentaje frente al valor observado del año anterior.
- `test_risk_is_classified_from_predicted_growth_against_2025`: comprueba las tres zonas con crecimientos por debajo, entre y por encima de los umbrales, incluido un crecimiento negativo.
- `test_risk_thresholds_must_be_finite_and_in_increasing_order`: comprueba que una configuración inválida se señale en lugar de clasificar.
- `test_default_thresholds_are_growth_percentiles_from_neighborhood_data`: verifica que los umbrales iniciales se calculen desde los CAGR observados por barrio.

## Relación con los ejemplos del curso

La implementación toma como referencia los patrones de los talleres revisados: separar API y modelo, validar solicitudes mediante esquemas, probar rutas con un cliente HTTP de pruebas, automatizar pytest con tox y describir el entorno en un Dockerfile. No es una copia literal del repositorio de un taller. El cliente Dash, el formato de `urban_ai_manifest.json`, la descarga desde la URI concreta de Databricks y la combinación de dashboard y API en un contenedor para el MVP son adaptaciones específicas de este proyecto.

## Herramientas de dependencias y ejecución

- `requirements.txt`: dependencias de ejecución, incluidas Dash, GeoPandas, FastAPI, MLflow, Requests, XGBoost y Uvicorn.
- `requirements-dev.txt`: pytest, tox y `httpx` para las pruebas de FastAPI.
- `tox.ini`: crea un entorno de prueba aislado con las dependencias que necesita la suite y ejecuta pytest.
- `.gitignore`: excluye entornos, cachés y el artefacto MLflow exportado.
- `Dockerfile`: crea una imagen con aplicación, datos y dependencias; no entrena modelos.
- `.dockerignore`: excluye datos locales de desarrollo que no se necesitan en la imagen. Permite incluir un paquete MLflow si está presente en el contexto Docker.

Para validar la suite:

```powershell
python -m pytest -q
python -m tox
```
