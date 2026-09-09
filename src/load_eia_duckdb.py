"""Load EIA price data into DuckDB and compute the crack spread.

Loads eia_prices.parquet into a table, then creates a VIEW (a saved query,
computed on demand -- not stored data) that converts diesel from $/gallon
to $/barrel and derives the crack spread (diesel - crude, $/barrel), the
standard refining-margin convention.

Run from project root:  python -m src.load_eia_duckdb
"""

from pathlib import Path

import duckdb

DB_PATH = Path("data/diesel.duckdb")
PARQUET_PATH = Path("data/processed/eia_prices.parquet")

GALLONS_PER_BARREL = 42  # fixed unit conversion, not an approximation


def main() -> None:
    con = duckdb.connect(str(DB_PATH))

    con.execute("DROP TABLE IF EXISTS eia_prices")
    con.execute(f"""
        CREATE TABLE eia_prices AS
        SELECT * FROM read_parquet('{PARQUET_PATH.as_posix()}')
    """)

    con.execute(f"""
        CREATE OR REPLACE VIEW crack_spread AS
        SELECT
            refYear, refMonth,
            brent_usd_bbl,
            diesel_usd_gal,
            diesel_usd_gal * {GALLONS_PER_BARREL} AS diesel_usd_bbl,
            (diesel_usd_gal * {GALLONS_PER_BARREL} - brent_usd_bbl) AS crack_spread_usd_bbl
        FROM eia_prices
    """)

    n_rows = con.execute("SELECT COUNT(*) FROM eia_prices").fetchone()[0]
    print(f"Table 'eia_prices' loaded: {n_rows} rows")

    preview = con.execute("""
        SELECT * FROM crack_spread ORDER BY refYear, refMonth LIMIT 5
    """).fetchdf()
    print("\nPreview:")
    print(preview)

    around_embargo = con.execute("""
        SELECT refYear, refMonth, crack_spread_usd_bbl
        FROM crack_spread
        WHERE (refYear = 2022 AND refMonth >= 6)
           OR (refYear = 2023 AND refMonth <= 12)
        ORDER BY refYear, refMonth
    """).fetchdf()
    print("\nCrack spread, June 2022 - Dec 2023:")
    print(around_embargo.to_string(index=False))

    con.close()
    print(f"\nDatabase updated: {DB_PATH}")


if __name__ == "__main__":
    main()