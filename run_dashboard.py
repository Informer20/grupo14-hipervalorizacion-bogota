"""Arranca la API MLflow y el dashboard como procesos coordinados."""

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from api.model.config import PACKAGED_MODEL_DIR


PROJECT_ROOT = Path(__file__).resolve().parent
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"
API_HOST = "127.0.0.1"
API_PORT = int(os.getenv("URBAN_AI_API_PORT", "8001"))
API_HEALTH_URL = f"http://{API_HOST}:{API_PORT}/health"
API_STARTUP_TIMEOUT_SECONDS = 60


def environment_python(environment_path):
    """Obtiene el ejecutable Python que está dentro de la carpeta indicada."""
    executable_dir = "Scripts" if sys.platform == "win32" else "bin"
    executable_name = "python.exe" if sys.platform == "win32" else "python"
    return environment_path / executable_dir / executable_name


def select_python():
    """Selecciona el intérprete para instalar dependencias y lanzar procesos.

    Respeta el entorno virtual activo; en caso contrario reutiliza ``env-dvc``
    o ``.venv`` si existen, y crea ``.venv`` cuando todavía no hay uno.
    """
    if os.getenv("URBAN_AI_USE_SYSTEM_PYTHON") == "1":
        return Path(sys.executable)

    if sys.prefix != sys.base_prefix:
        return Path(sys.executable)

    for environment_name in ("env-dvc", ".venv"):
        candidate = environment_python(PROJECT_ROOT / environment_name)
        if candidate.is_file():
            return candidate

    environment_path = PROJECT_ROOT / ".venv"
    print("Creando ambiente virtual .venv...", flush=True)
    subprocess.run(
        [sys.executable, "-m", "venv", str(environment_path)],
        cwd=PROJECT_ROOT,
        check=True,
    )
    return environment_python(environment_path)


def wait_for_api(api_process):
    """Espera a que la API confirme que está lista para recibir predicciones.

    Si el proceso termina o la carga del modelo falla, genera un error con
    información para no iniciar el dashboard como si el servicio funcionara.
    """
    deadline = time.monotonic() + API_STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if api_process.poll() is not None:
            raise RuntimeError("La API terminó antes de quedar disponible.")
        try:
            with urlopen(API_HEALTH_URL, timeout=1) as response:
                if response.status == 200:
                    return
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"La API no pudo cargar el modelo MLflow: {detail}"
            ) from error
        except (URLError, TimeoutError):
            time.sleep(1)
    raise TimeoutError(
        f"La API no estuvo disponible en {API_HEALTH_URL} "
        f"después de {API_STARTUP_TIMEOUT_SECONDS} segundos."
    )


def run():
    """Prepara el entorno e inicia la API y el dashboard como procesos locales.

    Primero verifica el modelo configurado, inicia FastAPI y espera su respuesta
    de salud; después inicia Dash. Al cerrar el dashboard, detiene también la
    API. Este lanzador no entrena ni reemplaza el modelo.
    """
    python = select_python()

    if os.getenv("URBAN_AI_SKIP_DEPENDENCY_INSTALL") != "1":
        print("Instalando o verificando dependencias...", flush=True)
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)],
            cwd=PROJECT_ROOT,
            check=True,
        )

    if not (PACKAGED_MODEL_DIR / "MLmodel").is_file() and not os.getenv(
        "MLFLOW_MODEL_URI"
    ):
        raise FileNotFoundError(
            "No se encontró el paquete MLflow ni se configuró MLFLOW_MODEL_URI. "
            "Consulta docs/MLFLOW.md para descargar el modelo."
        )

    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = str(PROJECT_ROOT) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    environment["URBAN_AI_API_URL"] = (
        f"http://{API_HOST}:{API_PORT}/api/v1/predict"
    )

    api_process = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "api.app.main:app",
            "--host",
            API_HOST,
            "--port",
            str(API_PORT),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
    )
    try:
        wait_for_api(api_process)
        print(f"API disponible en {API_HEALTH_URL}", flush=True)
        dashboard_port = int(os.getenv("PORT", "8050"))
        print(
            f"Dashboard disponible en http://127.0.0.1:{dashboard_port}",
            flush=True,
        )
        subprocess.run(
            [str(python), str(PROJECT_ROOT / "dashboard" / "app.py")],
            cwd=PROJECT_ROOT,
            env=environment,
            check=True,
        )
    finally:
        if api_process.poll() is None:
            api_process.terminate()
            try:
                api_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                api_process.kill()
                api_process.wait()


if __name__ == "__main__":
    run()
