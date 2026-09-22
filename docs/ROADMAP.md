# Research Roadmap & Pipeline — NFLComp

This document outlines ongoing and scheduled enhancements for future NFL research seasons.

## Continuous strategy cycle (primary priority)

Every research cycle must add or explicitly reject pre-declared strategy candidates. The weekly automation verifies that `data/strategy_lab.json` is reproducible from the exact `games.csv` snapshot and runs both test suites. New source snapshots require a fresh report, but holdout thresholds must never be tuned after viewing holdout output.

Current cycle (statuses, windows and samples are shown in the generated table in
`README.md`; `data/strategy_lab.json` is the source of truth and
`python3 -m engine.strategy_lab --check` proves it re-derives from the snapshot):
- `STRAT_DIV_TOTAL_040_v1` cleared the declared gate (100 development / 40 validation / 40 holdout bets
  with positive ROI in all three) and is eligible for prospective paper testing only.
- `STRAT_REST_TNF_005_v3` failed the untouched holdout window and stays archived with its rule unchanged,
  so the failure is not re-tested or tuned away.
- Next candidates must be based only on fields with retained source/provenance. Player props, live markets,
  and order-book rules stay blocked until timestamped prices and observable outcomes exist.
- A research claim the bundled snapshot cannot re-derive is labelled `DECLARED_ASSUMPTION` in
  `data/research_experiments.json`; do not promote one to a measured result without a re-derivation study in
  `engine/empirical_studies.py`.

A candidate is valuable even when it fails: retain the fixed rule and failure result to prevent repeated testing and survivorship bias.

---

## 1. Advanced Modeling Tracks
- **Track A (NextGen Stats Spatial Tracking):** Ingest receiver separation and pass rusher closing speed from AWS NextGen Stats to construct micro-level offensive line pass block win rate (PBWR) models.
- **Track B (In-Game Micro-Betting Engine):** Extend walk-forward simulator to drive by-drive live betting on Kalshi in-game turnover and drive outcome markets.
- **Track C (Bayesian Hierarchical EPA):** Implement Bayesian hierarchical shrinkage for early-season quarterback transfers and rookie signal callers to eliminate sample-size variance in Weeks 1–4.

---

## 2. Platform & Infrastructure Enhancements
- **Automated Discord / Slack Webhook Dispatch:** Real-time push notifications when upcoming bets transition from `WATCHING` to `QUALIFIED` or `READY TO BET` as line movements cross threshold.
- **Multi-Bookmaker Best-Execution Router:** Expand line shopping across Circa Sports, BookMaker, Pinnacle, DraftKings, and FanDuel to quantify execution slippage reduction.
- **Automated Synthetic Game Monte Carlo Engine:** Real-time in-browser Monte Carlo simulator allowing users to tweak game script parameters (e.g. weather, injuries, turnovers) and watch the strategy qualification state mutate dynamically.
