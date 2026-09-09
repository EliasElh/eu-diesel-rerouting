"""Test whether EU extra-zone diesel import volumes respond to the crack
spread, and with what lag.

Hypothesis: chartering a ship and sailing from India/Gulf takes ~4-6 weeks,
so volumes should follow price movements with a delay, not react instantly.

Approach: correlate monthly extra-zone volumes against the crack spread
shifted back by 0 to 6 months, and see which lag gives the strongest
correlation. Simple, appropriate for 84 monthly points and a period that
also contains a structural shock (the embargo itself) -- not just a
continuous price signal.

Run from project root:  python -m src.analyze_price_flow
"""

from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path("data/diesel.duckdb")
MAX_LAG_MONTHS = 6


def main() -> None:
    con = duckdb.connect(str(DB_PATH))

    # monthly extra-zone volumes: origins outside our 30-reporter list
    volumes = con.execute("""
        SELECT refYear, refMonth, SUM(netWgt) / 1000 AS extra_zone_tonnes
        FROM flows
        WHERE is_special_partner = false
          AND partnerCode NOT IN (SELECT DISTINCT reporterCode FROM flows)
        GROUP BY refYear, refMonth
    """).fetchdf()

    prices = con.execute("""
        SELECT refYear, refMonth, crack_spread_usd_bbl
        FROM crack_spread
    """).fetchdf()

    con.close()

    # inner join: only months present in BOTH series survive
    # (this naturally restricts us to 2019-2025, since eia_prices stops there)
    df = volumes.merge(prices, on=["refYear", "refMonth"], how="inner")
    df["date"] = pd.to_datetime(
        df["refYear"].astype(str) + "-" + df["refMonth"].astype(str) + "-01"
    )
    df = df.sort_values("date").reset_index(drop=True)

    print(f"Months available for analysis: {len(df)}")
    print(df[["date", "extra_zone_tonnes", "crack_spread_usd_bbl"]].head())

    # test each lag: does past crack spread correlate with current volumes?
    print("\nCorrelation between volumes and crack spread, by lag (months):")
    results = []
    for lag in range(MAX_LAG_MONTHS + 1):
        lagged_price = df["crack_spread_usd_bbl"].shift(lag)
        corr = df["extra_zone_tonnes"].corr(lagged_price)
        results.append((lag, corr))
        print(f"  lag {lag}: {corr:.3f}")

    best_lag, best_corr = max(results, key=lambda x: x[1])
    print(f"\nStrongest correlation at lag {best_lag} months (r = {best_corr:.3f})")

        # --- alternative test: correlate month-over-month CHANGES, not levels ---
    # two trending series can show near-zero level correlation while their
    # variations are actually related -- a classic time-series pitfall
    df["volume_change"] = df["extra_zone_tonnes"].diff()
    df["price_change"] = df["crack_spread_usd_bbl"].diff()

    print("\nCorrelation between MONTH-OVER-MONTH CHANGES, by lag (months):")
    for lag in range(MAX_LAG_MONTHS + 1):
        lagged_price_change = df["price_change"].shift(lag)
        corr = df["volume_change"].corr(lagged_price_change)
        print(f"  lag {lag}: {corr:.3f}")


if __name__ == "__main__":
    main()