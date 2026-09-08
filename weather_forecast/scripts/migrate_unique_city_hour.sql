-- Migration: change UNIQUE constraint on weather_forecast
-- Old: UNIQUE (hour)  → breaks with multi-city (two cities at same hour conflict)
-- New: UNIQUE (city, hour) → allows same hour for different cities
--
-- The city column already exists (added in a previous session).
-- Existing data (all Sincelejo, June 2026 from archive API) is preserved.
--
-- Idempotent: safe to run multiple times.

DO $$
BEGIN
    -- Drop old UNIQUE constraint if it exists
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'weather_forecast_hour_key'
    ) THEN
        ALTER TABLE weather_forecast DROP CONSTRAINT weather_forecast_hour_key;
        RAISE NOTICE 'Dropped weather_forecast_hour_key';
    END IF;

    -- Add new composite UNIQUE if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'weather_forecast_city_hour_key'
    ) THEN
        ALTER TABLE weather_forecast
            ADD CONSTRAINT weather_forecast_city_hour_key UNIQUE (city, hour);
        RAISE NOTICE 'Added weather_forecast_city_hour_key';
    END IF;

    -- Index on city alone (for Streamlit queries filtering by city)
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_weather_forecast_city'
    ) THEN
        CREATE INDEX idx_weather_forecast_city ON weather_forecast(city);
        RAISE NOTICE 'Created idx_weather_forecast_city';
    END IF;
END
$$;