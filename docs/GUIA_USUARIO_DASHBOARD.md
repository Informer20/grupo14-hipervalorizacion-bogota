# Guía de usuario del dashboard Urban AI

## Para qué sirve

El dashboard permite explorar barrios de Bogotá, consultar indicadores urbanos e inmobiliarios y simular cómo cambia la estimación del valor de referencia por metro cuadrado para 2026 bajo un escenario de nuevos alojamientos.

La aplicación presenta datos territoriales del GeoPackage del proyecto. Al ejecutar una predicción, envía las variables del barrio y el número de nuevos alojamientos a la API, que utiliza el modelo XGBoost configurado para el proyecto. El dashboard no vuelve a entrenar el modelo.

## Cómo abrirlo

Desde la raíz del repositorio, activa el entorno virtual y ejecuta:

```powershell
python run_dashboard.py
```

Abre `http://127.0.0.1:8050` en el navegador. El lanzador necesita que las dependencias y el modelo estén disponibles, ya sea como paquete local o mediante la configuración de MLflow. Si aparece un error relacionado con el modelo o la API, consulta [la guía de MLflow](./MLFLOW.md).

## Recorrido recomendado

1. **Selecciona una localidad.** El selector de barrio se actualiza con los barrios disponibles en esa localidad.
2. **Selecciona un barrio.** El mapa y el contexto territorial corresponden a esa selección.
3. **Define los nuevos alojamientos.** Usa el deslizador para indicar cuántos anuncios hipotéticos agregar al escenario. El máximo se ajusta al barrio seleccionado; el paso es de un alojamiento.
4. **Revisa los umbrales del semáforo.** Puedes conservar los valores iniciales o modificarlos antes de predecir.
5. **Pulsa “Ejecutar predicción”.** Mientras se consulta la API aparece el indicador de carga. Al terminar, revisa la alerta, la ficha de indicadores, el diagnóstico y la comparación gráfica.
6. **Prueba otro escenario.** Cambia el barrio, la localidad o el número de alojamientos y ejecuta de nuevo la predicción. Los resultados corresponden a la combinación seleccionada cuando se solicitó la predicción.

El máximo del deslizador se calcula usando barrios comparables de Bogotá: mismo estrato y valor de referencia 2025 dentro de un margen de aproximadamente 25 %. Se toma el máximo de anuncios de esos barrios, se aumenta 25 % y se redondea hacia arriba. El límite es al menos 5 y como máximo 1.000 alojamientos nuevos. Es un límite práctico para acotar el escenario; no garantiza que el modelo haya sido validado para todos los valores posibles.

## Cómo leer cada sección

### Panel de control de simulación

- **Localidad y barrio:** determinan el territorio consultado.
- **Nuevos alojamientos:** cantidad adicional hipotética para el escenario. No reemplaza ni modifica el conteo de anuncios existentes.
- **Semáforo de riesgo:** compara el crecimiento estimado para 2026 con el valor de referencia de 2025.
- **Ejecutar predicción:** solicita el resultado a la API. Si la API o el modelo no están disponibles, el estado debe mostrar el error recibido.

### Mapa de densidad de alojamientos turísticos

El mapa colorea los sectores catastrales según la densidad de anuncios Airbnb, expresada en propiedades por km². Los tonos más intensos representan mayor densidad en la escala del mapa. El barrio seleccionado se marca con un contorno rojo; al pasar el cursor sobre un sector se muestran sus datos de barrio, localidad, anuncios y densidad.

Después de una predicción, el cursor sobre el barrio seleccionado también puede mostrar el valor estimado para 2026. El mapa es una visualización por sectores; los indicadores de la ficha se agregan para el barrio completo.

### Diagnóstico y contexto del barrio

El texto resume el estrato predominante, el área, los anuncios Airbnb existentes, su densidad, las estaciones de TransMilenio, los valores de referencia de 2025 y el CAGR histórico 2015–2025. Después de predecir, agrega el escenario de nuevos alojamientos, la densidad resultante, el valor estimado para 2026, el crecimiento frente a 2025 y la zona asignada por el semáforo.

### Indicadores del territorio

La ficha técnica presenta las métricas principales:

| Indicador | Cómo interpretarlo |
|---|---|
| Estrato predominante | Estrato que aparece con mayor frecuencia entre los sectores del barrio. |
| Área | Suma de las áreas de los sectores que componen el barrio, en km². |
| Anuncios Airbnb existentes | Suma de los anuncios registrados en los sectores del barrio. |
| Nuevos alojamientos del escenario | Cantidad adicional seleccionada en el deslizador. |
| Densidad Airbnb | Anuncios existentes divididos por el área, en propiedades/km². |
| Densidad del escenario | Anuncios existentes más los nuevos, divididos por el área. |
| Estaciones de TransMilenio | Suma de estaciones asociadas a los sectores del barrio en la matriz. |
| Valor de referencia 2015 y 2025 | Valores históricos de referencia por m²; sirven como contexto y comparación. |
| Valor de referencia 2026 predicho | Estimación del modelo para el escenario elegido, por m². |
| Crecimiento predicho 2026 vs. 2025 | Variación porcentual de la predicción respecto al valor de referencia 2025. |
| CAGR histórico 2015–2025 | Tasa de crecimiento anual compuesto histórica agregada para el barrio; no es la predicción de 2026. |

Para barrios compuestos por varios sectores, área, anuncios y estaciones se suman. El estrato predominante es la moda. Los valores de referencia de 2015 y 2025 y el CAGR se ponderan por área.

### Gráfica de valor de referencia por m²

La gráfica compara el valor de referencia de 2025 con la predicción de 2026, cuando esta ya está disponible. El eje vertical está expresado en **millones de pesos por m²**. La ficha y el diagnóstico muestran los valores completos en pesos. El valor de 2025 es una referencia observada de la matriz, no una predicción.

## Cómo interpretar el semáforo

El porcentaje mostrado se calcula así:

`(valor predicho 2026 / valor de referencia 2025 - 1) × 100`

- **Verde:** crecimiento menor o igual al umbral “Verde hasta (%)”.
- **Amarillo:** crecimiento mayor que el umbral verde y menor o igual al umbral “Rojo desde (%)”.
- **Rojo:** crecimiento estrictamente mayor que el umbral “Rojo desde (%)”.

Los umbrales iniciales se derivan de la distribución histórica del CAGR de los barrios. Son bandas configurables para clasificar el crecimiento estimado; **no son probabilidades de riesgo producidas por el modelo**.

**Nota sobre los campos actuales:** el control “Amarillo hasta (%)” debe ser mayor que el umbral verde y no puede superar “Rojo desde (%)”, pero en la lógica actual no constituye un corte independiente de clasificación. El límite superior efectivo de la zona amarilla es “Rojo desde (%)”. Si los umbrales no cumplen ese orden, el dashboard muestra un mensaje para revisarlos y no asigna una zona.

## Recomendaciones y límites de interpretación

- Cambia los parámetros y vuelve a ejecutar la predicción para que los resultados correspondan al escenario nuevo.
- Distingue entre **anuncios existentes** y **nuevos alojamientos**: estos últimos son una entrada hipotética del escenario.
- Una asociación o variación que muestra el dashboard no demuestra que los alojamientos turísticos causen cambios en los valores inmobiliarios.
- La estimación depende de los datos disponibles, la preparación de variables y el modelo configurado. No debe interpretarse como una tasación individual, una garantía del precio futuro ni una recomendación de inversión.
- Un resultado de crecimiento negativo se compara igualmente con los umbrales configurados; el semáforo clasifica el porcentaje, no la calidad del modelo ni la certeza de la predicción.
