"""
Compute forecast accuracy by joining weather_forecast (predictions) and
weather_actual (observations) on (city, hour).

Outputs MAE (Mean Absolute Error) per city per metric. Inserts results into
weather_accuracy table for historical tracking.

MAE = mean(|predicted - actual|) per metric, per city.

Usage:
    python compute_accuracy.py            # all cities
    python compute_accuracy.py --limit 10 # smoke test
    python compute_accuracy.py --city 'BOGOTA, D.C.'  # single city
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

MAX_ATTEMPTS = 3  # not retried here; just informational


def connect_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )


def ensure_accuracy_table(cursor):
    """Create weather_accuracy table if it doesn't exist (idempotent)."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS weather_accuracy (
            id SERIAL PRIMARY KEY,
            city VARCHAR(255) NOT NULL,
            metric VARCHAR(50) NOT NULL,
            mae FLOAT NOT NULL,
            n_samples INT NOT NULL,
            computed_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT weather_accuracy_city_metric_time_key
                UNIQUE (city, metric, computed_at)
        )
        """
    )


def compute_and_store(cursor, conn, only_city=None):
    """Compute MAE per city per metric. Store results in weather_accuracy.
    Only joins rows where the forecast was made BEFORE the hour being predicted
    (forecast_run_at < hour). Past_days values from the forecast API are observed,
    not predicted, so they would inflate the metric with zero error."""
    where = "WHERE f.forecast_run_at < f.hour"
    params = []
    if only_city:
        where += " AND f.city = %s"
        params = [only_city]

    # JOIN forecast and actual on (city, hour), filter to true predictions
    sql = f"""
        WITH joined AS (
            SELECT
                f.city,
                f.temperature AS f_temp, a.temperature AS a_temp,
                f.sens AS f_sens, a.sens AS a_sens,
                f.humidity AS f_hum, a.humidity AS a_hum,
                f.wind_speed AS f_wind, a.wind_speed AS a_wind
            FROM weather_forecast f
            INNER JOIN weather_actual a
                ON f.city = a.city AND f.hour = a.hour
            {where}
        )
        SELECT
            city,
            'temperature' AS metric,
            AVG(ABS(f_temp - a_temp)) AS mae,
            COUNT(*) AS n
        FROM joined
        WHERE f_temp IS NOT NULL AND a_temp IS NOT NULL
        GROUP BY city
        UNION ALL
        SELECT
            city, 'sens' AS metric,
            AVG(ABS(f_sens - a_sens)) AS mae,
            COUNT(*) AS n
        FROM joined
        WHERE f_sens IS NOT NULL AND a_sens IS NOT NULL
        GROUP BY city
        UNION ALL
        SELECT
            city, 'humidity' AS metric,
            AVG(ABS(f_hum - a_hum)) AS mae,
            COUNT(*) AS n
        FROM joined
        WHERE f_hum IS NOT NULL AND a_hum IS NOT NULL
        GROUP BY city
        UNION ALL
        SELECT
            city, 'wind_speed' AS metric,
            AVG(ABS(f_wind - a_wind)) AS mae,
            COUNT(*) AS n
        FROM joined
        WHERE f_wind IS NOT NULL AND a_wind IS NOT NULL
        GROUP BY city
        ORDER BY city, metric
    """
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    if not rows:
        logging.warning(
            "No matching predictions found. MAE only counts forecast rows where "
            "forecast_run_at < hour (true predictions, not observed past_days). "
            "To populate: run forecast.py with --forecast-days=7 daily, wait for "
            "those hours to pass, then run actual_weather.py + compute_accuracy.py."
        )
        return 0

    # Store with timestamp for historical tracking
    insert_sql = (
        "INSERT INTO weather_accuracy "
        "(city, metric, mae, n_samples) VALUES (%s, %s, %s, %s)"
    )
    for city, metric, mae, n in rows:
        if mae is None:
            continue
        cursor.execute(insert_sql, (city, metric, round(float(mae), 4), n))
    conn.commit()

    # Print summary
    by_city = {}
    for city, metric, mae, n in rows:
        if mae is None:
            continue
        by_city.setdefault(city, {})[metric] = (round(float(mae), 4), n)

    logging.info(f"\n{'City':<35} {'Temp MAE':>10} {'Sens MAE':>10} {'Hum MAE':>10} {'Wind MAE':>10} {'N':>6}")
    logging.info("-" * 90)
    for city in sorted(by_city.keys()):
        m = by_city[city]
        temp = m.get("temperature", (None, 0))
        sens = m.get("sens", (None, 0))
        hum = m.get("humidity", (None, 0))
        wind = m.get("wind_speed", (None, 0))
        n = temp[1] or sens[1] or hum[1] or wind[1]
        def fmt(x): return f"{x[0]:.3f}" if x[0] is not None else "-"
        logging.info(
            f"{city:<35} {fmt(temp):>10} {fmt(sens):>10} {fmt(hum):>10} {fmt(wind):>10} {n:>6}"
        )

    return len(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--city", help="single city (exact match)")
    p.add_argument("--limit", type=int, help="only first N cities (via DB)")
    args = p.parse_args()

    try:
        conn = connect_db()
        cursor = conn.cursor()
        ensure_accuracy_table(cursor)
        conn.commit()
        logging.info("DB connected, weather_accuracy table ready")
    except Exception as e:
        logging.critical(f"DB connection failed: {e}")
        sys.exit(1)

    rows_written = compute_and_store(cursor, conn, only_city=args.city)
    logging.info(f"\nWrote {rows_written} accuracy rows to weather_accuracy")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()