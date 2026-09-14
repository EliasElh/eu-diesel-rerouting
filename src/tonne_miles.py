"""Q3 deliverable: tonne-miles of EU extra-zone diesel imports, monthly.

Joins flows (extra-zone origins only) with the hand-built distance
reference table, computes tonne-nautical-miles per month, and compares
average monthly tonne-miles before vs. after the embargo -- the concrete
measure of how much more shipping capacity the EU's diesel supply now
requires, given the shift to distant suppliers.

Note: 4.4% of extra-zone volume comes from countries outside the 18-country
distance reference (long tail beyond our coverage cutoff) and is excluded
from this specific calculation -- documented, not silently dropped.

Run from project root:  python -m src.tonne_miles
"""

from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path("data/diesel.duckdb")
OUT_PATH = Path("docs/tonne_miles.csv")

EMBARGO_YEAR, EMBARGO_MONTH = 2023, 2


def main() -> None:
    con = duckdb.connect(str(DB_PATH))

    monthly = con.execute("""
        SELECT
            f.refYear, f.refMonth,
            SUM(f.netWgt / 1000) AS extra_zone_tonnes,
            SUM(f.netWgt / 1000 * d.nm_to_rotterdam) AS tonne_nm,
            SUM(f.netWgt / 1000 * d.nm_to_rotterdam)
                / SUM(f.netWgt / 1000) AS avg_distance_nm
        FROM flows f
        JOIN distances d ON f.partnerName = d.partnerName
        WHERE f.is_special_partner = false
          AND f.partnerCode NOT IN (SELECT DISTINCT reporterCode FROM flows)
        GROUP BY f.refYear, f.refMonth
        ORDER BY f.refYear, f.refMonth
    """).fetchdf()

    con.close()

    monthly["date"] = pd.to_datetime(
        monthly["refYear"].astype(str) + "-" + monthly["refMonth"].astype(str) + "-01"
    )
    monthly = monthly.sort_values("date").reset_index(drop=True)
    monthly.to_csv(OUT_PATH, index=False)

    embargo_date = pd.Timestamp(EMBARGO_YEAR, EMBARGO_MONTH, 1)
    before = monthly[monthly["date"] < embargo_date]
    after = monthly[monthly["date"] >= embargo_date]

    print(f"Months before embargo: {len(before)}, after: {len(after)}")
    print(f"\nAvg monthly tonne-miles before: {before['tonne_nm'].mean():,.0f}")
    print(f"Avg monthly tonne-miles after:  {after['tonne_nm'].mean():,.0f}")
    increase_pct = (
        (after["tonne_nm"].mean() - before["tonne_nm"].mean())
        / before["tonne_nm"].mean() * 100
    )
    print(f"Increase: {increase_pct:+.1f}%")

    print(f"\nAvg weighted distance before (nm): {before['avg_distance_nm'].mean():,.0f}")
    print(f"Avg weighted distance after (nm):  {after['avg_distance_nm'].mean():,.0f}")

    print(f"\nFull monthly table written to {OUT_PATH}")


if __name__ == "__main__":
    main()