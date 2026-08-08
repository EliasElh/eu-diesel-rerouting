"""Download raw monthly import data (HS 271019) from the UN Comtrade API.

One API call = one reporter x one year (all partners, all 12 months).
Raw JSON responses are stored untouched in data/raw/, one file per call.
The script is idempotent: existing files are skipped, so it can be
re-run safely after a crash or an interruption.
"""

import json
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

from src.reporters import REPORTERS

# --- 1. Configuration ------------------------------------------------------

load_dotenv()  # reads the .env file at project root
API_KEY = os.getenv("COMTRADE_API_KEY")

BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/M/HS"
CMD_CODE = "271019"          # medium distillates (diesel proxy)
FLOW_CODE = "M"              # imports
YEARS = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019]  # recent first
RAW_DIR = Path("data/raw")

SLEEP_BETWEEN_CALLS = 1.5    # seconds; stay polite with the API
MAX_RETRIES = 3


# --- 2. One API call -------------------------------------------------------

TIMEOUT_SECONDS = 180        # Comtrade can be very slow on wide queries

def fetch_year(reporter_code: int, year: int) -> dict:
    """Call the API for one reporter and one year. Return the parsed JSON."""
    periods = ",".join(f"{year}{month:02d}" for month in range(1, 13))
    params = {
        "reporterCode": reporter_code,
        "period": periods,
        "cmdCode": CMD_CODE,
        "flowCode": FLOW_CODE,
        "subscription-key": API_KEY,
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=TIMEOUT_SECONDS)
        except requests.exceptions.Timeout:
            wait = 20 * attempt
            print(f"  timeout, retrying in {wait}s (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(wait)
            continue
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:          # rate limit hit
            wait = 30 * attempt
            print(f"  rate limited, waiting {wait}s (attempt {attempt})")
            time.sleep(wait)
            continue
        raise RuntimeError(
            f"API error {response.status_code} for reporter={reporter_code} "
            f"year={year}: {response.text[:200]}"
        )
    raise RuntimeError(
        f"Gave up after {MAX_RETRIES} attempts (timeouts or rate limits) "
        f"for reporter={reporter_code} year={year}"
    )


# --- 3. Main loop ----------------------------------------------------------

def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    n_done, n_skipped, n_failed = 0, 0, 0

    for year in YEARS:                       # years first: see design notes
        for code, iso3 in REPORTERS.items():
            out_path = RAW_DIR / f"comtrade_{iso3}_{year}.json"

            if out_path.exists():            # idempotence: never re-download
                n_skipped += 1
                continue

            print(f"Fetching {iso3} {year}...")
            try:
                payload = fetch_year(code, year)
            except RuntimeError as err:
                print(f"  FAILED: {err}")
                n_failed += 1
                continue                     # move on, re-run later for gaps

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            n_done += 1
            time.sleep(SLEEP_BETWEEN_CALLS)

    print(f"\nDone: {n_done} downloaded, {n_skipped} skipped, {n_failed} failed")


if __name__ == "__main__":
    main()