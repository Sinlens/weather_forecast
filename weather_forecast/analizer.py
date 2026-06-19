import streamlit as st
import pandas as pd
import psycopg2

#Setting up the Streamlit page configuration
st.set_page_config(page_title="Weather Forecast Analysis", layout="wide")
st.title("dashboard de monitoreo de clima")
st.markdown("visualización de datos meteorológicos para la ciudad de Sincelejo")

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
        cursor.execute("SELECT city, hour, temperature FROM weather_forecast")
        data = cursor.fetchall()
        
        #Creating a DataFrame from the fetched data
        df = pd.DataFrame(data, columns=['City', 'Hour', 'Temperature'])
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
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Evolución de la temperatura a lo largo del tiempo")
        #Line chart to show temperature evolution over time
        st.line_chart(data=df_weather, x='Hour', y='Temperature')
        
    with col2:
        st.subheader("datos meteorológicos") 
        st.dataframe(df_weather)
else:
    st.warning("No se encontraron datos para mostrar. Por favor, asegúrate de que los datos se hayan insertado correctamente en la base de datos.")         