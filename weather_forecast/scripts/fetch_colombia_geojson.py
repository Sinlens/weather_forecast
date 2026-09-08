"""
Fetch Colombia municipalities from DANE ArcGIS REST API and compute centroids.
Output: config/colombia.json with {dane_code, name, department, lat, lon, type} per municipality.

Source: MGN 2025 - Marco Geoestadístico Nacional, nivel municipio.
Endpoint layer 317 (Municipio).

Centroid: simple average of all polygon vertices across all rings.
For weather forecast lookup the cartographic accuracy (~few km) doesn't matter.
"""
import json
import sys
from pathlib import Path
import requests

ENDPOINT = (
    "https://portalgis.dane.gov.co/mparcgis/rest/services/Hosted/"
    "Serv_Mpio_MGN_2025/FeatureServer/317/query"
)
DST = Path(__file__).resolve().parents[1] / "config" / "colombia.json"


def fetch_features():
    """Fetch all features (paginated if needed)."""
    all_features = []
    offset = 0
    page_size = 2000
    while True:
        params = {
            "where": "1=1",
            "outFields": "dpto_ccdgo,mpio_ccdgo,mpio_cdpmp,dpto_cnmbre,mpio_cnmbre,mpio_tipo",
            "f": "json",
            "returnGeometry": "true",
            "geometryPrecision": 4,
            "outSR": 4326,
            "resultRecordCount": page_size,
            "resultOffset": offset,
        }
        print(f"  page offset={offset}", flush=True)
        r = requests.get(ENDPOINT, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        feats = data.get("features", [])
        all_features.extend(feats)
        if len(feats) < page_size or not data.get("exceededTransferLimit"):
            break
        offset += page_size
    return all_features


def polygon_centroid(rings):
    """Average of vertices across all rings (Esri JSON: rings is list of rings).
    Each ring is list of [x, y] or [lon, lat] since outSR=4326."""
    if not rings:
        return None
    lats, lons = [], []
    for ring in rings:
        for x, y in ring:
            lons.append(x)
            lats.append(y)
    if not lats:
        return None
    return sum(lats) / len(lats), sum(lons) / len(lons)


def main():
    print("Fetching Colombia municipalities from DANE...")
    feats = fetch_features()
    print(f"Got {len(feats)} features")

    out = []
    skipped = 0
    for f in feats:
        a = f["attributes"]
        rings = (f.get("geometry") or {}).get("rings") or []
        centroid = polygon_centroid(rings) if rings else None
        if centroid is None:
            skipped += 1
            continue
        lat, lon = centroid
        out.append({
            "dane_code": a.get("mpio_cdpmp"),
            "dept_code": a.get("dpto_ccdgo"),
            "name": (a.get("mpio_cnmbre") or "").strip(),
            "department": (a.get("dpto_cnmbre") or "").strip(),
            "type": a.get("mpio_tipo"),
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
        })

    out.sort(key=lambda x: x["dane_code"] or "")
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    size_kb = DST.stat().st_size / 1024
    print(f"\nSaved {DST} ({size_kb:.1f} KB, {len(out)} municipalities)")
    if skipped:
        print(f"Skipped {skipped} features with no geometry")

    # Sanity checks
    print("\nFirst 3 entries:")
    for e in out[:3]:
        print(f"  {e}")
    sincelejo = [e for e in out if "SINCEL" in (e["name"] or "").upper()]
    print(f"\nSincelejo matches ({len(sincelejo)}):")
    for s in sincelejo:
        print(f"  {s}")
    bogota = [e for e in out if "BOGOT" in (e["name"] or "").upper()]
    print(f"\nBogotá matches ({len(bogota)}):")
    for b in bogota[:3]:
        print(f"  {b}")
    # Type breakdown
    types = {}
    for e in out:
        types[e["type"]] = types.get(e["type"], 0) + 1
    print(f"\nType breakdown: {types}")


if __name__ == "__main__":
    main()