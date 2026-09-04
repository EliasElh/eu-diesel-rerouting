"""Enrich the cleaned flow table with partner and reporter names.

Adds:
  - partnerName, iso3, is_special_partner (from data/reference/partners.parquet)
  - reporterName (from src.reporters.REPORTERS)

All rows are kept, including special/unspecified-origin partners, so total
import volumes stay accurate. is_special_partner lets later analysis exclude
these rows from country-level breakdowns without ever dropping the tonnage
from totals.

Run from project root:  python -m src.enrich
"""

from pathlib import Path

import pandas as pd

from src.reporters import REPORTERS

PROCESSED_DIR = Path("data/processed")
REFERENCE_DIR = Path("data/reference")


def main() -> None:
    detail = pd.read_parquet(PROCESSED_DIR / "flows_detail.parquet")
    partners = pd.read_parquet(REFERENCE_DIR / "partners.parquet")

    # join partner names (left join: keep every row, even if unmatched)
    detail = detail.merge(partners, on="partnerCode", how="left")

    # add reporter names too, from the small dict we already have in memory
    detail["reporterName"] = detail["reporterCode"].map(REPORTERS)

    # --- sanity checks -------------------------------------------------
    unmatched_partners = detail[detail["partnerName"].isna()]["partnerCode"].unique()
    unmatched_reporters = detail[detail["reporterName"].isna()]["reporterCode"].unique()
    assert len(unmatched_partners) == 0, f"unmatched partnerCodes: {unmatched_partners}"
    assert len(unmatched_reporters) == 0, f"unmatched reporterCodes: {unmatched_reporters}"

    # --- report on special (unspecified-origin) partners ----------------
    total_t = detail["netWgt"].sum() / 1000
    special_t = detail.loc[detail["is_special_partner"], "netWgt"].sum() / 1000
    print(f"Total detail volume: {total_t:,.0f} t")
    print(f"Special-partner volume: {special_t:,.0f} t "
          f"({special_t / total_t * 100:.2f}% of total)")

    out_path = PROCESSED_DIR / "flows_detail_named.parquet"
    detail.to_parquet(out_path, index=False)
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()