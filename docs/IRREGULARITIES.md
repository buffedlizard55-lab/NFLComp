# Irregularity Register & Resolution Log

This register catalogs all anomalous data, missing observations, provider conflicts, and API limitations detected across the 7,548 game historical archive.

The file carries two views. The long-form notes below were written while the
discrepancies were found and keep their original `IRR-2026-0nn` numbering. The
table at the end is the machine-checked export of `data/irregularities.json`,
which the audit regenerates on every run: an irregularity the audit detects
(`IRR-11-EXP_004_TNF_SHORT_REST_TRAVEL-DISPUTED`, for example, where a dossier
claim disagrees with the snapshot) appears there without anyone editing this
page. The export is authoritative; nothing here is deleted to make a number look
better.

---

## Registered Irregularities

### 1. `IRR-2026-001`: Historical Neutral-Site Missing Temperature Data
- **Severity:** Low
- **Category:** Missing Meteorological Data
- **Description:** 42 neutral site international games (London / Munich / Mexico City) between 2007 and 2023 lacked surface temperature and wind recordings in standard NOAA weather feeds.
- **Affected Datasets:** `games.csv`
- **Resolution:** Implemented neutral stadium fallback defaulting to standard indoor climate (70°F, 0 mph wind) or local Met Office archival weather feeds. Strategy `@WindChill_Totals` is suppressed on neutral international games unless certified local airport observation is present.

### 2. `IRR-2026-002`: nflverse Spread Line Sign Inversion Convention
- **Severity:** High (Resolved)
- **Category:** Data Schema Convention
- **Description:** The `spread_line` column in `nflverse/nfldata` stores `away_spread` (positive when the home team is favored, e.g. `BUF -6.5` vs DET is recorded as `spread_line = 6.5` in `games.csv`), which is the mathematical opposite of traditional sportsbook convention (`home_spread = -6.5`). A prior engine build incorrectly treated this raw value as a home spread, inflating rest-differential backtests.
- **Affected Datasets:** `games.csv` (away convention), `closing_lines.csv`, `initial_lines.csv` (home convention)
- **Resolution:** Standardized in `engine/data_loader.py`: `raw_away_spread` is negated to `spread_line = -raw_away_spread` (home convention, negative = home favored). All settlements, Poisson grids, and strategy displays now use `home_cover = (home_score - away_score) + spread_line > 0`. Cross-check confirmed the correction flips `STRAT_REST_TNF_005_v3` 2023-2025 holdout from an inflated 52.46% / +2.6% ROI to the true 48.75% / -7.25% (HOLDOUT_FAILED).

### 3. `IRR-2026-003`: 2020 COVID-19 Schedule Disruptions & Bye Week Irregularities
- **Severity:** Medium
- **Category:** Schedule Rescheduling
- **Description:** Multiple 2020 games were rescheduled to Tuesday and Wednesday (e.g. TEN vs BUF, BAL vs PIT) due to COVID-19 outbreaks, causing non-standard 4-day, 5-day, and 12-day rest intervals.
- **Affected Datasets:** `games.csv`
- **Resolution:** `engine/data_loader.py` computes true rest days using UTC calendar day arithmetic between consecutive gamedays rather than assuming fixed 7-day NFL weekly intervals.

### 4. `IRR-2026-004`: Reddit API Hard Commercial Paywall (HTTP 403 Forbidden)
- **Severity:** Medium
- **Category:** API Access Block
- **Description:** Probed Reddit `/r/nfl/` and `/r/sportsbook/` public JSON endpoints for crowd sentiment extraction; requests returned HTTP 403 Forbidden due to Reddit's 2023 commercial API paywall.
- **Affected Datasets:** Data Source Registry (`SRC_REDDIT_JSON`)
- **Resolution:** Formally cataloged in Data Source Registry as `DISCOVERY_ONLY / BLOCKED`. Removed crowd sentiment reliance from all quantitative strategy lineages in favor of verified line movements from `closing_lines.csv`.

### 5. `IRR-2026-005`: Kalshi Event Market Fee & Spread Slippage
- **Severity:** High (Calibrated)
- **Category:** Market Friction
- **Description:** Naive paper-trading models report unrealistic profits on Kalshi contracts by assuming instantaneous fills at the mid-price with zero fees.
- **Affected Datasets:** `kalshi_trades.json`
- **Resolution:** Implemented `KalshiExecutionSimulator` in `engine/models.py` simulating 2¢ bid-ask spread crossing, volume-dependent slippage (0.5¢ per 500 contracts), and the CFTC exchange fee schedule ($0.01 per contract).

---

## Machine-checked register export

<!-- IRREGULARITIES_START -->
_generated — do not edit by hand — the export the audit writes (20 entries). An irregularity the audit detects appears here automatically; the long-form notes above are the human-written record of the earliest discoveries and keep their original numbering._

| ID | Title | Category | Severity | Status |
| --- | --- | --- | --- | --- |
| `IRR-01-NFL-BYRON-YOUNG-ROSTER` | Player-Team Discrepancy: Byron Young LAR vs PHI | ROSTER_DISCREPANCY | LOW | `LOGGED_AND_RESOLVED` |
| `IRR-02-REDDIT-JSON-403` | Reddit JSON API Access Blocked (HTTP 403) | API_BLOCK | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-03-TNF-SHORT-REST-WEATHER` | TNF Indoor vs Outdoor Weather Attribution | ENVIRONMENT_DATA | LOW | `LOGGED_AND_RESOLVED` |
| `IRR-04-NFL-POLICY-PDF-404` | NFL Personnel Policy PDFs Return 404 | BROKEN_LINK | LOW | `LOGGED_AND_RESOLVED` |
| `IRR-05-KALSHI-TOUCH-REANCHOR` | Kalshi Orderbook Depth Re-anchoring Between Snapshots | EXECUTION_MODEL | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-06-OL-CONTINUITY-TRACKING` | Offensive Line Continuity Tracking Limited Pre-2018 | DATA_LIMITATION | LOW | `LOGGED_AND_RESOLVED` |
| `IRR-07-PLAYER-PROP-HISTORICAL` | Historical Player Prop Lines Not in Free Archive | DATA_LIMITATION | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-08-ALT-SPREAD-HISTORICAL` | Alternate Spreads Historical Archive Limited | DATA_LIMITATION | LOW | `LOGGED_AND_RESOLVED` |
| `IRR-09-LIVE-PBP-LATENCY` | Live Play-by-Play Latency & Verification | EXECUTION_MODEL | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-10-TRAVEL-COORD-MAPPING` | Travel Distance Coordinate Mapping Approximation | CALCULATION | LOW | `LOGGED_AND_RESOLVED` |
| `IRR-SYNC-01-LINE_MOVED-2026_02_MIA_SF` | Upstream revision: Line Moved (2026_02_MIA_SF) | UPSTREAM_REVISION | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-SYNC-02-LINE_MOVED-2026_02_NYG_LA` | Upstream revision: Line Moved (2026_02_NYG_LA) | UPSTREAM_REVISION | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-SYNC-03-LINE_MOVED-2026_02_SEA_ARI` | Upstream revision: Line Moved (2026_02_SEA_ARI) | UPSTREAM_REVISION | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-SYNC-04-LINE_MOVED-2026_02_WAS_DAL` | Upstream revision: Line Moved (2026_02_WAS_DAL) | UPSTREAM_REVISION | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-SYNC-05-LINE_MOVED-2026_03_ARI_SF` | Upstream revision: Line Moved (2026_03_ARI_SF) | UPSTREAM_REVISION | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-SYNC-06-LINE_MOVED-2026_03_ATL_GB` | Upstream revision: Line Moved (2026_03_ATL_GB) | UPSTREAM_REVISION | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-SYNC-07-LINE_MOVED-2026_03_BAL_DAL` | Upstream revision: Line Moved (2026_03_BAL_DAL) | UPSTREAM_REVISION | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-SYNC-08-LINE_MOVED-2026_03_CIN_PIT` | Upstream revision: Line Moved (2026_03_CIN_PIT) | UPSTREAM_REVISION | MEDIUM | `LOGGED_AND_RESOLVED` |
| `IRR-SYNC-SUMMARY` | Upstream sync revision summary (+28 more grouped MEDIUM/HIGH events) | UPSTREAM_REVISION | LOW | `LOGGED_AND_RESOLVED` |
| `IRR-11-EXP_004_TNF_SHORT_REST_TRAVEL-DISPUTED` | Dossier claim refuted by the snapshot: Home cover rate, Thursday with visitor on <=4 days rest | RESEARCH_CLAIM_DISCREPANCY | MEDIUM | `LOGGED_AND_RESOLVED` |
<!-- IRREGULARITIES_END -->
