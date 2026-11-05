import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"
MODEL_PATH = PROJECT_ROOT / "dashboard" / "models" / "catboost_v_ref_2026.cbm"


def environment_python(environment_path):
    executable_dir = "Scripts" if sys.platform == "win32" else "bin"
    executable_name = "python.exe" if sys.platform == "win32" else "python"
    return environment_path / executable_dir / executable_name


def select_python():
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


def run():
    python = select_python()

    print("Instalando o verificando dependencias...", flush=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)],
        cwd=PROJECT_ROOT,
        check=True,
    )

    if not MODEL_PATH.is_file():
        print("Entrenando el modelo CatBoost...", flush=True)
        subprocess.run(
            [str(python), str(PROJECT_ROOT / "dashboard" / "train_model.py")],
            cwd=PROJECT_ROOT,
            check=True,
        )

    print("Iniciando el dashboard en http://127.0.0.1:8050", flush=True)
    subprocess.run(
        [str(python), str(PROJECT_ROOT / "dashboard" / "app.py")],
        cwd=PROJECT_ROOT,
        check=True,
    )


if __name__ == "__main__":
    run()
