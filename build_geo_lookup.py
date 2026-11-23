"""Rebuild data/geo_lookup.csv from the membership export.

The dashboard plots straight-line distance from a fixed reference address, but the
export has no street addresses, so each member's location is approximated by:

  * US      -> postcode centroid (ZIP+4 trimmed to 5 digits), from GeoNames via pgeocode
  * other   -> city centroid, from OpenStreetMap Nominatim

Run this whenever a new export introduces postcodes or cities that are not yet in the
lookup. Rows already present are preserved, so it is safe to re-run.

    .venv/bin/pip install pgeocode requests
    .venv/bin/python build_geo_lookup.py

Nominatim asks for at most one request per second and a real User-Agent; both are
honoured below. Only locations new to the lookup are queried.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

DATA_PATH = Path(__file__).parent / "data" / "2026-memberships.csv"
LOOKUP_PATH = Path(__file__).parent / "data" / "geo_lookup.csv"

USER_AGENT = {
    "User-Agent": "fprfc-membership-dashboard/1.0 (club membership map; contact s@bolen.co)"
}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
US_NAMES = {"US", "United States"}


def nominatim(query: str) -> tuple[float, float, str] | None:
    resp = requests.get(
        NOMINATIM,
        params={"q": query, "format": "json", "limit": 1},
        headers=USER_AGENT,
        timeout=30,
    )
    resp.raise_for_status()
    hits = resp.json()
    if not hits:
        return None
    top = hits[0]
    return float(top["lat"]), float(top["lon"]), str(top.get("display_name", ""))[:70]


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    for col in ("City", "Postcode", "Country Code"):
        df[col] = df[col].fillna("").astype(str).str.strip()

    df["ISO"] = df["Country Code"].replace({"United States": "US"})
    df["IsUS"] = df["ISO"] == "US"
    df["Zip5"] = df["Postcode"].str.split("-").str[0]

    existing = pd.read_csv(LOOKUP_PATH) if LOOKUP_PATH.exists() else pd.DataFrame(
        columns=["country", "key", "lat", "lon", "source", "label"]
    )
    have = {(r.country, str(r.key)) for r in existing.itertuples()}

    rows: list[dict] = []
    missing: list[str] = []

    us_zips = sorted(df.loc[df.IsUS, "Zip5"].unique())
    todo_zips = [z for z in us_zips if ("US", z) not in have]
    if todo_zips:
        import pgeocode  # imported lazily; downloads GeoNames data on first use

        nomi = pgeocode.Nominatim("us")
        for zip5 in todo_zips:
            hit = nomi.query_postal_code(zip5)
            lat, lon = hit.get("latitude"), hit.get("longitude")
            if pd.isna(lat) or pd.isna(lon):
                missing.append(f"US:{zip5}")
                continue
            rows.append({
                "country": "US", "key": zip5, "lat": float(lat), "lon": float(lon),
                "source": "geonames-postal",
                "label": f"{hit.get('place_name')}, {hit.get('state_code')}",
            })

    intl = (df.loc[~df.IsUS, ["City", "ISO"]].drop_duplicates()
              .sort_values(["ISO", "City"]).values.tolist())
    for city, iso in intl:
        key = str(city).upper()
        if (iso, key) in have:
            continue
        hit = nominatim(f"{city}, {iso}")
        time.sleep(1.2)  # Nominatim rate limit: max 1 request/second
        if hit is None:
            missing.append(f"{iso}:{city}")
            continue
        rows.append({
            "country": iso, "key": key, "lat": hit[0], "lon": hit[1],
            "source": "osm-nominatim", "label": hit[2],
        })

    combined = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    combined = combined.drop_duplicates(subset=["country", "key"], keep="first")
    combined.to_csv(LOOKUP_PATH, index=False, lineterminator="\n")

    print(f"lookup rows : {len(combined)} ({len(rows)} newly geocoded)")
    print(f"written to  : {LOOKUP_PATH}")
    if missing:
        print("NOT geocoded (excluded from the distance average):")
        for item in missing:
            print("  -", item)


if __name__ == "__main__":
    main()
