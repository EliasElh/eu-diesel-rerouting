"""One-shot test: download a single reporter/year to validate the pipeline.

Run from project root:  python -m src.test_single_call
Expected result: data/raw/comtrade_NLD_2023.json appears, then a second
run prints 'already exists' and does nothing (idempotence check).
"""

import json
from pathlib import Path

from src.ingest_comtrade import fetch_year, RAW_DIR

TEST_REPORTER_CODE = 528     # Netherlands
TEST_REPORTER_ISO = "NLD"
TEST_YEAR = 2023


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / f"comtrade_{TEST_REPORTER_ISO}_{TEST_YEAR}.json"

    if out_path.exists():
        print(f"{out_path} already exists — idempotence works, nothing to do")
        return

    print(f"Fetching {TEST_REPORTER_ISO} {TEST_YEAR}...")
    payload = fetch_year(TEST_REPORTER_CODE, TEST_YEAR)

    n_rows = payload.get("count", "unknown")
    print(f"Rows received: {n_rows}")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()