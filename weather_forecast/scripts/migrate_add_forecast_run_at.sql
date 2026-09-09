-- Migration: add forecast_run_at to weather_forecast for proper accuracy tracking (T10)
-- Without this column, all forecast rows look identical regardless of when they were
-- inserted. With it, we can JOIN forecast rows with actuals and filter to only those
-- predictions that were made in the past (forecast_run_at < hour).
--
-- Idempotent: safe to run multiple times.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'weather_forecast' AND column_name = 'forecast_run_at'
    ) THEN
        ALTER TABLE weather_forecast
            ADD COLUMN forecast_run_at TIMESTAMP DEFAULT NOW();
        RAISE NOTICE 'Added forecast_run_at column';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_weather_forecast_run_at'
    ) THEN
        CREATE INDEX idx_weather_forecast_run_at
            ON weather_forecast(forecast_run_at);
        RAISE NOTICE 'Created idx_weather_forecast_run_at';
    END IF;
END
$$;