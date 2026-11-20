"""Define qué datos debe recibir y devolver el servicio de predicción."""

from pydantic import BaseModel, ConfigDict, Field


class PredictionRequest(BaseModel):
    """Datos necesarios para solicitar el valor de referencia de 2026.

    ``localidad`` debe ser texto. Los valores numéricos deben ser finitos;
    estrato debe ser mayor que 0 y hasta 6, referencias deben ser positivas y
    estaciones/densidad no pueden ser negativas. No se admiten campos extra.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    localidad: str = Field(
        strict=True,
        min_length=1,
        description="Nombre de la localidad tal como aparece en los datos.",
    )
    estrato_predominante: float = Field(
        strict=True,
        gt=0,
        le=6,
        allow_inf_nan=False,
        description="Estrato predominante del barrio, mayor que 0 y hasta 6.",
    )
    v_ref_2025: float = Field(
        strict=True,
        gt=0,
        allow_inf_nan=False,
        description="Valor de referencia 2025 por metro cuadrado.",
    )
    cagr_15_25: float = Field(
        strict=True,
        allow_inf_nan=False,
        description="Crecimiento anual compuesto observado entre 2015 y 2025.",
    )
    num_estaciones_transmilenio: float = Field(
        strict=True,
        ge=0,
        allow_inf_nan=False,
        description="Número de estaciones asociadas al barrio.",
    )
    densidad_airbnb_km2: float = Field(
        strict=True,
        ge=0,
        allow_inf_nan=False,
        description="Anuncios existentes y nuevos divididos por el área en km².",
    )
    area_km2: float = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        description="Área del barrio utilizada para calcular la densidad.",
    )
    num_listings_airbnb: int = Field(
        default=None,
        ge=0,
        description="Anuncios Airbnb existentes antes de agregar el escenario.",
    )


class PredictionResponse(BaseModel):
    """Respuesta con el valor estimado, la versión del modelo y el objetivo."""

    prediction: float
    model_version: str
    target: str = "v_ref_2026"


class HealthResponse(BaseModel):
    """Respuesta de estado de la API y del modelo que tiene disponible."""

    status: str
    model_version: str
