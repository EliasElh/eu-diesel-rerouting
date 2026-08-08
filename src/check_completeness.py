"""Completeness report for raw Comtrade files.

Checks the expected grid (30 reporters x 8 years) against what is actually
on disk, and inspects each file: row count, months present, data-quality
flags (motCode, customsCode, World consistency, missing weights).

Run from project root:  python -m src.check_completeness
Output: data/processed/completeness_report.csv + terminal summary.
"""

import json
from pathlib import Path

import pandas as pd

from src.reporters import REPORTERS
from src.ingest_comtrade import YEARS, RAW_DIR

OUT_PATH = Path("data/processed/completeness_report.csv")


def inspect_file(path: Path) -> dict:
    """Read one raw JSON file and return its quality metrics."""
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    rows = payload.get("data", [])

    months = sorted({r["refMonth"] for r in rows})
    partners = {r["partnerCode"] for r in rows}

    world_wgt = sum(r["netWgt"] or 0 for r in rows if r["partnerCode"] == 0)
    partners_wgt = sum(r["netWgt"] or 0 for r in rows if r["partnerCode"] != 0)
    # relative gap; avoid division by zero on empty files
    world_gap_pct = (
        abs(world_wgt - partners_wgt) / world_wgt * 100 if world_wgt else None
    )

    return {
        "n_rows": len(rows),
        "n_months": len(months),
        "months_present": ",".join(str(m) for m in months),
        "n_partners": len(partners),
        "has_world_line": 0 in partners,
        "world_gap_pct": world_gap_pct,
        "n_zero_netwgt": sum(1 for r in rows if not r["netWgt"]),
        "n_estimated_wgt": sum(1 for r in rows if r["isNetWgtEstimated"]),
        "mot_codes": ",".join(str(c) for c in {r["motCode"] for r in rows}),
        "customs_codes": ",".join({r["customsCode"] for r in rows}),
    }


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    records = []

    for year in sorted(YEARS):
        for code, iso3 in REPORTERS.items():
            path = RAW_DIR / f"comtrade_{iso3}_{year}.json"
            record = {"reporter": iso3, "year": year, "file_exists": path.exists()}
            if path.exists():
                record.update(inspect_file(path))
            records.append(record)

    df = pd.DataFrame(records)
    df.to_csv(OUT_PATH, index=False)

    # --- Terminal summary ---------------------------------------------------
    print(f"Files expected: {len(df)}, present: {df['file_exists'].sum()}")

    empty = df[(df["file_exists"]) & (df["n_rows"] == 0)]
    print(f"\nEmpty files (0 rows) — candidates for re-download: {len(empty)}")
    print(empty[["reporter", "year"]].to_string(index=False))

    partial = df[(df["n_rows"] > 0) & (df["n_months"] < 12)]
    print(f"\nPartial years (<12 months): {len(partial)}")
    print(partial[["reporter", "year", "n_months", "months_present"]].to_string(index=False))

    print("\nmotCode values across all files:", set(df["mot_codes"].dropna()))
    print("customsCode values across all files:", set(df["customs_codes"].dropna()))

    bad_gap = df[df["world_gap_pct"] > 0.5]
    print(f"\nFiles where sum(partners) differs from World by >0.5%: {len(bad_gap)}")
    if len(bad_gap):
        print(bad_gap[["reporter", "year", "world_gap_pct"]].to_string(index=False))

    print(f"\nDetailed report written to {OUT_PATH}")


if __name__ == "__main__":
    main()