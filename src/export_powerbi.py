"""Export analysis-ready CSV files for Power BI.

Power BI has no native DuckDB connector, so tables are exported to CSV
(chosen over Parquet: at this data size, CSV has no real downside and is
human-readable, which matters more here than Parquet's type-strictness).

All monthly tables get a harmonized "Date" column (first-of-month) so they
can each relate to date_dim on the same field -- a single source of truth
for time across the whole Power BI model.

Outputs go to data/powerbi/ (gitignored, like the rest of data/).

Run from project root:  python -m src.export_powerbi
"""

from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path("data/diesel.duckdb")
OUT_DIR = Path("data/powerbi")
DOCS_DIR = Path("docs")


def export_flows(con: duckdb.DuckDBPyConnection) -> None:
    flows = con.execute("""
        SELECT
            refYear, refMonth,
            reporterCode, reporterName,
            partnerCode, partnerName, iso2, iso3,
            is_special_partner,
            (partnerCode NOT IN (SELECT DISTINCT reporterCode FROM flows)) AS isExtraZone,
            netWgt, primaryValue, isNetWgtEstimated
        FROM flows
        WHERE refYear < 2026
    """).fetchdf()

    flows["Date"] = pd.to_datetime(
        flows["refYear"].astype(str) + "-" + flows["refMonth"].astype(str) + "-01"
    )
    flows.to_csv(OUT_DIR / "flows.csv", index=False)
    print(f"flows.csv: {len(flows):,} rows")


def export_date_dim() -> None:
    dates = pd.date_range("2019-01-01", "2025-12-01", freq="MS")
    date_dim = pd.DataFrame({
        "Date": dates,
        "Year": dates.year,
        "Month": dates.month,
        "MonthName": dates.strftime("%b"),
    })
    date_dim.to_csv(OUT_DIR / "date_dim.csv", index=False)
    print(f"date_dim.csv: {len(date_dim)} rows")


def export_price_flow(con: duckdb.DuckDBPyConnection) -> None:
    monthly = con.execute("""
        SELECT
            f.refYear, f.refMonth,
            SUM(f.netWgt) / 1000 AS extra_zone_tonnes,
            c.crack_spread_usd_bbl
        FROM flows f
        JOIN crack_spread c ON f.refYear = c.refYear AND f.refMonth = c.refMonth
        WHERE f.is_special_partner = false
          AND f.partnerCode NOT IN (SELECT DISTINCT reporterCode FROM flows)
        GROUP BY f.refYear, f.refMonth, c.crack_spread_usd_bbl
    """).fetchdf()
    monthly["Date"] = pd.to_datetime(
        monthly["refYear"].astype(str) + "-" + monthly["refMonth"].astype(str) + "-01"
    )
    monthly.to_csv(OUT_DIR / "price_flow_monthly.csv", index=False)
    print(f"price_flow_monthly.csv: {len(monthly)} rows")


def export_distances(con: duckdb.DuckDBPyConnection) -> None:
    dist = con.execute("SELECT * FROM distances").fetchdf()
    dist.to_csv(OUT_DIR / "distances.csv", index=False)
    print(f"distances.csv: {len(dist)} rows")


def export_market_shares() -> None:
    df = pd.read_csv(DOCS_DIR / "market_shares.csv")
    df["Date"] = pd.to_datetime(
        df["refYear"].astype(str) + "-" + df["refMonth"].astype(str) + "-01"
    )
    df.to_csv(OUT_DIR / "market_shares.csv", index=False)
    print(f"market_shares.csv: {len(df)} rows")


def export_tonne_miles() -> None:
    df = pd.read_csv(DOCS_DIR / "tonne_miles.csv")
    df = df.rename(columns={"date": "Date"})
    df.to_csv(OUT_DIR / "tonne_miles.csv", index=False)
    print(f"tonne_miles.csv: {len(df)} rows")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))

    export_flows(con)
    export_date_dim()
    export_price_flow(con)
    export_distances(con)
    export_market_shares()
    export_tonne_miles()

    con.close()
    print(f"\nAll Power BI inputs written to {OUT_DIR}/")


if __name__ == "__main__":
    main()