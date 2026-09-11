"""Q1 deliverable: exact monthly market shares by origin (extra-zone only),
and a quantified measure of the transition speed away from Russia.

Uses a SQL window function (SUM() OVER (PARTITION BY ...)) to compute each
origin's percentage share of that month's total extra-zone volume, without
collapsing the per-origin detail -- the classic use case for window functions.

Run from project root:  python -m src.market_share
"""

from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path("data/diesel.duckdb")
OUT_PATH = Path("docs/market_shares.csv")

N_TOP_ORIGINS = 6
EMBARGO_YEAR, EMBARGO_MONTH = 2023, 2
RUSSIA_LOW_THRESHOLD_PCT = 2.0  # "near-zero" cutoff for transition speed


def main() -> None:
    con = duckdb.connect(str(DB_PATH))

    # same top-6 extra-zone origins as the chart, for a consistent story
    top_origins = con.execute("""
        SELECT partnerName
        FROM flows
        WHERE is_special_partner = false
          AND partnerCode NOT IN (SELECT DISTINCT reporterCode FROM flows)
        GROUP BY partnerName
        ORDER BY SUM(netWgt) DESC
        LIMIT %d
    """ % N_TOP_ORIGINS).fetchdf()["partnerName"].tolist()
    top_list_sql = ", ".join(f"'{n}'" for n in top_origins)

    # CTE (monthly) groups tonnes by origin; the outer SELECT uses a window
    # function to divide each row by ITS month's total, without collapsing rows
    shares = con.execute(f"""
        WITH monthly AS (
            SELECT
                refYear, refMonth,
                CASE WHEN partnerName IN ({top_list_sql}) THEN partnerName
                     ELSE 'Other' END AS origin,
                SUM(netWgt) / 1000 AS tonnes
            FROM flows
            WHERE is_special_partner = false
              AND partnerCode NOT IN (SELECT DISTINCT reporterCode FROM flows)
            GROUP BY refYear, refMonth, origin
        )
        SELECT
            refYear, refMonth, origin, tonnes,
            tonnes / SUM(tonnes) OVER (PARTITION BY refYear, refMonth) * 100
                AS share_pct
        FROM monthly
        ORDER BY refYear, refMonth, origin
    """).fetchdf()

    con.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    shares.to_csv(OUT_PATH, index=False)
    print(f"Full monthly share table written to {OUT_PATH}")

    # --- quantify the transition speed -------------------------------------
    russia = shares[shares["origin"] == "Russian Federation"].copy()
    russia["date"] = pd.to_datetime(
        russia["refYear"].astype(str) + "-" + russia["refMonth"].astype(str) + "-01"
    )
    russia = russia.sort_values("date")

    embargo_date = pd.Timestamp(EMBARGO_YEAR, EMBARGO_MONTH, 1)
    before = russia[russia["date"] < embargo_date]
    after = russia[russia["date"] >= embargo_date]

    baseline_share = before["share_pct"].mean()
    print(f"\nRussia's average share before the embargo: {baseline_share:.1f}%")

    below_threshold = after[after["share_pct"] < RUSSIA_LOW_THRESHOLD_PCT]
    if len(below_threshold):
        first_low = below_threshold.iloc[0]
        months_elapsed = (
            (first_low["date"].year - embargo_date.year) * 12
            + (first_low["date"].month - embargo_date.month)
        )
        print(f"First month below {RUSSIA_LOW_THRESHOLD_PCT}%: "
              f"{first_low['date'].strftime('%Y-%m')} "
              f"({months_elapsed} month(s) after the embargo)")
    else:
        print(f"Russia's share never fell below {RUSSIA_LOW_THRESHOLD_PCT}% "
              "in the available data.")

    # --- print the embargo transition window for a quick look --------------
    print("\nRussia's monthly share, Aug 2022 - Aug 2023:")
    window = shares[
        (shares["origin"] == "Russian Federation")
        & (shares["refYear"].isin([2022, 2023]))
    ]
    window = window[
        ((window["refYear"] == 2022) & (window["refMonth"] >= 8))
        | ((window["refYear"] == 2023) & (window["refMonth"] <= 8))
    ]
    print(window[["refYear", "refMonth", "share_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()