import requests
import psycopg2
import logging
import time

# setting up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s %(message)s]',
    handlers=[
        logging.FileHandler("pipeline.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

url = "https://archive-api.open-meteo.com/v1/archive?latitude=9.3045&longitude=-75.3905&start_date=2026-06-01&end_date=2026-06-15&hourly=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m"

Max_attempts = 3
Delay_s = 5
Data_api = None

logging.info("Starting the data extraction process")

for attempt in range(1, Max_attempts + 1):
    try:
        logging.info("Getting data from the API")
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            Data_api = response.json()
            logging.info("Data extraction successful")
            break
        else:
            logging.warning(f"The API request failed with status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        logging.error(f"An error occurred during the API request: {e}.")
    
    if attempt < Max_attempts:
        #retrying after a delay if the request fails
        logging.info(f"Retrying in {Delay_s} seconds...")
        time.sleep(Delay_s)
        break
        
if Data_api is None:
        #warning message if the data extraction fails after all attempts
        logging.critical("failed to retrieve data from the API")
else:
    try:
        logging.info("Processing the data and inserting it into the database")
             
        #Connecting to the database
        conn = psycopg2.connect(
            host="localhost",
            database="postgres",
            user="postgres",
            password="Akira123",
            port="5432"
        )    
        hours = Data_api['hourly']['time']
        temps = Data_api['hourly']['temperature_2m']
        sensible_temp=Data_api['hourly']['apparent_temperature']
        humidity=Data_api['hourly']['relative_humidity_2m']
        wind_speed=Data_api['hourly']['wind_speed_10m']
        city="Sincelejo"
    
            
        conn.set_client_encoding('UTF8')
        cursor = conn.cursor()
    
        logging.info("Connected to the database successfully")
    
        #creating the table if it doesn't exist
        cursor.execute("CREATE TABLE IF NOT EXISTS weather_forecast (id SERIAL PRIMARY KEY, city VARCHAR(255), hour TIMESTAMP UNIQUE, temperature FLOAT, sens FLOAT, humidity FLOAT, wind_speed FLOAT)")
    
        count=0
        for hour, temp, sensa, hum, wind in zip(hours, temps, sensible_temp, humidity, wind_speed):
            #inserting data into the database
            insert_query = "INSERT INTO weather_forecast (city, hour, temperature, sens, humidity, wind_speed) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(insert_query, (city, hour, temp, sensa, hum, wind))
            count+=1
            conn.commit()
            logging.info(f"{count} records inserted successfully")
    except Exception as e:
        logging.critical(f"An error occurred: {e}")
    finally:
        if cursor in locals():
            cursor.close()
        if conn in locals():
            conn.close()
        logging.info("Database connection closed")