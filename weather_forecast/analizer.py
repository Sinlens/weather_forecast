"""
Streamlit dashboard for weather forecast analysis.

Multi-city version: reads city list from config/colombia.json and adds a
searchable selector in the sidebar. Filters the DB query by selected city.

Usage:
    streamlit run analizer.py
"""
import json
import os
from pathlib import Path

import pandas as pd
import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "colombia.json"

# ---------- data ----------

@st.cache_data
def load_cities():
    """Load municipalities sorted by department + name."""
    if not CONFIG_PATH.exists():
        return []
    cities = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return sorted(cities, key=lambda c: (c["department"], c["name"]))


@st.cache_data(ttl=600)
def load_data(city_name):
    """Fetch forecast data for one city. Cached 10 min."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "postgres"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", "5432"),
        )
        conn.set_client_encoding("UTF8")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT city, hour, sens, humidity, wind_speed, temperature "
            "FROM weather_forecast WHERE city = %s ORDER BY hour",
            (city_name,),
        )
        data = cursor.fetchall()
        df = pd.DataFrame(
            data,
            columns=["City", "Hour", "Sensación térmica", "Humedad",
                     "Velocidad del viento", "Temperatura"],
        )
        return df
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame()
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@st.cache_data(ttl=600)
def load_accuracy(city_name):
    """Fetch MAE metrics for one city from weather_accuracy. Cached 10 min."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "postgres"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", "5432"),
        )
        conn.set_client_encoding("UTF8")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metric, mae, n_samples, computed_at "
            "FROM weather_accuracy WHERE city = %s "
            "ORDER BY computed_at DESC, metric",
            (city_name,),
        )
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        return []
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


# ---------- UI ----------

st.set_page_config(page_title="Weather Forecast Analysis", layout="wide")
st.title("Dashboard de monitoreo de clima")
st.markdown("Pronóstico por municipio de Colombia — datos via Open-Meteo")

cities = load_cities()
if not cities:
    st.error(
        f"No se encontró config/colombia.json. "
        f"Ejecutá scripts/fetch_colombia_geojson.py primero."
    )
    st.stop()

# Sidebar: search + select
with st.sidebar:
    st.header("Ciudad")
    search = st.text_input("Buscar municipio", "").strip().upper()
    if search:
        filtered = [c for c in cities if search in c["name"].upper()
                    or search in c["department"].upper()]
    else:
        filtered = cities
    if not filtered:
        st.warning("Sin resultados")
        st.stop()
    options = [f"{c['name']} ({c['department']})" for c in filtered]
    selection = st.selectbox(
        f"{len(filtered)} municipios",
        options,
        index=0,
    )
    city_name = selection.split(" (")[0]

df_weather = load_data(city_name)

st.subheader(f"{city_name}")
st.caption(
    f"{df_weather['Hour'].min() if not df_weather.empty else 'N/A'} "
    f"→ {df_weather['Hour'].max() if not df_weather.empty else 'N/A'} "
    f"· {len(df_weather)} registros"
)

if df_weather.empty:
    st.warning(
        "No hay datos para esta ciudad. "
        "Ejecutá `python forecast.py --cities <DANE_CODE>` para popularla."
    )
    st.stop()

df_weather["Hour"] = pd.to_datetime(df_weather["Hour"])
df_weather["Temperatura"] = df_weather["Temperatura"].astype(float)
df_weather["Sensación térmica"] = df_weather["Sensación térmica"].astype(float)
df_weather["Humedad"] = pd.to_numeric(df_weather["Humedad"], errors="coerce")
df_weather["Velocidad del viento"] = pd.to_numeric(
    df_weather["Velocidad del viento"], errors="coerce"
)

ultimo = df_weather.iloc[-1]

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Temperatura", f"{ultimo['Temperatura']:.1f} °C")
with col2:
    st.metric("Sensación térmica", f"{ultimo['Sensación térmica']:.1f} °C")
with col3:
    st.metric("Humedad", f"{ultimo['Humedad']:.0f} %")
with col4:
    st.metric("Viento", f"{ultimo['Velocidad del viento']:.1f} m/s")

st.markdown("---")
st.subheader("Comparación de Temperatura y Sensación Térmica")

df_graph = df_weather[["Hour", "Temperatura", "Sensación térmica"]].copy()
df_graph.columns = ["Hora", "Temperatura", "Sensación térmica"]
st.line_chart(data=df_graph, x="Hora",
              y=["Temperatura", "Sensación térmica"])

st.subheader("Humedad y Viento")
df_graph2 = df_weather[["Hour", "Humedad", "Velocidad del viento"]].copy()
df_graph2.columns = ["Hora", "Humedad (%)", "Viento (m/s)"]
st.line_chart(data=df_graph2, x="Hora",
              y=["Humedad (%)", "Viento (m/s)"])

# --- Accuracy (T10) ---
st.markdown("---")
st.subheader("Precisión del forecast (MAE)")

acc_rows = load_accuracy(city_name)
if acc_rows:
    # Show most recent run's MAE per metric
    by_metric = {}
    for metric, mae, n, computed_at in acc_rows:
        if metric not in by_metric:  # first (most recent) per metric
            by_metric[metric] = (mae, n, computed_at)
    cols = st.columns(4)
    metric_labels = {
        "temperature": ("Temperatura", "°C"),
        "sens": ("Sensación térmica", "°C"),
        "humidity": ("Humedad", "%"),
        "wind_speed": ("Viento", "m/s"),
    }
    for col, key in zip(cols, ["temperature", "sens", "humidity", "wind_speed"]):
        with col:
            if key in by_metric:
                mae, n, computed_at = by_metric[key]
                st.metric(
                    metric_labels[key][0],
                    f"{mae:.2f} {metric_labels[key][1]}",
                    delta=f"n={n}",
                )
            else:
                st.metric(metric_labels[key][0], "—")
else:
    st.info(
        "Sin datos de accuracy todavía. MAE se acumula cuando horas pronosticadas "
        "pasan y se comparan con valores reales. Mientras tanto: "
        "`python actual_weather.py --days 7 && python compute_accuracy.py`."
    )

with st.expander("Ver tabla de datos"):
    st.dataframe(df_weather, width="stretch")