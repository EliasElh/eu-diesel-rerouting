"""Hand-built reference table of sea distances from each major extra-zone
diesel origin to Rotterdam (the EU's main diesel entry hub), used as the
basis for tonne-mile calculations.

Simplification, documented: one representative export port per country,
straight to Rotterdam. Real cargo routing is more complex (multiple ports,
multiple EU destinations), but this is not measurable from Comtrade data
alone (would require AIS vessel-tracking data, out of scope).

Distances are REAL SEA ROUTES (via Suez Canal etc. where applicable), not
great-circle/straight-line distances -- a ship cannot sail through land.

Countries covered: the top 18 extra-zone origins by tonnage, covering
~95.5% of extra-zone import volume (see coverage report below).

Sources:
  - Top 6 (76% of volume): verified via ports.com sea-route calculator,
    each checked individually (see README methodology notes).
  - Remaining 12 (20% of volume): estimated by geographic proximity to a
    verified route on the same sea/strait system. Lower confidence -- not
    individually checked. Spot-check recommended before treating any single
    one as precise.

Run from project root:  python -m src.distances
"""

from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path("data/diesel.duckdb")
DOCS_DIR = Path("docs")

# partnerName must match the exact spelling used in the `flows` table
DISTANCES_NM = {
    # --- verified via ports.com ---
    "Russian Federation":   {"port": "Primorsk",         "nm": 1532, "confidence": "verified"},
    "Saudi Arabia":         {"port": "Ras Tanura",        "nm": 7338, "confidence": "verified"},
    "USA":                  {"port": "Houston",           "nm": 6137, "confidence": "verified"},
    "Kuwait":               {"port": "Mina Al-Ahmadi",    "nm": 7484, "confidence": "verified"},
    "India":                {"port": "Mumbai (proxy for Jamnagar)", "nm": 7173, "confidence": "verified_proxy_port"},
    "United Arab Emirates": {"port": "Fujairah",          "nm": 6830, "confidence": "verified"},
    # --- estimated by geographic proximity, not individually checked ---
    "Qatar":                {"port": "Ras Laffan",        "nm": 7300, "confidence": "estimated"},
    "Rep. of Korea":        {"port": "Ulsan",             "nm": 11500, "confidence": "estimated"},
    "Türkiye":              {"port": "Izmit",             "nm": 3100, "confidence": "estimated"},
    "China":                {"port": "Ningbo-Zhoushan",   "nm": 11800, "confidence": "estimated"},
    "Singapore":            {"port": "Singapore",         "nm": 8300, "confidence": "estimated"},
    "Egypt":                {"port": "Alexandria",        "nm": 3100, "confidence": "estimated"},
    "Israel":               {"port": "Haifa",             "nm": 3300, "confidence": "estimated"},
    "Iraq":                 {"port": "Basra",             "nm": 7600, "confidence": "estimated"},
    "Malaysia":             {"port": "Port Dickson",      "nm": 8300, "confidence": "estimated"},
    "Algeria":              {"port": "Arzew",             "nm": 1500, "confidence": "estimated"},
    "Bahrain":               {"port": "Sitra",             "nm": 7400, "confidence": "estimated"},
    "Oman":                 {"port": "Sohar",             "nm": 6850, "confidence": "estimated"},
}

# confidence values:
#   verified  -- distance checked for the actual chosen representative port
#   proxy     -- distance checked, but for a substitute port (chosen port
#                wasn't indexed by the distance calculator used)
#   estimated -- neither port nor distance individually checked; inferred
#                from geographic proximity to a verified/proxy route


def build_coverage_report(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Same cumulative-coverage query used to decide the 18-country cutoff,
    now saved permanently so the methodology stays reproducible/documented."""
    return con.execute("""
        SELECT
            partnerName,
            SUM(netWgt) / 1000 AS tonnes,
            SUM(SUM(netWgt) / 1000) OVER (ORDER BY SUM(netWgt) DESC)
                / SUM(SUM(netWgt) / 1000) OVER () * 100 AS cumulative_pct
        FROM flows
        WHERE is_special_partner = false
          AND partnerCode NOT IN (SELECT DISTINCT reporterCode FROM flows)
        GROUP BY partnerName
        ORDER BY tonnes DESC
    """).fetchdf()


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))

    # --- save the coverage justification (Elias wanted to keep this) -------
    coverage = build_coverage_report(con)
    coverage.to_csv(DOCS_DIR / "extra_zone_coverage.csv", index=False)
    covered = coverage[coverage["partnerName"].isin(DISTANCES_NM.keys())]
    print(f"Distance table covers {len(DISTANCES_NM)} countries, "
          f"{covered['cumulative_pct'].max():.1f}% of extra-zone volume")
    print(f"Coverage report saved to {DOCS_DIR / 'extra_zone_coverage.csv'}")

    # --- build and load the distance reference table ------------------------
    rows = [
        {"partnerName": name, "port": info["port"],
         "nm_to_rotterdam": info["nm"], "confidence": info["confidence"]}
        for name, info in DISTANCES_NM.items()
    ]
    df = pd.DataFrame(rows)

    con.execute("DROP TABLE IF EXISTS distances")
    con.execute("CREATE TABLE distances AS SELECT * FROM df")

    print(f"\nTable 'distances' loaded: {len(df)} rows")
    print(df.to_string(index=False))

    con.close()


if __name__ == "__main__":
    main()