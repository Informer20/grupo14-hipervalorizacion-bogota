from pathlib import Path

from catboost import CatBoostRegressor
from sklearn.model_selection import train_test_split

from map_view import load_geodata
from predictor import FEATURE_COLUMNS, MODEL_PATH


TARGET_COLUMN = "v_ref_2026"
MODEL_PARAMETERS = {
    "iterations": 600,
    "learning_rate": 0.04,
    "depth": 6,
    "loss_function": "RMSE",
    "random_seed": 42,
    "verbose": False,
    "allow_writing_files": False,
}


def train_and_save_model():
    geodata = load_geodata()
    missing_columns = set(FEATURE_COLUMNS + [TARGET_COLUMN]) - set(geodata.columns)
    if missing_columns:
        raise ValueError(
            f"Faltan columnas requeridas para entrenar CatBoost: "
            f"{sorted(missing_columns)}"
        )

    training_data = geodata.loc[
        geodata[TARGET_COLUMN].notna(),
        FEATURE_COLUMNS + [TARGET_COLUMN],
    ].copy()
    if training_data[FEATURE_COLUMNS + [TARGET_COLUMN]].isna().any().any():
        raise ValueError("Hay valores faltantes en las variables de entrenamiento.")

    training_data["localidad"] = training_data["localidad"].astype(str)
    x_train, _, y_train, _ = train_test_split(
        training_data[FEATURE_COLUMNS],
        training_data[TARGET_COLUMN],
        test_size=0.2,
        random_state=42,
    )

    model = CatBoostRegressor(**MODEL_PARAMETERS)
    model.fit(
        x_train,
        y_train,
        cat_features=["localidad"],
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_PATH))
    return len(x_train), model


if __name__ == "__main__":
    row_count, _ = train_and_save_model()
    print(
        f"Modelo CatBoost entrenado con {row_count} registros y guardado en "
        f"{Path(MODEL_PATH).relative_to(Path(__file__).resolve().parents[1])}."
    )
