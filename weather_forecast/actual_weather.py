"""
Fetch observed weather for Colombian municipalities from Open-Meteo Archive API.

Mirrors forecast.py structure but pulls ACTUAL values (historical observations) 
instead of forecasts. Used by T10 (accuracy tracking) to compare predictions 
vs reality.

API: https://archive-api.open-meteo.com/v1/archive

Usage:
    python actual_weather.py                       # all 1,122 mpios, past 7 days
    python actual_weather.py --limit 5             # smoke test
    python actual_weather.py --cities 70001,11001  # specific codes
    python actual_weather.py --days 7              # how many days back (default 7)
    python actual_weather.py --rate 0.2            # seconds between requests
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("actual_pipeline.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "colombia.json"

API_BASE = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m"
)
MAX_ATTEMPTS = 3
RETRY_DELAY_S = 5


def load_cities(limit=None, only_codes=None):
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


def fetch_actual(city, start_date, end_date, rate):
    """Fetch observed hourly weather from Archive API for one city."""
    url = (
        f"{API_BASE}?latitude={city['latitude']}&longitude={city['longitude']}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&hourly={HOURLY_VARS}"
    )
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = requests.get(url, timeout=20)
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
                    f"Attempt {attempt}/{MAX_ATTEMPTS} [{city['name']}]: missing keys"
                )
            else:
                logging.warning(
                    f"Attempt {attempt}/{MAX_ATTEMPTS} [{city['name']}]: status {r.status_code}"
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
    """Insert observed rows with ON CONFLICT (city, hour) DO NOTHING (idempotent re-runs)."""
    sql = (
        "INSERT INTO weather_actual "
        "(city, hour, temperature, sens, humidity, wind_speed) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (city, hour) DO NOTHING"
    )
    name = city["name"]
    inserted = 0
    for h, t, s, hu, w in zip(hours, temps, sens, hum, wind):
        cursor.execute(sql, (name, h, t, s, hu, w))
        inserted += cursor.rowcount
    conn.commit()
    return inserted, len(hours)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, help="only first N cities")
    p.add_argument("--cities", help="comma-separated DANE codes")
    p.add_argument("--days", type=int, default=7,
                   help="days back from yesterday (default 7, max ~7 for free tier)")
    p.add_argument("--rate", type=float, default=0.3,
                   help="seconds between requests (default 0.3)")
    args = p.parse_args()

    days = min(args.days, 7)  # Archive free tier cap
    end_date = (date.today() - timedelta(days=1)).isoformat()
    start_date = (date.today() - timedelta(days=days + 1)).isoformat()

    cities = load_cities(limit=args.limit, only_codes=args.cities)

    logging.info("=" * 60)
    logging.info(
        f"Actual pipeline: {len(cities)} cities, "
        f"range {start_date} to {end_date}, rate={args.rate}s"
    )
    logging.info("=" * 60)

    try:
        conn = connect_db()
        cursor = conn.cursor()
        logging.info("DB connected")
    except Exception as e:
        logging.critical(f"DB connection failed: {e}")
        sys.exit(1)

    success = failed = skipped = 0
    inserted = 0
    start = time.time()

    for idx, city in enumerate(cities, 1):
        name = city["name"]
        try:
            data = fetch_actual(city, start_date, end_date, args.rate)
            if data is None:
                failed += 1
                logging.warning(f"[{idx}/{len(cities)}] {name}: FAILED")
            else:
                hours, temps, sens, hum, wind = data
                if not hours:
                    skipped += 1
                    logging.warning(f"[{idx}/{len(cities)}] {name}: empty response")
                else:
                    ins, total = insert_batch(cursor, conn, city, hours, temps, sens, hum, wind)
                    inserted += ins
                    success += 1
                    logging.info(f"[{idx}/{len(cities)}] {name}: {ins}/{total} inserted")
        except Exception as e:
            failed += 1
            logging.error(f"[{idx}/{len(cities)}] {name}: {e}")

        if idx < len(cities):
            time.sleep(args.rate)

    elapsed = time.time() - start
    logging.info("=" * 60)
    logging.info(
        f"Actual pipeline finished in {elapsed/60:.1f} min — "
        f"success={success}, failed={failed}, skipped={skipped}, "
        f"rows_inserted={inserted}"
    )
    logging.info("=" * 60)

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()