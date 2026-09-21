# Operational status and evidence policy

**As of 2026-09-21 (America/Los_Angeles)**, NFLComp is a research and paper-trading prototype. It never submits real orders.

## What is executable

- `engine.data_loader.NFLDataLoader` loads the checked-in source snapshot and preserves missing market prices as `null`.
- `engine.provenance` creates SHA-256 snapshot metadata, validates point-in-time availability, and returns only observed side-specific prices.
- `engine.backtest_engine.NFLBacktestRunner` walks games chronologically and suppresses historical signals when a timestamped side price is absent.
- `engine.ledger` provides an append-only newline JSON hash chain for new paper bets.
- `engine.settlement` settles spreads and totals from observed final scores only.

## Evidence boundaries

The checked-in dashboard JSON files are read-model fixtures. Their presence is not independent proof that every row was retrieved during this run. Historical price claims require a source snapshot, retrieval/availability timestamp, and a side-specific observed price. Player props, live markets, alternate lines, and unarchived Kalshi books remain forward-test or research-only unless those artifacts are present.

Model projections are labelled `MODEL_OUTPUT`; they must not be used as observed prices, fills, results, or settlement outcomes. Missing, conflicting, or late data belongs in `data/irregularities.json` and is not silently imputed.

## Verification commands

```bash
python3 test/engine.test.py
node test/ui.test.js
python3 -m py_compile engine/*.py
```

Passing tests validate software contracts and arithmetic. They do not establish a profitable betting edge.
