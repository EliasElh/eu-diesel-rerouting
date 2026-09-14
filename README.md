# EU Diesel Rerouting — After the Russian Embargo

Data pipeline and analysis of the reshuffling of EU diesel imports after the
2023 EU embargo on Russian refined petroleum products.

## The story

Before 2022, Russia supplied roughly half of the EU's imported diesel — short
shipping distances, established logistics, a crude blend well suited to
distillate production. The EU embargo on Russian refined products, effective
5 February 2023, cut that supply overnight. Diesel didn't disappear from the
world market — it got rerouted: the Gulf (Saudi Arabia, UAE — new mega
refineries), the US and India (which buys discounted Russian crude, refines
it and legally re-sells the diesel to Europe) stepped in, at the cost of much
longer shipping routes.

This project quantifies that reshuffling using public UN Comtrade trade data,
US EIA price data, and hand-built maritime distance references.

## What this project answers

1. **Origin shift** — who supplied EU diesel in 2019, who supplies it now,
   and how fast the switch happened, month by month.
2. **Price vs. flows** — did import volumes respond to the diesel refining
   margin (crack spread) spike after the embargo, and with what lag?
3. **Distance** — how much did the average shipping distance for EU diesel
   imports increase (tonne-miles), given the shift from nearby (Russia) to
   distant (India, Gulf, US) suppliers?

All three questions are answered as of this writing — see Results below and
`docs/` for the full data behind each chart and figure.

## Data & methodology

- **Sources**: [UN Comtrade](https://comtrade.un.org) (trade flows, free API
  tier), [US EIA](https://www.eia.gov/opendata/) (crude and diesel prices,
  free API), hand-built sea-distance reference (see `src/distances.py`).
- **Commodity**: HS code `271019` — medium petroleum distillates. The closest
  available proxy for diesel; also includes some heating oil and jet fuel
  blends depending on national classification. Diesel dominates this code for
  European flows, but the exact split isn't isolated in Comtrade data — a
  documented approximation, not a precision measure.
- **Flow direction**: **imports**, declared by the receiving country — not
  exports declared by the origin. Two reasons: Russia stopped publishing
  detailed export statistics after 2022 (export-side data is simply missing
  for the country at the center of this story) and import declarations are
  generally more reliable (customs and VAT are charged on imports, so they're
  checked more closely than exports).
- **Reporting countries**: EU-27 + UK + Norway + Switzerland (30 countries).
  Scope follows the physical diesel market, not the EU's legal borders — the
  UK shares the same supply routes and had its own near-simultaneous embargo;
  Norway/Switzerland are included for geographic completeness (marginal
  volume impact).
- **Period**: January 2019 – December 2025 for the origin/volume analysis
  (2026 data exists but is incomplete — see Limitations). Price data (EIA)
  covers the same window.
- **Price proxy**: diesel prices use the NY Harbor ULSD spot price (US
  benchmark), not a European quote — the closest free, reliable series
  available. Prices are globally correlated, but this is a proxy, not a
  European price (see Limitations).
- **Distance proxy**: tonne-miles use one representative export port per
  origin country, real sea-route distance (via Suez Canal etc. where
  applicable, not straight-line) to Rotterdam as the EU's main diesel entry
  hub — not the actual declaring country's port. See `src/distances.py` for
  the full table and per-country confidence level (`verified` /
  `verified_proxy_port` / `estimated`).

## Pipeline

```
Comtrade API ─┐                                         EIA API
              ├─> raw JSON ─> cleaned table ─┐             │
              │  (data/raw/)  (data/processed/)            v
       completeness report          │            eia_prices table
                                    v                       │
                            DuckDB: flows table             v
                                    │            DuckDB: crack_spread view
                                    ├──────────────┬─────────────────┐
                                    v              v                 v
                          origin-share charts   Q1 market      Q2 price/flow
                                                shares (SQL)    correlation
                                    │
                                    v (+ distances table)
                              Q3 tonne-miles
```

### Comtrade data pipeline

1. **Ingest** (`src/ingest_comtrade.py`) — downloads monthly import data for
   all 30 reporters, 2019–2026, one API call per (reporter, year). Idempotent:
   safe to re-run, skips files already downloaded. `src/reporters.py` holds
   the hand-built, validated reporter code reference;
   `src/test_single_call.py` is a one-shot test used to validate the API
   connection during development.
2. **Verify** (`src/check_completeness.py`) — checks the downloaded files
   against the expected (reporter × year) grid: empty files, partial years,
   internal consistency (e.g. sum of partner lines vs. the reported World
   total).
3. **Transform** (`src/transform.py`) — stacks all raw files, drops
   transport/customs/consignment breakdown rows (keeps totals only, to avoid
   double counting), and separates partner-level detail from the World
   aggregate line.
4. **Enrich** (`src/reference.py`, `src/enrich.py`) — downloads the official
   Comtrade partner reference table, joins country names onto the numeric
   codes, and flags non-country aggregate codes (regional "nes" categories,
   Bunkers, Free Zones, Special Categories).
5. **Fill zeros** (`src/fill_zeros.py`) — Comtrade omits rows for zero flows
   entirely rather than writing a zero. This script reconstructs explicit
   zero rows for (reporter, partner, month) combinations that are genuinely
   zero — but only for months where the reporter is known to have published
   data (at least one other partner line exists that month). Months where a
   reporter published nothing at all (e.g. Austria) are left untouched: no
   data is invented.
6. **Load** (`src/load_duckdb.py`) — loads the cleaned table into
   `data/diesel.duckdb` as a `flows` table, queryable with plain SQL.

### Price data pipeline (EIA)

7. **Ingest** (`src/ingest_eia.py`) — downloads monthly Brent crude
   (`PET.RBRTE.M`) and NY Harbor ULSD diesel (`PET.EER_EPD2DXL0_PF4_Y35NY_DPG.M`)
   price series, 2019–2025.
8. **Load & derive** (`src/load_eia_duckdb.py`) — loads prices into an
   `eia_prices` table, and creates a `crack_spread` SQL **view** (diesel
   converted to $/barrel minus crude, recomputed on demand rather than
   stored, so it always reflects the latest source data).

### Distance reference

9. **Build** (`src/distances.py`) — hand-built table of sea-route distances
   (nautical miles) from 18 major extra-zone origins (covering 95.6% of
   extra-zone volume) to Rotterdam, loaded as a `distances` table. Also
   saves the cumulative-volume coverage report used to justify the
   18-country cutoff (`docs/extra_zone_coverage.csv`).

### Analysis (answers the three questions)

10. **Chart** (`src/first_chart.py`) — produces the origin-share charts (all
    declared imports, and extra-zone-only sourcing).
11. **Q1 — market shares** (`src/market_share.py`) — exact monthly market
    share per origin (SQL window functions) and the embargo transition
    speed for Russia.
12. **Q2 — price vs. flow** (`src/analyze_price_flow.py`) — correlates
    extra-zone volumes against the crack spread at 0–6 month lags, on levels
    and on month-over-month changes.
13. **Q3 — tonne-miles** (`src/tonne_miles.py`) — joins flows to the distance
    table, computes monthly tonne-nautical-miles and the volume-weighted
    average shipping distance, before vs. after the embargo.

## Repository structure

```
eu-diesel-rerouting/
├── src/
│   ├── reporters.py           # EU-27+UK+NO+CH reporter code reference (hand-built, validated)
│   ├── ingest_comtrade.py     # Comtrade API ingestion
│   ├── test_single_call.py    # one-shot ingestion test
│   ├── check_completeness.py  # raw data QA report
│   ├── transform.py           # stacking + double-count filtering
│   ├── reference.py           # partner code reference (downloaded + cached)
│   ├── enrich.py               # join partner/reporter names onto flows
│   ├── fill_zeros.py          # explicit zero-flow reconstruction
│   ├── load_duckdb.py         # Parquet -> DuckDB (flows table)
│   ├── ingest_eia.py          # EIA price ingestion (Brent, NY Harbor ULSD)
│   ├── load_eia_duckdb.py     # eia_prices table + crack_spread view
│   ├── distances.py           # sea-distance reference table + coverage report
│   ├── first_chart.py         # origin-share charts
│   ├── market_share.py        # Q1: exact market shares, transition speed
│   ├── analyze_price_flow.py  # Q2: price/flow lag correlation
│   └── tonne_miles.py         # Q3: tonne-mile calculation
├── sql/                       # (reserved for standalone analytical queries)
├── docs/                      # charts, CSV exports, methodology artifacts
├── data/                      # raw/processed data, DuckDB file (gitignored)
├── requirements.txt
└── .env.example                # COMTRADE_API_KEY, EIA_API_KEY
```

## Data quality issues found and how they were handled

This dataset required real cleaning; the issues below were found by building
consistency checks into the pipeline, not assumed:

- **Breakdown double counting**: some reporters publish both a total line and
  its breakdown by transport mode, customs regime and consignment country.
  Left unfiltered, this roughly doubled reported volumes for some countries.
  Fixed by keeping only total lines (`motCode=0`, `customsCode=C00`,
  `partner2Code=0`).
- **World-line inconsistency**: a cross-check (sum of partner-level rows vs.
  the reported World total) showed a 14% gap. Root cause: France, the UK and
  Spain sometimes publish a World line with zero weight while partner detail
  is fully populated. Partner detail is used as the source of truth; the
  World check now only applies where the World line carries a non-zero
  weight (0.000% gap on ~2,400 comparable reporter-months).
- **Austria**: publishes almost no monthly data for the study period (only
  2022 available). Excluded from the analysis. Austria is landlocked,
  sources diesel almost entirely intra-EU, and represents roughly 2% of EU
  diesel imports — its exclusion does not affect the extra-EU rerouting
  story that is the focus of this project.
- **Special/aggregate partner codes**: some import volume is declared against
  non-country codes (regional "not elsewhere specified" categories, ship
  bunkers, free zones). These are kept in totals (they represent real
  tonnage) but flagged and excluded from country-level breakdowns, so a
  bar labeled "Areas, nes" never appears next to real countries on a chart.
- **Rotterdam/Antwerp hub effect**: the Netherlands and Belgium report as
  top "origins" in the raw data, but 60% and 77% of their declared imports
  respectively originate from another reporter in this project's own
  30-country list — i.e. transit through Europe's largest oil ports, not
  production. A second chart (`extra_zone_origins.png`) sums only imports
  whose origin lies outside the 30-country zone, isolating true external
  sourcing from intra-zone redistribution. Known residual limitation: gross
  sums can in principle double-count a cargo re-declared after intra-zone
  transshipment; assumed marginal here and not corrected.
- **2026 coverage**: reporter coverage drops sharply from ~29/30 countries
  in December 2025 to 1 by June 2026 (publication lag). All analysis is cut
  at December 2025.
- **No price/flow correlation found (Q2)**: tested rigorously (levels and
  changes, 0–6 month lags) rather than stopping at the first result or
  searching for a flattering lag — the null result is reported as-is and
  interpreted as evidence the rerouting was driven by the embargo itself
  (a discrete shock) rather than a gradual price response.

## Results so far

![Origin shares, all declared imports](docs/origin_shares.png)
![Origin shares, extra-zone sourcing only](docs/extra_zone_origins.png)

The second chart isolates external sourcing: Russia supplied 2.5–4.5 Mt/month
before the embargo and collapses to near-zero after February 2023, replaced
simultaneously by Saudi Arabia, the US, Kuwait, India and the UAE.

### Q1 — Origin shift, quantified

Russia's average share of extra-zone EU diesel imports was 44.9% before the
embargo (Jan 2019 - Jan 2023). It fell to 6.0% in February 2023 (the month
the embargo took effect) and below 2% by March 2023 -- a near-vertical drop
completed within one month of the embargo date, not a gradual substitution.
Full monthly market-share table: `docs/market_shares.csv`

### Q2 — Price signal vs. volume response

Tested whether extra-zone diesel import volumes respond to the crack spread
(diesel minus crude price) with a lag, on the hypothesis that shipping from
new suppliers (India, Gulf) takes 4-6 weeks longer than the pre-embargo
Russian routes.

Result: no meaningful linear correlation found, at any lag from 0 to 6
months, whether tested on price/volume levels (max |r| = 0.17) or on
month-over-month changes (max |r| = 0.18, sign inconsistent across lags).

Interpretation: the rerouting appears driven primarily by the embargo itself
-- a discrete regulatory shock -- rather than a gradual response to a price
signal. The crack spread spike (peaking Oct 2022, several months before the
February 2023 embargo) is more plausibly a *consequence* of anticipated
scarcity than a *cause* of the volume shift. This is consistent with the
sharp, near-instantaneous drop in Russian volumes visible in the origin
chart, rather than a gradual substitution pattern.

### Q3 — Shipping distance impact (tonne-miles)

Using sea-route distances from each origin's representative port to
Rotterdam (`src/distances.py`), average monthly tonne-nautical-miles for
extra-zone diesel imports rose from 34.9 billion (pre-embargo) to 45.2
billion (post-embargo) -- a 29.5% increase. The volume-weighted average
shipping distance per tonne rose from 4,509 nm to 6,905 nm (+53%), driven by
the replacement of nearby Russian supply with more distant Gulf, Indian and
US origins.

Caveat: covers the 18 origins with a distance reference (95.6% of
extra-zone volume); each country uses one representative port, a
simplification (see Limitations). Full monthly table: `docs/tonne_miles.csv`

## Status

- [x] Data acquisition (Comtrade, 240 API calls, 0 failures)
- [x] Data quality checks and cleaning
- [x] DuckDB load
- [x] Origin-share charts (Q1 first pass)
- [x] EIA price data ingestion
- [x] SQL analysis: exact market-share tables, embargo transition speed
- [x] Price/flow correlation (crack spread vs. volumes, lagged)
- [x] Tonne-mile calculation (shipping distance impact)
- [ ] Power BI dashboard
- [ ] One-pager + methodology summary

## Limitations

- HS 271019 is a proxy for diesel, not an exact match (see Methodology).
- Import-side declarations only; export-side data for Russia is unavailable
  post-2022.
- Austria excluded (no monthly publication for most of the period).
- Some countries impute weight from value when no physical weight is
  declared (`isNetWgtEstimated` flag retained in the data).
- Gross extra-zone sourcing figures may include marginal double-counting
  from cargoes re-declared after intra-zone transshipment.
- Diesel price is a US benchmark (NY Harbor ULSD) used as a global proxy,
  not a European quote.
- Tonne-mile figures use one representative port per origin country and
  straight-to-Rotterdam routing, not actual per-cargo destinations or
  routes. Of the 18 origins covered (95.6% of extra-zone volume), 6 have
  individually verified distances (76% of volume), 1 uses a verified
  distance to a substitute port (India — Jamnagar not indexed by the
  calculator used, Mumbai used instead), and 12 are estimated by
  geographic proximity to a verified route rather than individually
  checked (see `src/distances.py` for the per-country confidence level).
  The remaining 4.4% of extra-zone volume (origins outside the 18-country
  reference) is excluded from the tonne-mile calculation.

## Reproducing this project

```bash
git clone https://github.com/EliasElh/eu-diesel-rerouting
cd eu-diesel-rerouting
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env            # then fill in your Comtrade and EIA API keys

# Comtrade pipeline
python -m src.ingest_comtrade
python -m src.check_completeness
python -m src.transform
python -m src.reference
python -m src.enrich
python -m src.fill_zeros
python -m src.load_duckdb

# EIA pipeline
python -m src.ingest_eia
python -m src.load_eia_duckdb

# Analysis
python -m src.first_chart
python -m src.distances
python -m src.market_share
python -m src.analyze_price_flow
python -m src.tonne_miles
```