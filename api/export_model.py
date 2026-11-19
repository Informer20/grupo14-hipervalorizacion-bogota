"""Descarga una copia local del artefacto XGBoost guardado en MLflow."""

import os
import shutil
import tempfile
from pathlib import Path

import mlflow

from api.model.config import DATA_PATH, PACKAGED_MODEL_DIR
from api.model.features import build_feature_metadata, write_model_manifest
from api.model.predictor import _validate_model_signature


def export_model(model_uri: str, destination: Path = PACKAGED_MODEL_DIR) -> Path:
    """Descarga el modelo indicado y prepara los archivos para la API.

    ``model_uri`` identifica un artefacto de una ejecución o una versión
    registrada, por ejemplo ``runs:/<id>/xgboost_model_bruto``. La función
    comprueba que sea un paquete MLflow y que sus columnas coincidan con las
    variables disponibles en el GeoPackage. No entrena ni cambia el modelo.
    """
    if destination.exists():
        raise FileExistsError(
            f"Ya existe {destination}; consérvalo o retíralo manualmente "
            "antes de exportar una nueva versión."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    feature_metadata = build_feature_metadata(DATA_PATH)
    with tempfile.TemporaryDirectory(
        prefix="urban-ai-mlflow-",
        dir=destination.parent,
    ) as temp_dir:
        temp_path = Path(temp_dir)
        downloaded_path = Path(
            mlflow.artifacts.download_artifacts(
                artifact_uri=model_uri,
                dst_path=str(temp_path / "download"),
            )
        )
        if not (downloaded_path / "MLmodel").is_file():
            raise ValueError(
                "La URI descargada no apunta a un modelo MLflow con archivo MLmodel."
            )

        model = mlflow.pyfunc.load_model(str(downloaded_path))
        _validate_model_signature(model, feature_metadata["feature_columns"])
        staged_path = temp_path / "package"
        shutil.copytree(downloaded_path, staged_path)
        write_model_manifest(staged_path, feature_metadata, model_uri)
        os.replace(staged_path, destination)
    return destination


def main() -> None:
    """Lee MLFLOW_MODEL_URI y exporta el artefacto correspondiente."""
    model_uri = os.getenv("MLFLOW_MODEL_URI")
    if not model_uri:
        raise RuntimeError(
            "Configura MLFLOW_MODEL_URI con la URI runs:/ o models:/ de Databricks."
        )

    destination = export_model(model_uri)
    print(f"Modelo MLflow descargado en {destination}")


if __name__ == "__main__":
    main()
