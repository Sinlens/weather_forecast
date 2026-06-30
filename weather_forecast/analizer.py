import streamlit as st
import pandas as pd
import psycopg2

#Setting up the Streamlit page configuration
st.set_page_config(page_title="Weather Forecast Analysis", layout="wide")
st.title("dashboard de monitoreo de clima")
st.markdown("visualización de datos meteorológicos para la ciudad de Sincelejo")

st.selectbox("Seleccione la ciudad", ["Sincelejo"])  # Dropdown for city selection

def load_data():
    try:
        #Connecting to the database
        conn = psycopg2.connect(
            host="localhost",
            database="postgres",
            user="postgres",
            password="Akira123",
            port="5432"
        )
        conn.set_client_encoding('UTF8')
        cursor = conn.cursor()
        
        #Fetching data from the database
        cursor.execute("SELECT city, hour, sens, humidity, wind_speed, temperature FROM weather_forecast")
        data = cursor.fetchall()
        
        #Creating a DataFrame from the fetched data
        df = pd.DataFrame(data, columns=['City', 'Hour', 'Sensación térmica', 'Humedad', 'Velocidad del viento', 'Temperatura'])
        return df
    except Exception as e:
        st.error(f"An error occurred while loading data: {e}")
        return pd.DataFrame()  # Return an empty DataFrame in case of error
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

#Loading data from the database            
df_weather = load_data()


if not df_weather.empty:
    df_weather['Hour'] = pd.to_datetime(df_weather['Hour'])
    
    ultimo_registro = df_weather.iloc[-1]
    
    df_weather['Temperatura'] = df_weather['Temperatura'].astype(float)
    df_weather['Sensación térmica'] = df_weather['Sensación térmica'].astype(float)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(label="Temperatura", value=f"{ultimo_registro['Temperatura']} °C")    
    with col2:
        st.metric(label="Sensación térmica", value=f"{ultimo_registro['Sensación térmica']} °C")
    with col3: 
        st.metric(label="Humedad", value=f"{ultimo_registro['Humedad']} %")
    with col4:
        st.metric(label="Velocidad del viento", value=f"{ultimo_registro['Velocidad del viento']} m/s")
    st.markdown("---")
    # Gráfico comparativo de temperatura y sensación térmica
    st.subheader("Comparación de Temperatura y Sensación Térmica")
    
    columna_fecha = 'Hour'  # o 'hour' si cambiaste la query
    columna_temp = 'Temperatura'      # o 'temperature'
    columna_sens = 'Sensación térmica' # <-- CAMBIA ESTO por 'Sensación térmica' si en Postgres la creaste como 'Sensación térmica'
    df_graph = df_weather[[columna_fecha, columna_temp, columna_sens]].copy()
    df_graph.columns = ['Hora', 'Temperatura', 'Sensación térmica']
    
    st.line_chart(
            data=df_graph,
            x="Hora",
            y=["Temperatura", "Sensación térmica"]
        )  
    # tabla de datos
    with st.expander("Ver tabla de datos"):
        st.dataframe(df_weather)
else:
    st.warning("No se encontraron datos para mostrar. Por favor, asegúrate de que los datos se hayan insertado correctamente en la base de datos.")
