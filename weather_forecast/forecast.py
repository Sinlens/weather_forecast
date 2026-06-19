import requests
import psycopg2

url="https://archive-api.open-meteo.com/v1/archive?latitude=9.3045&longitude=-75.3905&start_date=2026-06-01&end_date=2026-06-15&hourly=temperature_2m"

try:
    #Extracting data from the API
    reponse = requests.get(url)
    data = reponse.json()
    
    hours=data['hourly']['time']
    temps=data['hourly']['temperature_2m']
    city="Sincelejo"
    
    print(f"there is {len(hours)} records to be inserted into the database")
    
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
    
    print("Connected to the database successfully")
    
    #creating the table if it doesn't exist
    cursor.execute("CREATE TABLE IF NOT EXISTS weather_forecast (id SERIAL PRIMARY KEY, city VARCHAR(255), hour TIMESTAMP, temperature FLOAT)")
    
    count=0
    for hour, temp in zip(hours, temps):
        #inserting data into the database
        insert_query = "INSERT INTO weather_forecast (city, hour, temperature) VALUES (%s, %s, %s)"
        cursor.execute(insert_query, (city, hour, temp))
        count+=1
    conn.commit()
    print(f"{count} records inserted successfully")
except Exception as e:
    print(f"An error occurred: {e}")