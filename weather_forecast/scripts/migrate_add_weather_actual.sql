-- Migration: add weather_actual table for accuracy tracking (T10)
-- Stores observed values from Open-Meteo Archive API for comparison against
-- weather_forecast predictions. Same schema as weather_forecast but with
-- observed_at timestamp for tracking when the data was retrieved.
--
-- Idempotent: safe to run multiple times.

CREATE TABLE IF NOT EXISTS weather_actual (
    id SERIAL PRIMARY KEY,
    city VARCHAR(255) NOT NULL,
    hour TIMESTAMP NOT NULL,
    temperature FLOAT,
    sens FLOAT,
    humidity FLOAT,
    wind_speed FLOAT,
    observed_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT weather_actual_city_hour_key UNIQUE (city, hour)
);

CREATE INDEX IF NOT EXISTS idx_weather_actual_city ON weather_actual(city);