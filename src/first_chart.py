"""Produce two charts of EU diesel imports by origin, both cut at Dec 2025
(the last month with full ~29-reporter coverage; 2026 data is incomplete).

Chart 1 (origin_shares.png): all declared imports, top origins + Other.
  Caveat: Netherlands and Belgium act largely as transit hubs
  (60% / 77% of their declared imports come from another reporter in our
  own list) -- see chart 2 for the external-sourcing view.

Chart 2 (extra_zone_origins.png): imports from OUTSIDE our 30-country zone
  only, summed across all reporters. This isolates the external sourcing
  shift (Russia -> India/Gulf/US) from intra-zone redistribution.
  Caveat: gross sums can, in principle, double-count a cargo re-exported
  between two reporters in our list; the effect is assumed marginal here
  and not corrected (documented limitation, not resolved).

Run from project root:  python -m src.first_chart
"""

from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd

DB_PATH = Path("data/diesel.duckdb")
DOCS_DIR = Path("docs")

N_TOP_ORIGINS = 6
CUTOFF = "2025-12-01"  # last month with full reporter coverage


def plot_series(pivot: pd.DataFrame, title: str, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    pivot.plot(ax=ax, linewidth=1.8)
    ax.set_title(title)
    ax.set_ylabel("Tonnes")
    ax.set_xlabel("")
    ax.axvline(pd.Timestamp("2023-02-05"), color="black", linestyle="--", linewidth=1)
    ax.text(pd.Timestamp("2023-02-05"), ax.get_ylim()[1] * 0.95, "  EU embargo",
            rotation=90, va="top", fontsize=8)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Chart saved to {out_path}")


def add_date(df: pd.DataFrame) -> pd.DataFrame:
    df["date"] = pd.to_datetime(
        df["refYear"].astype(str) + "-" + df["refMonth"].astype(str) + "-01"
    )
    return df[df["date"] <= CUTOFF]


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Chart 1: all declared imports, top origins + Other ---------------
    top_origins = con.execute(f"""
        SELECT partnerName, SUM(netWgt) / 1000 AS total_t
        FROM flows
        WHERE is_special_partner = false
        GROUP BY partnerName
        ORDER BY total_t DESC
        LIMIT {N_TOP_ORIGINS}
    """).fetchdf()
    top_names = top_origins["partnerName"].tolist()
    top_list_sql = ", ".join(f"'{n}'" for n in top_names)

    monthly = con.execute(f"""
        SELECT refYear, refMonth,
            CASE WHEN partnerName IN ({top_list_sql}) THEN partnerName
                 ELSE 'Other' END AS origin,
            SUM(netWgt) / 1000 AS tonnes
        FROM flows
        WHERE is_special_partner = false
        GROUP BY refYear, refMonth, origin
    """).fetchdf()
    monthly = add_date(monthly)
    pivot1 = monthly.pivot(index="date", columns="origin", values="tonnes").fillna(0)
    pivot1 = pivot1[top_names + ["Other"]]
    plot_series(pivot1, "EU diesel imports by origin (HS 271019), monthly — all declared",
                DOCS_DIR / "origin_shares.png")

    # ---- Chart 2: extra-zone origins only ----------------------------------
    top_extra = con.execute(f"""
        SELECT partnerName, SUM(netWgt) / 1000 AS total_t
        FROM flows
        WHERE is_special_partner = false
          AND partnerCode NOT IN (SELECT DISTINCT reporterCode FROM flows)
        GROUP BY partnerName
        ORDER BY total_t DESC
        LIMIT {N_TOP_ORIGINS}
    """).fetchdf()
    top_extra_names = top_extra["partnerName"].tolist()
    top_extra_sql = ", ".join(f"'{n}'" for n in top_extra_names)

    monthly_extra = con.execute(f"""
        SELECT refYear, refMonth,
            CASE WHEN partnerName IN ({top_extra_sql}) THEN partnerName
                 ELSE 'Other' END AS origin,
            SUM(netWgt) / 1000 AS tonnes
        FROM flows
        WHERE is_special_partner = false
          AND partnerCode NOT IN (SELECT DISTINCT reporterCode FROM flows)
        GROUP BY refYear, refMonth, origin
    """).fetchdf()
    monthly_extra = add_date(monthly_extra)
    pivot2 = monthly_extra.pivot(index="date", columns="origin", values="tonnes").fillna(0)
    pivot2 = pivot2[top_extra_names + ["Other"]]
    plot_series(pivot2, "EU diesel imports from OUTSIDE the zone, by origin — extra-zone sourcing",
                DOCS_DIR / "extra_zone_origins.png")

    con.close()

    print("\nTop origins (all declared):")
    print(top_origins)
    print("\nTop origins (extra-zone only):")
    print(top_extra)


if __name__ == "__main__":
    main()