"""Download and cache the Comtrade partner reference table.

The partner list has ~250 entries -- far too many to hand-type like we did
for the 30 reporters. This script downloads the official reference file
once, saves a local copy, and builds a lookup table (partner code -> name).

A partner is flagged as "special" (not a real single country/territory) if
its name is a regional catch-all ending in ", nes" (not elsewhere specified),
or if it's one of a few known administrative placeholder codes (Bunkers,
Free Zones, Special Categories). Real territories without an official ISO
code -- e.g. Kosovo, Midway Islands -- are correctly kept as real countries.

Run from project root:  python -m src.reference
"""

import json
from pathlib import Path

import pandas as pd
import requests

REFERENCE_DIR = Path("data/reference")
PARTNERS_URL = "https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json"
PARTNERS_RAW_PATH = REFERENCE_DIR / "partners_raw.json"
PARTNERS_TABLE_PATH = REFERENCE_DIR / "partners.parquet"

# Administrative placeholders that are not "xxx, nes" by name but aren't
# real countries either -- found by reading the reference file.
NON_COUNTRY_CODES = {837, 838, 839}  # Bunkers, Free Zones, Special Categories


def download_partners() -> None:
    """Download the raw reference file once, cache it locally."""
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    if PARTNERS_RAW_PATH.exists():
        print(f"{PARTNERS_RAW_PATH} already exists, skipping download")
        return
    print("Downloading partner reference table from Comtrade...")
    response = requests.get(PARTNERS_URL, timeout=60)
    response.raise_for_status()
    with open(PARTNERS_RAW_PATH, "w", encoding="utf-8") as f:
        json.dump(response.json(), f)
    print(f"Saved raw reference to {PARTNERS_RAW_PATH}")


def build_partners_table() -> pd.DataFrame:
    """Turn the raw reference file into a clean lookup table."""
    download_partners()
    with open(PARTNERS_RAW_PATH, encoding="utf-8") as f:
        payload = json.load(f)

    df = pd.DataFrame(payload["results"])
    df = df.rename(columns={
        "PartnerCode": "partnerCode",
        "PartnerDesc": "partnerName",
        "PartnerCodeIsoAlpha2": "iso2",
        "PartnerCodeIsoAlpha3": "iso3",
    })

    is_nes_region = df["partnerName"].str.contains(", nes", case=False, na=False)
    is_known_placeholder = df["partnerCode"].isin(NON_COUNTRY_CODES)
    df["is_special_partner"] = is_nes_region | is_known_placeholder

    df = df[["partnerCode", "partnerName", "iso2", "iso3", "is_special_partner"]]
    df.to_parquet(PARTNERS_TABLE_PATH, index=False)
    return df


if __name__ == "__main__":
    df = build_partners_table()
    print(f"Partner table built: {len(df)} entries")
    print(f"Flagged as special: {df['is_special_partner'].sum()}")
    print("\nSpecial entries:")
    print(df[df["is_special_partner"]][["partnerCode", "partnerName"]]
          .to_string(index=False))
    print(f"\nSaved to {PARTNERS_TABLE_PATH}")