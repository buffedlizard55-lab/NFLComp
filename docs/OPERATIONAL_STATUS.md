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

## Published window versus complete simulation

`data/bets_ledger.json` publishes a recent-season window so that the repository
and the GitHub Pages artefact stay small. The complete simulation totals, the
window boundaries, the chain head and the snapshot hashes live in
`data/ledger_manifest.json`; each leaderboard row carries both its published-window
and all-time figures plus the difference. Nothing outside the window is deleted:
it is aggregated and labelled. A published record is append-only — any edit
breaks the hash chain, which `engine.ledger.verify_chain` detects from the
published bytes alone.

## Reproducibility

A full run is deterministic: two consecutive `python3 scripts/run_pipeline.py`
executions produced identical summary figures and an identical SHA-256 digest of
the published ledger. Model randomness comes from a seeded local generator
(`MonteCarloModel`), never from process-global RNG state.

## Verification commands

```bash
python3 scripts/run_pipeline.py --check-only     # data + generated docs + audit
python3 -m engine.audit_verifier --check         # audit only, exits non-zero on failure
python3 -m engine.ledger --verify data/bets_ledger.json
python3 scripts/render_readme.py --check
python3 scripts/render_verification.py --check
python3 scripts/render_claims.py --check
python3 test/engine.test.py
node test/ui.test.js
python3 -m py_compile engine/*.py
```

Passing tests validate software contracts, arithmetic and that the published
numbers re-derive from the checked-in data. They do not establish a profitable
betting edge.
