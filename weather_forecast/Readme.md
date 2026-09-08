# Weather Forecast Monitor — Colombia

End-to-end ETL pipeline that pulls hourly weather forecasts for **all 1,122 municipalities of Colombia** from the Open-Meteo API, persists them in PostgreSQL, and visualizes the data with Streamlit.

Built as a portfolio project demonstrating automation mastery across DA work: extraction, validation, persistence, visualization, and scheduled execution.

---

## Demo

![dashboard preview](docs/preview.webp)

---

## Index

- [Why this project](#why-this-project)
- [Architecture](#architecture)
- [Stack](#stack)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Project structure](#project-structure)
- [Roadmap](#roadmap)

---

## Why this project

Demonstrates a production-shaped data pipeline at small scale:

- Automated extraction from a public API (Open-Meteo)
- Configuration-driven coverage — switch from 6 cities to all 1,122 Colombian municipalities by changing one file
- Idempotent persistence (re-runs skip existing rows instead of failing)
- Per-row retry logic with backoff
- Interactive visualization filterable by municipality

---

## Architecture

```
┌──────────────────┐      ┌────────────┐      ┌──────────────┐      ┌──────────────┐
│  DANE MGN 2025   │      │ Extraction │      │ Persistence  │      │  Streamlit   │
│  1,122 mpios Geo │ ───▶ │  (Python)  │ ───▶ │  (Postgres)  │ ───▶ │  Dashboard   │
└──────────────────┘      └────────────┘      └──────────────┘      └──────────────┘
        │                         │                    │
        ▼                         ▼                    ▼
┌──────────────────┐      ┌────────────┐      ┌──────────────┐
│ config/colombia. │      │   Retry /  │      │   ON CONFLICT│
│       json       │      │ Rate limit │      │  DO NOTHING  │
└──────────────────┘      └────────────┘      └──────────────┘
```

**Data flow:**

1. `scripts/fetch_colombia_geojson.py` fetches the official DANE municipalities GeoJSON, computes centroids, and writes `config/colombia.json` (217KB, ~1,122 entries)
2. `forecast.py` iterates over each municipality in `config/colombia.json`, calls the Open-Meteo forecast API (7 days past + 7 days forecast, hourly), and writes rows to Postgres
3. `analizer.py` (Streamlit) reads from Postgres, lets the user pick any municipality, and renders the forecast

---

## Stack

| Layer | Tool |
|---|---|
| Language | Python 3.11+ |
| Extraction | `requests`, Open-Meteo API |
| Geo data | DANE Marco Geoestadístico Nacional 2025 (ArcGIS REST layer 317) |
| Persistence | PostgreSQL 18 |
| Visualization | Streamlit |
| Charts | Streamlit native (`st.line_chart`) |
| Containerization | Docker (Dockerfile + image on Docker Hub optional) |
| CI / Scheduling | GitHub Actions (planned) |

---

## Features

- **1,122 Colombian municipalities** — full national coverage from a single config file
- **7 days historical + 7 days forecast** per city (336 hourly records per run)
- **Idempotent inserts** via `ON CONFLICT (city, hour) DO NOTHING` — safe to re-run
- **Per-city retry** with exponential-friendly backoff (3 attempts, 5s delay)
- **Rate limiting** (`--rate` flag, default 0.5s) to respect Open-Meteo's fair-use policy
- **Filterable Streamlit UI** — search by name or department, dropdown over 1,122 options
- **Config-driven coverage** — `--limit`, `--cities`, default = all

---

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- pip

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/Sinlens/weather_forecast.git
cd weather_forecast

# 2. Create venv
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your Postgres credentials

# 5. (Optional) Regenerate the municipalities config
python scripts/fetch_colombia_geojson.py

# 6. Apply the DB schema migration
psql -h <host> -U <user> -d <db> -f scripts/migrate_unique_city_hour.sql

# 7. Run the pipeline
python forecast.py --rate 0.2

# 8. Launch the dashboard
streamlit run analizer.py
```

Dashboard runs at `http://localhost:8501`.

---

## Usage

### CLI arguments

```bash
python forecast.py                  # all 1,122 municipalities (~30 min at --rate 0.2)
python forecast.py --limit 10       # first 10 (smoke test, ~30s)
python forecast.py --cities 70001,11001   # specific DANE codes (Sincelejo, Bogotá)
python forecast.py --rate 0.3       # seconds between requests (default 0.5)
```

### Useful SQL queries

```sql
-- Latest forecast per city
SELECT DISTINCT ON (city) city, hour, temperature, sens, humidity, wind_speed
FROM weather_forecast
ORDER BY city, hour DESC;

-- Cities with data coverage
SELECT city, COUNT(*) AS rows, MIN(hour) AS from_, MAX(hour) AS to_
FROM weather_forecast
GROUP BY city
ORDER BY rows DESC;
```

---

## Project structure

```
weather_forecast/
├── analizer.py                       # Streamlit dashboard
├── forecast.py                       # Multi-city extraction pipeline
├── requirements.txt
├── Dockerfile                        # Container build (FROM python:3.11-slim)
├── .env.example                      # Template for credentials (DB_HOST, etc.)
├── .gitignore
├── Readme.md
├── config/
│   └── colombia.json                 # 1,122 municipalities with centroids (217KB)
├── data/
│   └── raw/                          # GeoJSON cache (gitignored, regenerable)
├── docs/
│   └── preview.webp                  # Dashboard screenshot
├── scripts/
│   ├── fetch_colombia_geojson.py     # DANE → colombia.json
│   └── migrate_unique_city_hour.sql  # DB schema migration (idempotent)
└── pipeline.log                      # Rolling log (gitignored)
```

---

## Roadmap

### Done

- [x] Multi-city pipeline (1,122 Colombian municipalities)
- [x] Real forecast API (not archive) — aligns table semantics
- [x] Idempotent inserts via `ON CONFLICT (city, hour) DO NOTHING`
- [x] Retry loop with backoff
- [x] Config-driven coverage from official DANE source
- [x] Filterable Streamlit dashboard

### Next (T10-T12)

- [ ] Accuracy tracking: compare forecast vs. actuals (Open-Meteo Archive API) with MAE per city
- [ ] pytest scaffold + GitHub Actions CI (lint + tests on push)
- [ ] Scheduled extraction via GitHub Actions cron (every 6h)
- [ ] Streamlit Cloud public deploy

### Beyond

- [ ] Public Notion case study
- [ ] More weather variables (precipitation, UV, cloud cover)
- [ ] Anomaly detection (alert when forecast diverges from historical patterns)
- [ ] LinkedIn post showcasing the 1,122-city coverage

---

## Author

Sinlens — marioa0704@gmail.com

## License

MIT