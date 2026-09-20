# Research Roadmap & Pipeline — NFLComp

This document outlines ongoing and scheduled enhancements for future NFL research seasons.

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
