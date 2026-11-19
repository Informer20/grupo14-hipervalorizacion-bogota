# Obtener y ejecutar el XGBoost registrado en MLflow

## Qué modelo buscar en Databricks

El notebook `notebooks/MLflow - Databricks/XGBoost_MLflow.ipynb` registra dos artefactos dentro de ejecuciones de MLflow:

- `xgboost_model_bruto`, asociado a la ejecución `XGB_Sin_Log`, que predice `v_ref_2026` en su escala original.
- `xgboost_model_log`, asociado a `XGB_Con_Log`, que predice el objetivo transformado y requiere revertir el logaritmo.

Para la integración actual se espera el modelo **bruto**, `xgboost_model_bruto`. En el notebook se llama a `mlflow.xgboost.log_model(...)`, pero no se llama a `mlflow.register_model(...)`. Por eso puede que el modelo exista como artefacto de una ejecución y no como un modelo registrado en el Model Registry.

## Localizar la URI del artefacto

1. Abre en Databricks el experimento `/modelos-hipervalorizacion`.
2. Busca la ejecución llamada `XGB_Sin_Log`.
3. Copia el Run ID desde sus detalles.
4. Comprueba en la pestaña **Artifacts** que exista la carpeta `xgboost_model_bruto`.
5. Construye la URI:

```text
runs:/<RUN_ID>/xgboost_model_bruto
```

Si el equipo registró posteriormente una versión en Model Registry, también puede utilizar una URI `models:/<nombre>/<versión>` o un alias compatible con su workspace. No reemplaces el artefacto bruto por `xgboost_model_log`.

## Descargar y empaquetar localmente

Instala las dependencias y configura las variables solo en la terminal o en un gestor de secretos; nunca guardes el token en el código o en Git. En PowerShell:

```powershell
$env:MLFLOW_TRACKING_URI = "databricks"
$env:DATABRICKS_HOST = "https://<tu-workspace>.cloud.databricks.com"
$env:DATABRICKS_TOKEN = "<token-personal>"
$env:MLFLOW_MODEL_URI = "runs:/<RUN_ID>/xgboost_model_bruto"
python -m api.export_model
```

El token es una credencial privada. No lo compartas en chats, capturas, archivos de configuración versionados ni argumentos que puedan guardarse en el historial del shell. Si la cuenta gratuita no permite crear un token personal, usa el mecanismo de autenticación autorizado por ese workspace.

El comando descarga el artefacto, valida que tenga descriptor `MLmodel`, comprueba que su firma tenga las mismas columnas que espera la aplicación y crea `api/models/xgboost_mlflow/urban_ai_manifest.json`. El manifiesto registra el URI, las columnas, las categorías de localidad, los rangos y los perfiles de barrios comparables calculados desde el GeoPackage local. No reentrena el modelo.

El exportador se detiene si ya existe la carpeta de destino para evitar reemplazar una versión sin confirmación. Si necesitas exportar otra versión, revisa y guarda la actual antes de retirar específicamente `api/models/xgboost_mlflow/`.

## Probarlo localmente

Una vez descargado el artefacto:

```powershell
python -m pytest -q
python run_dashboard.py
```

También se puede comprobar la API y su documentación interactiva en:

```text
http://127.0.0.1:8001/health
http://127.0.0.1:8001/docs
```

El dashboard aparece en `http://127.0.0.1:8050`. Las pruebas unitarias no requieren Databricks; para probar la carga real, el endpoint de salud y una predicción sí se necesita el modelo exportado.

## Docker y Railway

El `Dockerfile` copia `api/models/` si el paquete exportado está dentro del contexto de construcción. En un equipo local, primero ejecuta `api.export_model` y luego:

```powershell
docker build -t urban-ai-bogota .
docker run --rm -p 8050:8050 -e PORT=8050 urban-ai-bogota
```

Para Railway conectado directamente al repositorio Git, el paquete exportado se excluye deliberadamente de Git, por lo que Railway no lo recibirá automáticamente. Hay dos opciones:

1. **Carga remota en tiempo de ejecución:** configura en Railway `MLFLOW_TRACKING_URI`, `MLFLOW_MODEL_URI`, `DATABRICKS_HOST` y `DATABRICKS_TOKEN` como variables privadas. La API descarga/carga el modelo desde Databricks al primer chequeo de salud. La cuenta, el workspace, la red y la credencial deben seguir disponibles.
2. **Modelo empaquetado dentro de la imagen:** proporciona el directorio exportado al contexto Docker de Railway mediante el mecanismo de almacenamiento/artefactos que defina el equipo. Si se versiona el modelo en Git, considera tamaño, permisos y política de versionado antes de hacerlo; no añadas tokens al Dockerfile.

El contenedor ejecuta API y dashboard en un solo servicio para el MVP. FastAPI escucha en `127.0.0.1:8001` dentro del contenedor y Dash escucha en `0.0.0.0:$PORT`, que Railway publica. Esto evita exponer directamente el puerto de inferencia. Este Dockerfile prepara la aplicación, pero no crea el servicio ni las variables en Railway.

## Pendientes al obtener acceso al modelo

- Confirmar que la ejecución correcta sea `XGB_Sin_Log` y revisar sus métricas en MLflow.
- Verificar que el esquema registrado corresponda a las columnas calculadas con el GeoPackage local.
- Confirmar que las versiones de XGBoost y demás dependencias del artefacto sean compatibles con la imagen.
- Probar una predicción real y compararla con el resultado registrado o con un caso de referencia.
- Confirmar que el GeoPackage y el modelo se construyeron a partir de la misma versión de datos; los rangos del manifiesto se derivan de la copia local.
