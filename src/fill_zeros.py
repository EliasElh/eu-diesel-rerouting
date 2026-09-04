"""Fill in explicit zero-flow rows for published-but-silent reporter-months.

Comtrade never writes a row for a zero flow -- it simply omits it. This
creates a trap: a missing (reporter, month, partner) row can mean either
"this partner imported nothing that month" (a true zero) or "this reporter
didn't publish that month at all" (unknown, not a zero).

We distinguish the two per reporter:
  - "published months" = months where this reporter has AT LEAST ONE row,
    for any partner. Proves the reporter was reporting that month.
  - "known partners" = every partner this reporter has EVER reported from,
    across the whole period.
  - expected grid = published months x known partners.
  - any cell in that grid missing from the real data -> explicit netWgt=0.

Months where a reporter published nothing at all (e.g. Austria in most
years) are never touched: we don't invent data we don't have.

Run from project root:  python -m src.fill_zeros
"""

from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path("data/processed")


def fill_zeros_for_one_reporter(g: pd.DataFrame) -> pd.DataFrame:
    """g = all rows for a single reporterCode. Return g with zero rows added."""
    reporter_code = g.name
    reporter_name = g["reporterName"].iloc[0]

    published_months = g[["refYear", "refMonth"]].drop_duplicates()
    known_partners = g["partnerCode"].unique()

    expected = published_months.merge(pd.DataFrame({"partnerCode": known_partners}), how="cross")

    key_cols = ["refYear", "refMonth", "partnerCode"]
    merged = expected.merge(g[key_cols + ["netWgt"]], on=key_cols, how="left")
    missing = merged[merged["netWgt"].isna()].copy()
    missing["netWgt"] = 0.0
    missing["reporterCode"] = reporter_code
    missing["reporterName"] = reporter_name

    # carry over partner reference info (name, iso codes, special flag) --
    # these depend only on partnerCode, so we look them up from g itself
    partner_lookup = (
        g[["partnerCode", "partnerName", "iso2", "iso3", "is_special_partner"]]
        .drop_duplicates("partnerCode")
    )
    missing = missing.merge(partner_lookup, on="partnerCode", how="left")

    result = pd.concat([g, missing], ignore_index=True)
    result["reporterCode"] = reporter_code
    return result


def main() -> None:
    detail = pd.read_parquet(PROCESSED_DIR / "flows_detail_named.parquet")
    n_before = len(detail)

    filled = (
        detail.groupby("reporterCode", group_keys=False)
        .apply(fill_zeros_for_one_reporter)
    )

    n_added = len(filled) - n_before
    print(f"Rows before: {n_before:,}")
    print(f"Zero rows added: {n_added:,}")
    print(f"Rows after: {len(filled):,}")

    # sanity check: Netherlands-Russia should now show a full, unbroken series
    check = filled[(filled["reporterCode"] == 528) & (filled["partnerCode"] == 643)]
    check = check.sort_values(["refYear", "refMonth"])
    n_zero = (check["netWgt"] == 0).sum()
    print(f"\nNL-Russia rows: {len(check)}, of which zero-filled: {n_zero}")

    filled.to_parquet(PROCESSED_DIR / "flows_detail_filled.parquet", index=False)
    print(f"\nWritten to {PROCESSED_DIR}/flows_detail_filled.parquet")


if __name__ == "__main__":
    main()