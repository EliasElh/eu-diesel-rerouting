"""Download EIA monthly price series: Brent crude and NY Harbor ULSD diesel.

Two official EIA monthly series (already averaged by EIA from daily spot
prices, same convention as their own published data):
  - PET.RBRTE.M                       Brent crude, $/barrel
  - PET.EER_EPD2DXL0_PF4_Y35NY_DPG.M  NY Harbor ULSD diesel, $/gallon

Raw JSON responses are cached in data/raw/ (untouched, same principle as
Comtrade). A tidy monthly table is written to data/processed/eia_prices.parquet,
restricted to the project's study period (2019-01 to 2025-12, matching the
Comtrade cutoff decided earlier).

Run from project root:  python -m src.ingest_eia
"""

import json
import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("EIA_API_KEY")

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

SERIES = {
    "brent_usd_bbl": "PET.RBRTE.M",
    "diesel_usd_gal": "PET.EER_EPD2DXL0_PF4_Y35NY_DPG.M",
}

START_PERIOD = "2019-01"
END_PERIOD = "2025-12"


def fetch_series(series_id: str) -> dict:
    url = f"https://api.eia.gov/v2/seriesid/{series_id}"
    response = requests.get(url, params={"api_key": API_KEY}, timeout=60)
    response.raise_for_status()
    return response.json()


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    frames = []
    for col_name, series_id in SERIES.items():
        raw_path = RAW_DIR / f"eia_{col_name}.json"
        if raw_path.exists():
            print(f"{raw_path} already exists, skipping download")
            with open(raw_path, encoding="utf-8") as f:
                payload = json.load(f)
        else:
            print(f"Fetching {series_id}...")
            payload = fetch_series(series_id)
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)

        rows = payload["response"]["data"]
        df = pd.DataFrame(rows)[["period", "value"]].rename(columns={"value": col_name})
        frames.append(df)

    # merge both series side by side, matched on the shared "period" column
    merged = frames[0].merge(frames[1], on="period", how="outer")

    # "period" strings are zero-padded (YYYY-MM), so plain string comparison
    # sorts and filters correctly -- no need to parse dates for this
    merged = merged[(merged["period"] >= START_PERIOD) & (merged["period"] <= END_PERIOD)]

    merged[["refYear", "refMonth"]] = merged["period"].str.split("-", expand=True).astype(int)
    merged = merged.drop(columns="period").sort_values(["refYear", "refMonth"]).reset_index(drop=True)

    n_missing = merged[["brent_usd_bbl", "diesel_usd_gal"]].isna().sum().sum()
    assert n_missing == 0, f"missing prices in study period: {n_missing}"

    print(f"Rows in study period ({START_PERIOD} to {END_PERIOD}): {len(merged)}")
    print(merged.head())
    print(merged.tail())

    out_path = PROCESSED_DIR / "eia_prices.parquet"
    merged.to_parquet(out_path, index=False)
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()