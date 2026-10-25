# Riesgo de hipervalorización inmobiliaria por gentrificación turística en Bogotá

## 1. Descripción del proyecto

Proyecto académico enfocado en el desarrollo de una solución analítica preventiva orientada a la planificación urbana. El proyecto busca evaluar y simular el impacto de la proliferación de alojamientos turísticos de corta estancia sobre el crecimiento desproporcionado en el valor del suelo en microterritorios (sectores catastrales) clave de Bogotá D.C.

## 2. Objetivo

Estimar el valor comercial actual por metro cuadrado a nivel de barrio mediante un modelo de aprendizaje supervisado (regresión) que integra la presión turística reciente, la inercia histórica de precios y la infraestructura de conectividad urbana. Este modelo alimenta un Producto Mínimo Viable (MVP) compuesto por una API REST de inferencia y un tablero de control interactivo, facultando a las autoridades distritales para evaluar preventivamente el riesgo socioeconómico de la gentrificación turística.

## 3. Fuentes de datos propuestas

* **UAECD (Unidad Administrativa Especial de Catastro Distrital):** Histórico del valor comercial de referencia por metro cuadrado de terreno (serie 2015 a 2026), utilizado para extraer métricas de crecimiento e inercia como la Tasa de Crecimiento Anual Compuesto (CAGR).
* **Inside Airbnb:** Registros georreferenciados de las propiedades activas de alquiler de corta estancia (corte transversal septiembre 2025 - septiembre 2026) para cuantificar la densidad turística.
* **Datos Abiertos Bogotá:** Infraestructura de transporte masivo para georreferenciar y contabilizar las estaciones de TransMilenio por barrio, actuando como variable de control espacial.

## 4. Estructura del repositorio

* `data/`: instrucciones y referencias de los datos.
* `notebooks/`: análisis exploratorio y experimentos.
* `src/`: procesamiento de datos y modelado.
* `tests/`: pruebas del código.
* `api/`: componentes para consultar el modelo.
* `dashboard/`: visualización de resultados.
* `docs/`: documentación del proyecto.

## 5. Tecnologías previstas

Desarrollo fundamentado en Python aplicando buenas prácticas de MLOps. Para garantizar la reproductibilidad técnica y la trazabilidad del sistema, se utiliza Git para el control de versiones del código fuente, Data Version Control (DVC) para el versionado de los conjuntos de datos, y MLflow para el rastreo de experimentos y gestión del ciclo de vida del modelo predictivo. La infraestructura de entrenamiento, almacenamiento y despliegue del MVP se gestionará mediante la nube de Amazon Web Services (AWS).

## 6. Equipo: Grupo 14

* Johan Sebastián Manjarres Diaz
* Sebastián Palomino Delgado
* Laura Valentina Prieto Jiménez
