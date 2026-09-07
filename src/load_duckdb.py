"""Load the cleaned, filled flow table into a DuckDB database file.

DuckDB is a file-based analytical database: no server, no password, just
a file on disk. This script creates data/diesel.duckdb and loads our
Parquet file into a table called "flows", ready to be queried with SQL.

Run from project root:  python -m src.load_duckdb
"""

from pathlib import Path

import duckdb

PROCESSED_DIR = Path("data/processed")
DB_PATH = Path("data/diesel.duckdb")
PARQUET_PATH = PROCESSED_DIR / "flows_detail_filled.parquet"


def main() -> None:
    con = duckdb.connect(str(DB_PATH))

    con.execute("DROP TABLE IF EXISTS flows")
    con.execute(f"""
        CREATE TABLE flows AS
        SELECT * FROM read_parquet('{PARQUET_PATH.as_posix()}')
    """)

    n_rows = con.execute("SELECT COUNT(*) FROM flows").fetchone()[0]
    print(f"Table 'flows' created with {n_rows:,} rows")

    print("\nColumns:")
    print(con.execute("DESCRIBE flows").fetchdf())

    print("\nPreview:")
    print(con.execute("SELECT * FROM flows LIMIT 5").fetchdf())

    # sanity check: the embargo, visible directly in SQL
    check = con.execute("""
        SELECT refYear, refMonth, netWgt
        FROM flows
        WHERE reporterCode = 528 AND partnerCode = 643
        ORDER BY refYear, refMonth
        LIMIT 15
    """).fetchdf()
    print("\nNL-Russia, first 15 months:")
    print(check)

    con.close()
    print(f"\nDatabase saved to {DB_PATH}")


if __name__ == "__main__":
    main()