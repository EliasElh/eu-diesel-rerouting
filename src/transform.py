"""Transform raw Comtrade JSON files into clean, analysis-ready tables.

Steps:
  1. Read all raw files and stack them into one DataFrame (kept columns only).
  2. Sanity checks: flowCode and cmdCode must be constant.
  3. Keep only total lines: motCode == 0, customsCode == "C00",
     partner2Code == 0 (drops transport/customs/consignment breakdowns
     to avoid double counting).
  4. Split partner detail (one row per origin) from World aggregate lines
     (partnerCode == 0). Partner detail is treated as the source of truth:
     some reporters (notably FRA, GBR, ESP) publish a World line with
     netWgt == 0 for some months while partner detail is fully populated.
     The World line is therefore used as a consistency check only for
     reporter-months where it carries a non-zero weight.
  5. Write both tables to data/processed/ as Parquet files.

Run from project root:  python -m src.transform
"""

import json
from pathlib import Path

import pandas as pd

from src.ingest_comtrade import RAW_DIR

PROCESSED_DIR = Path("data/processed")

KEEP_COLS = [
    "refYear", "refMonth", "reporterCode", "partnerCode", "partner2Code",
    "netWgt", "primaryValue", "isNetWgtEstimated",
    "motCode", "customsCode", "flowCode", "cmdCode",
]


def load_one_file(path: Path) -> pd.DataFrame | None:
    """Read one raw JSON file. Return a DataFrame, or None if empty."""
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    rows = payload.get("data", [])
    if not rows:                      # empty file (e.g. Austria) -> skip
        return None
    return pd.DataFrame(rows)[KEEP_COLS]


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # --- 1. Read and stack all files ---------------------------------------
    frames = []
    n_empty = 0
    for path in sorted(RAW_DIR.glob("comtrade_*.json")):
        df_one = load_one_file(path)
        if df_one is None:
            n_empty += 1
            continue
        frames.append(df_one)
    df = pd.concat(frames, ignore_index=True)
    print(f"Files read: {len(frames)} with data, {n_empty} empty")
    print(f"Stacked rows: {len(df):,}")

    # --- 2. Sanity checks ---------------------------------------------------
    assert set(df["flowCode"].unique()) == {"M"}, "unexpected flowCode found"
    assert set(df["cmdCode"].unique()) == {"271019"}, "unexpected cmdCode found"

    # --- 3. Keep totals only (drop transport/customs/consignment breakdowns)
    n_before = len(df)
    df = df[(df["motCode"] == 0)
            & (df["customsCode"] == "C00")
            & (df["partner2Code"] == 0)]
    print(f"After motCode/customsCode/partner2Code filter: {len(df):,} rows "
          f"({n_before - len(df):,} breakdown rows dropped)")

    # checks passed and filters applied -> these columns are now constant
    df = df.drop(columns=["motCode", "customsCode", "partner2Code",
                           "flowCode", "cmdCode"])

    # --- 4. Split detail vs World aggregate ---------------------------------
    world = df[df["partnerCode"] == 0]
    detail = df[df["partnerCode"] != 0]
    print(f"Detail rows: {len(detail):,} | World rows: {len(world):,}")

    # World control: only meaningful where the World line carries a weight.
    # Some reporters (FRA, GBR, ESP) publish zero-weight World lines while
    # partner detail is fully populated -> detail is the source of truth.
    d = detail.groupby(["reporterCode", "refYear", "refMonth"])["netWgt"].sum()
    w = world.groupby(["reporterCode", "refYear", "refMonth"])["netWgt"].sum()
    both = pd.concat([d.rename("detail"), w.rename("world")], axis=1).dropna()
    both = both[both["world"] > 0]

    gap_pct = (both["detail"] - both["world"]).abs().sum() / both["world"].sum() * 100
    print(f"World control on {len(both):,} reporter-months with non-zero World: "
          f"gap = {gap_pct:.3f}%")

    n_zero_world = w[w == 0].shape[0]
    print(f"Reporter-months with a zero-weight World line (excluded from check): "
          f"{n_zero_world:,}")

    # --- 5. Write outputs -----------------------------------------------------
    detail.to_parquet(PROCESSED_DIR / "flows_detail.parquet", index=False)
    world.to_parquet(PROCESSED_DIR / "flows_world.parquet", index=False)
    print(f"Written to {PROCESSED_DIR}/")


if __name__ == "__main__":
    main()