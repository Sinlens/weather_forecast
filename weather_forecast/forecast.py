"""
Weather forecast pipeline for all Colombia municipalities.

Replaces the original single-city (Sincelejo) script with a multi-city version
that loads 1,122 municipalities from config/colombia.json and queries Open-Meteo's
forecast API for each.

API switch (T9): was archive-api.open-meteo.com (historical data for June 2026),
now api.open-meteo.com (real forecast) — aligns semantics with table name
weather_forecast.

Usage:
    python forecast.py                  # all 1,122 municipalities (~28 min)
    python forecast.py --limit 10       # first 10 (smoke test)
    python forecast.py --cities 70001,11001   # specific DANE codes
    python forecast.py --rate 0.3       # seconds between requests (default 0.5)
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

# ----- logging -----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("pipeline.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# ----- config -----
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "colombia.json"

API_BASE = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m"
)
PAST_DAYS = 7
FORECAST_DAYS = 7
MAX_ATTEMPTS = 3
RETRY_DELAY_S = 5


def load_cities(limit=None, only_codes=None):
    """Load municipalities from config/colombia.json."""
    if not CONFIG_PATH.exists():
        logging.critical(f"Config not found: {CONFIG_PATH}")
        sys.exit(1)
    cities = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if only_codes:
        codes = {c.strip() for c in only_codes.split(",")}
        cities = [c for c in cities if c["dane_code"] in codes]
        if not cities:
            logging.critical(f"No cities matched codes: {only_codes}")
            sys.exit(1)
    elif limit:
        cities = cities[:limit]
    logging.info(f"Loaded {len(cities)} cities from config")
    return cities


def fetch_one(city, rate):
    """Fetch forecast for one city. Returns (hours, temps, sens, hum, wind) or None."""
    url = (
        f"{API_BASE}?latitude={city['latitude']}&longitude={city['longitude']}"
        f"&hourly={HOURLY_VARS}&past_days={PAST_DAYS}&forecast_days={FORECAST_DAYS}"
    )
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                hourly = data.get("hourly", {})
                if all(k in hourly for k in ("time", "temperature_2m", "apparent_temperature",
                                              "relative_humidity_2m", "wind_speed_10m")):
                    return (
                        hourly["time"],
                        hourly["temperature_2m"],
                        hourly["apparent_temperature"],
                        hourly["relative_humidity_2m"],
                        hourly["wind_speed_10m"],
                    )
                logging.warning(
                    f"Attempt {attempt}/{MAX_ATTEMPTS} [{city['name']}]: "
                    f"missing keys in response"
                )
            else:
                logging.warning(
                    f"Attempt {attempt}/{MAX_ATTEMPTS} [{city['name']}]: "
                    f"status {r.status_code}"
                )
        except requests.exceptions.RequestException as e:
            logging.error(
                f"Attempt {attempt}/{MAX_ATTEMPTS} [{city['name']}]: {e}"
            )
        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY_S)
    return None


def connect_db():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )
    conn.set_client_encoding("UTF8")
    return conn


def insert_batch(cursor, conn, city, hours, temps, sens, hum, wind):
    """Insert hourly rows for one city with ON CONFLICT (city, hour) DO NOTHING."""
    sql = (
        "INSERT INTO weather_forecast "
        "(city, hour, temperature, sens, humidity, wind_speed) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (city, hour) DO NOTHING"
    )
    name = city["name"]
    rows = list(zip(hours, temps, sens, hum, wind))
    inserted = 0
    for h, t, s, hu, w in rows:
        cursor.execute(sql, (name, h, t, s, hu, w))
        inserted += cursor.rowcount
    conn.commit()
    return inserted, len(rows)


def ensure_schema(cursor):
    """CREATE TABLE IF NOT EXISTS with composite UNIQUE(city, hour)."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS weather_forecast (
            id SERIAL PRIMARY KEY,
            city VARCHAR(255) NOT NULL,
            hour TIMESTAMP NOT NULL,
            temperature FLOAT,
            sens FLOAT,
            humidity FLOAT,
            wind_speed FLOAT,
            CONSTRAINT weather_forecast_city_hour_key UNIQUE (city, hour)
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_weather_forecast_city "
        "ON weather_forecast(city)"
    )
    # Backfill city='UNKNOWN' for any pre-migration rows with NULL city
    cursor.execute(
        "UPDATE weather_forecast SET city='UNKNOWN' WHERE city IS NULL"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, help="only first N cities")
    p.add_argument("--cities", help="comma-separated DANE codes")
    p.add_argument("--rate", type=float, default=0.5,
                   help="seconds between requests (default 0.5)")
    args = p.parse_args()

    cities = load_cities(limit=args.limit, only_codes=args.cities)

    logging.info("=" * 60)
    logging.info(f"Pipeline starting: {len(cities)} cities, rate={args.rate}s")
    logging.info("=" * 60)

    try:
        conn = connect_db()
        cursor = conn.cursor()
        ensure_schema(cursor)
        conn.commit()
        logging.info("DB connected, schema ensured")
    except Exception as e:
        logging.critical(f"DB connection failed: {e}")
        sys.exit(1)

    success = 0
    failed = 0
    skipped = 0
    total_inserted = 0
    start = time.time()

    for idx, city in enumerate(cities, 1):
        name = city["name"]
        try:
            data = fetch_one(city, args.rate)
            if data is None:
                failed += 1
                logging.warning(f"[{idx}/{len(cities)}] {name}: FAILED after retries")
            else:
                hours, temps, sens, hum, wind = data
                ins, total = insert_batch(cursor, conn, city, hours, temps, sens, hum, wind)
                total_inserted += ins
                if ins == 0:
                    skipped += 1
                else:
                    success += 1
                logging.info(
                    f"[{idx}/{len(cities)}] {name}: {ins}/{total} inserted"
                )
        except Exception as e:
            failed += 1
            logging.error(f"[{idx}/{len(cities)}] {name}: {e}")

        if idx < len(cities):
            time.sleep(args.rate)

    elapsed = time.time() - start
    logging.info("=" * 60)
    logging.info(
        f"Pipeline finished in {elapsed/60:.1f} min — "
        f"success={success}, failed={failed}, skipped={skipped}, "
        f"rows_inserted={total_inserted}"
    )
    logging.info("=" * 60)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()