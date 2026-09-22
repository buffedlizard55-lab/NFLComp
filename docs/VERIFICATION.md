# Verification & Evidence Ledger — NFLComp

This document states what has actually been verified in this repository, by what
method, and — just as importantly — what has **not** been verified. Published
counts, hashes and audit rows below are generated from the checked-in files by
`python3 scripts/render_verification.py`; if they drift from `data/`, the audit
suite fails.

---

## 1. Evidence classes

| class | meaning | may be used as an execution price or result? |
| --- | --- | --- |
| `SOURCE_DATA` | a row retrieved from a named provider and retained with its retrieval timestamp | yes, if the timestamp precedes the decision |
| `DERIVED_DATA` | calculated only from source rows available before the decision time | no |
| `MODEL_OUTPUT` | a probability, projection or model estimate | never |
| `FORWARD_TEST` | the honest category when a timestamped historical price/outcome is unavailable | n/a |
| `UNVERIFIED` | retained in the verification queue only | no |

Settlement additionally requires a completed game with a verified final score and
a market-specific outcome that can be calculated from observed data; see
`docs/DATA_TRUTH.md`.

## 2. What is verified locally

`data/source/` is a checked-in snapshot of the provider files the engine reads.
The `sha256` values in the generated block are computed from those files' bytes
in this repository, which is a statement about the snapshot, not about an
upstream release. The loader (`engine.data_loader.NFLDataLoader`) reads the
snapshot directly and preserves missing prices as `null`; it never substitutes a
conventional `-110`.

Recorded provenance of the snapshot's origin (which repository, which commit,
which retrieval date) is maintained in `data/registry.json` and quoted in
`README.md`. When an upstream commit hash could not be re-verified from this
environment, the registry entry says so rather than implying a check that never
ran.

## 3. What is **not** verified in this environment

* Upstream release assets and raw file downloads (blocked for this environment:
  only git, GitHub API and page fetches are reachable).
* Commercial or gated feeds: sportsbook odds APIs, RotoWire, X/Twitter.
* Live injury/weather feeds beyond the checked-in snapshot.
* Any historical player-prop line, alternate line or live-market price.

Those sources and endpoints are recorded with their probe result in
`data/registry.json` and, where they affected a strategy, in
`data/irregularities.json`. A strategy that depends on a blocked feed is
classified `FORWARD_TEST` and is not backtested against invented prices.

<!-- VERIFICATION_START -->
## Machine-verified evidence (generated — do not edit by hand)

### Source snapshot hashes

SHA-256 computed here from the checked-in snapshot bytes. These are file hashes of the
local snapshot, not a claim about an upstream release asset.

| snapshot file | bytes | sha256 |
| --- | --- | --- |
| games.csv | 2,180,005 | `c9038d5c927d9d6bd9d2e98cb76b57fccfd4f040b7ce4b9353cc0c7ad4a860d4` |
| closing_lines.csv | 942,229 | `3571e1c9fc8d7396f405fb7c17d43c15676d335ffc932fbb03ff18da691d1729` |
| initial_lines.csv | 45,068 | `654770173d11fdb2074537d520f6b1213d663e3bbf47689e5cc9994c1af255e5` |
| teams.csv | 90,927 | `b7cfab98e6ac35c684432f6ace65d6065b0b89b90e3a2e91116a69ae38e04d42` |
| officials.csv | 2,058,971 | `6a34c3208de583bf038fda224c7839c827cd74974f5a0ed5683e1c2838674a1a` |

### Audit results

| # | check | category | result | detail |
| --- | --- | --- | --- | --- |
| 1 | `GAMES_SOURCE_EXISTS` | DATA_INTEGRITY | PASS | games.csv verified present |
| 2 | `GAME_ID_UNIQUENESS` | DATA_INTEGRITY | PASS | Found 0 duplicate game IDs across 7548 games |
| 3 | `SCORE_MARGIN_ARITHMETIC` | CALCULATION | PASS | Score margin checked on 7548 games; 0 mismatches |
| 4 | `GAMES_CHRONOLOGICAL_ORDER` | DATA_INTEGRITY | PASS | Games sorted chronologically: 1999-09-12 to 2027-01-10 |
| 5 | `SOURCE_SYNC_PROVENANCE` | SOURCE_PROVENANCE | PASS | last sync 2026-09-22T18:29:52Z; 7 files hash-verified against fetched bytes; 79 upstream revisions this sync (by severity {'MEDIUM': 2, 'INFO': 77}); 19 notable revisions retained in history |
| 6 | `SOURCE_REVISION_REVIEW` | SOURCE_PROVENANCE | PASS | 0 unacknowledged result corrections against already-settled games |
| 7 | `LEDGER_POPULATED` | AUDIT | PASS | Found 31,502 bets in ledger (2020-2026 recent slice) |
| 8 | `BET_ID_UNIQUENESS` | AUDIT | PASS | Found 0 duplicate bet IDs out of 31,502 |
| 9 | `LEDGER_PRICE_IMPLIED_PROB_CONSISTENCY` | AUDIT | PASS | Re-derived implied probability from the recorded price on 31,502 bets; 0 disagree with the price they quote |
| 10 | `LEDGER_EDGE_CONSISTENCY` | AUDIT | PASS | Re-derived edge = model_prob - implied_prob on 31,502 bets; 0 inconsistent |
| 11 | `PNL_CALCULATION_ACCURACY` | AUDIT | PASS | Audited 31,502 bets; 0 math errors |
| 12 | `LEDGER_REQUIRED_FIELDS` | AUDIT | PASS | Checked required fields; 0 missing field instances |
| 13 | `MARKET_TYPES_VALID` | AUDIT | PASS | Checked market types; 0 invalid market types |
| 14 | `LEDGER_HASH_CHAIN` | AUDIT | PASS | Re-derived 31,502 links; head f8c974419a83c9b7… |
| 15 | `LEDGER_MANIFEST_RECONCILIATION` | AUDIT | PASS | window 2020–2026: 31,502 of 97,218 bets published (65,716 in earlier seasons, totals stated separately) |
| 16 | `LEADERBOARD_INTEGRITY` | AUDIT | PASS | Leaderboard contains 70 verified strategies (target >=40) |
| 17 | `CATEGORY_COVERAGE` | AUDIT | PASS | Leaderboard covers 17 categories: Alternate Markets & Futures, Coaching & Decision Tendencies, Defensive Matchups & Scheme, Game Script & Situational, Injury & Player Availability... |
| 18 | `LEADERBOARD_LEDGER_RECONCILIATION` | AUDIT | PASS | All 70 rows re-derived from 31,502 published records (published window PnL -221,808.53; all-time totals remain on the rows) |
| 19 | `KALSHI_TRADES_INTEGRITY` | AUDIT | PASS | Found 1,463 simulated Kalshi trades with bid/ask/spread/liquidity/slippage |
| 20 | `KALSHI_FIELDS_COMPLETE` | AUDIT | PASS | Kalshi trade fields complete: True |
| 21 | `REGISTRY_ENTRIES` | AUDIT | PASS | Registry contains 56 probed sources (target >=30) |
| 22 | `VERIFIED_PRIMARY_COUNT` | AUDIT | PASS | Found 24 VERIFIED_PRIMARY sources |
| 23 | `REQUIRED_CATEGORY_COVERAGE` | AUDIT | PASS | Covered 12/12 required categories: ['Alternate Markets & Futures', 'Coaching & Decision Tendencies', 'Defensive Matchups & Scheme', 'Game Script & Situational', 'Injury & Player Availability', 'Kalshi Prediction Markets', 'Live & In-Game Strategies', 'Market Movement & CLV Strategies', 'Offensive Line & Protection', 'Player Prop Strategies', 'Public Strategy Research & Replication', 'Quarterback & Passing Efficiency', 'Referee & Officiating Tendencies', 'Rest & Scheduling Asymmetries', 'Statistical & Machine Learning Models', 'Team Totals & Efficiency', 'Weather & Stadium Conditions'] |
| 24 | `STRATEGY_VERSIONING` | AUDIT | PASS | Found 23 strategies with parent_version (versioning) |
| 25 | `MASTERSITE_RESEARCH` | AUDIT | PASS | MasterSite projects mapped: 12 sources covering CEO, Weather, Insider, TheLeap, NFL/NBA Injury, FDA, NCAA/NFL/MLB Scoreboard, Sports Pred, Gold, PinePilot |
| 26 | `PUBLISHED_README_BLOCK` | PUBLICATION | PASS | 25 published metrics and badges match the data files |
| 27 | `PUBLISHED_REPORT_BLOCK` | PUBLICATION | PASS | 25 report metrics match the data files |
| 28 | `PUBLISHED_VERIFICATION_BLOCK` | PUBLICATION | PASS | evidence ledger matches the snapshot hashes and audit results |
| 29 | `PUBLISHED_SITE_CLAIMS` | PUBLICATION | PASS | 38 embedded site claims match the data files |
| 30 | `EMPIRICAL_STUDIES_REPRODUCIBLE` | PUBLICATION | PASS | 5 studies re-derived from the snapshot; 6 dossier claims labelled DECLARED_ASSUMPTION; 1 disputed by the snapshot (EXP_004_TNF_SHORT_REST_TRAVEL) |
| 31 | `RISK_ANALYTICS_RECONCILIATION` | PUBLICATION | PASS | 70 persona risk rows and the calibration curve re-derive from 31,502 published records (Brier 0.2609, ECE 9.655 pts, 44 seeded bootstraps) |
| 32 | `PUBLISHED_PROSE_CLAIMS` | PUBLICATION | PASS | 6 generated narrative blocks current across 10 documents; no unbound numeric claim found |
| 33 | `SITE_VIEW_CONTRACTS` | PUBLICATION | PASS | 13 nav tabs map onto 13 view sections; 38 data-bound claim spans registered and present; 55 JS render targets resolved |

### Ledger chain

- Hash rule: `sha256(previous_hash + compact_json(record_without_chain_fields))`
- State: 31,502 published of 97,218 simulated records; head `f8c974419a83c9b7…`; published window 2020–2026
- The published chain starts mid-history: yes (earlier seasons are aggregated, not published).
- Published-state totals: 31,502 bets / -221,808.53 USD inside the window, 97,218 bets / -531,192.71 USD all time.

<!-- VERIFICATION_END -->

## 4. Ledger immutability and the published window

Every simulated wager carries `previous_hash` and `hash`, where

```
hash = sha256(previous_hash + json.dumps(record_without_chain_fields))
```

So a single edited field invalidates the record and every link after it. The
GitHub Pages export publishes a recent-season window of the ledger to keep the
repository small; the complete all-time totals, the window, the chain head and
the source-file hashes are written to `data/ledger_manifest.json`, and the audit
reconciles the published slice against them. Aggregates outside the published
window are stated on each leaderboard row (`pnl_outside_published_window`)
instead of being quietly folded into a number a reader cannot re-derive.

The check is honest in both directions: the published slice is *missing* records
(they are summarised, not deleted), and any attempt to alter a published record
breaks the chain, which `engine.ledger.verify_chain` detects locally without
trusting the generator.

## 5. Zero-lookahead boundary conditions

To prevent retrospective data leakage:

1. **Rolling Averages:** Team points scored/allowed and EPA ratings are updated
   **after** each game completes. When evaluating Game $N$, ratings only use
   games $1 \dots N-1$.
2. **Injury Designations:** Models read only pre-game status designations
   (OUT / DOUBTFUL / QUESTIONABLE) and practice reports.
3. **Weather Forecasts:** Wind and temperature metrics use pre-game stadium
   forecasts rather than post-game meteorological archives.
4. **Line Timestamps:** Spread moves are calculated from opening line to closing
   line timestamps; a signal is suppressed when the side-specific price at the
   decision time is absent.
5. **Chronology:** TRAIN → VALIDATE → OOS/HOLDOUT splits are defined by season.
   Future games are never mixed into an earlier training window, and a holdout
   is evaluated once without retuning (`data/strategy_lab.json`).

## 6. How to re-verify this document

```bash
python3 scripts/run_pipeline.py --check-only     # data + generated docs + audit
python3 -m engine.audit_verifier --check         # audit only, no writes
python3 scripts/render_verification.py --check   # this document's evidence block
python3 test/engine.test.py && node test/ui.test.js
```

Passing these checks proves that the published artifacts re-derive from the
checked-in data and that the arithmetic is internally consistent. It does **not**
prove that any strategy is profitable, and no result here should be read as a
claim of an edge.
