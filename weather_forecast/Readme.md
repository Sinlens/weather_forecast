#  Weather Forecast Monitor

Dashboard de monitoreo y análisis de pronóstico climático construido con un pipeline ETL en python y visualización en streamlit. Extrae datos de la APO de Open-Meteo, se transforman para luego ser almacenados y con ello hacer un analisís de pronóstico.

# Demo
![dashboard preview](preview.webp)
---
## Indice

- [Por qué este proyecto](#por-qué-este-proyecto)
- [Arquitectura](#arquitectura)
- [Stack técnico](#stack-técnico)
- [Features](#features)
- [installation](#installation)
- [Uso](#uso)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Roadmap](#Roadmap)

---
## Por qué este proyecto
 
Este proyecto consta de un pipeline de datos end-to-end con la adicción de visualización de los datos. En este proyecto se demuestra:
 
- Extracción automatizada de datos desde una API externa
- Transformación y validación de datos
- Almacenamiento persistente para análisis histórico
- Visualización interactiva orientada a insights, no solo a datos crudos
El objetivo es que el código sea representativo de cómo se construye un pipeline en un entorno de producción real, en una escala pequeña y manejable.
 
---

## Arquitectura
 
```
┌─────────────────┐      ┌──────────────┐      ┌─────────────────┐      ┌───────────────┐
│   Open-Meteo    │ ──▶ │   Extracción  │ ──▶ │ Almacenamiento  │ ──▶ │   Streamlit    │
│   API (Weather) │      │   (Python)   │      │ (PostgreSQL/CSV)│      │   Dashboard   │
└─────────────────┘      └──────────────┘      └─────────────────┘      └───────────────┘
                                  │
                                  ▼
                          ┌──────────────┐
                          │   Logging /  │
                          │   manejo de  │
                          │   errores    │
                          └──────────────┘
```
 
**Flujo de datos:**
 
1. Un script de extracción consulta la API de Open-Meteo para una o varias ciudades
2. Los datos crudos se validan y transforman (tipos, nulos, unidades)
3. Los datos limpios se cargan en postgres
4. Streamlit lee directamente de esa fuente y renderiza el dashboard
5. Cada corrida queda registrada en logs para trazabilidad

 
---
## Stack técnico
 
| Capa | Herramienta |
|---|---|
| Lenguaje | Python 3.14.4 |
| Extracción de datos | `requests`, Open-Meteo API |
| Procesamiento | `Pandas` |
| Almacenamiento | PostgreSQL  |
| Visualización | Streamlit |
| Gráficos | Streamlit|
---
## features
 
- Monitoreo de temperatura para la ciudad en base a coordenadas
- Visualización de la evolución horaria de temperatura
- Tabla de datos meteorológicos consultable
---
## Instalación
 
### Requisitos previos
 
- Python 3.14.4 
- PostgreSQL
- pip
### Pasos
 
```bash
# 1. Clonar el repositorio
git clone https://github.com/Sinlens/weather_forecast.git
cd weather_forecast
 
# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
 
# 3. Instalar dependencias
pip install -r requirements.txt
 
# 4. Configurar variables de entorno
cp .env.example .env
# Edita .env con tus credenciales si usas base de datos
 
# 5. Ejecutar el pipeline de extracción
python etl/extract.py
 
# 6. Lanzar el dashboard
streamlit run app.py
```
 
La aplicación estará disponible en `http://localhost:8501`
 
---
# Uso
 
```bash
# Ejecutar extracción manual de datos
python etl/extract.py --city Sincelejo
 
# Lanzar el dashboard
streamlit run app.py
```
 
[Agrega aquí cualquier parámetro o comando adicional relevante: cambio de ciudad, rango de fechas, etc.]
 
---
## Estructura del proyecto
 
```
weather_forecast/
├── analizer.py               # Aplicación principal
├── forecast.py               # Extractición de datos
├── .gitignore
├── docs/
│   └── dashboard_preview.png
├── requirements.txt
└── README.md
```

 
---
 
## Roadmap
 
Mejoras planeadas para convertir esto en un proyecto de portafolio completo:
 
- [ ] Agregar sensación térmica, humedad y velocidad del viento
- [ ] Implementar seguimiento de precisión del pronóstico (predicho vs. real)
- [ ] Comparación entre múltiples ciudades de Colombia
- [ ] Tests unitarios con pytest
- [ ] Logging estructurado y manejo de errores con reintentos
- [ ] Containerización con Docker y Docker Compose
- [ ] Automatización de la extracción con GitHub Actions
- [ ] Despliegue público en Streamlit Cloud
---
## Autor
Sinlens