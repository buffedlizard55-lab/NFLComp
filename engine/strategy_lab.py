"""Reproducible strategy development and holdout testing.

This lab evaluates pre-declared rules against fields that are present in the
bundled nflverse game snapshot. It does not search the holdout period for a
better threshold and does not turn a positive backtest into a performance
promise. New rules remain paper-trading candidates after passing holdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from engine.data_loader import NFLDataLoader
from engine.models import calculate_pnl
from engine.settlement import settle_spread, settle_total


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    hypothesis: str
    market: str
    required_fields: tuple[str, ...]
    rule: str
    select: Callable[[dict], str | None]
    lineage_parent: str | None = None


def _rest_four_day_side(game: dict) -> str | None:
    rest_diff = game.get("rest_diff")
    if rest_diff is None or abs(rest_diff) < 4 or game.get("spread_line") is None:
        return None
    side = "home" if rest_diff > 0 else "away"
    if not game.get(f"{side}_spread_odds_recorded"):
        return None
    return side


def _divisional_high_total_side(game: dict) -> str | None:
    if not game.get("under_odds_recorded"):
        return None
    if game.get("div_game") and game.get("total_line") is not None and game["total_line"] >= 47.0:
        return "under"
    return None


CANDIDATES = (
    Candidate(
        id="STRAT_REST_TNF_005_v3",
        name="Four-Day Rest Differential ATS",
        hypothesis="A team with at least four more rest days than its opponent may cover more often than the market price implies.",
        market="SPREAD",
        required_fields=("home_rest", "away_rest", "spread_line", "home_spread_odds", "away_spread_odds", "home_score", "away_score"),
        rule="Regular-season game; absolute home_rest - away_rest >= 4; back the more-rested team at the recorded spread price.",
        select=_rest_four_day_side,
        lineage_parent="STRAT_REST_TNF_005_v1",
    ),
    Candidate(
        id="STRAT_DIV_TOTAL_040_v1",
        name="Divisional High-Total Under",
        hypothesis="Divisional familiarity may reduce scoring relative to high posted totals.",
        market="TOTAL",
        required_fields=("div_game", "total_line", "total", "under_odds"),
        rule="Regular-season divisional game with recorded total >= 47.0; test the Under at the recorded price.",
        select=_divisional_high_total_side,
    ),
)

WINDOWS = (
    ("development", 2000, 2019),
    ("validation", 2020, 2022),
    ("holdout", 2023, 2025),
)


def _source_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evaluate_bet(candidate: Candidate, game: dict, side: str) -> tuple[float, float]:
    if candidate.market == "SPREAD":
        outcome = settle_spread(game["result"], game["spread_line"], side)
        odds = game["home_spread_odds"] if side == "home" else game["away_spread_odds"]
    elif candidate.market == "TOTAL":
        outcome = settle_total(game["total"], game["total_line"], side)
        odds = game["over_odds"] if side == "over" else game["under_odds"]
    else:
        raise ValueError(f"Unsupported candidate market: {candidate.market}")
    return outcome, calculate_pnl(100.0, odds, outcome)


def evaluate_candidate(candidate: Candidate, games: list[dict]) -> dict:
    def source_value_missing(game: dict, field: str) -> bool:
        recorded_flag = f"{field}_recorded"
        if recorded_flag in game:
            return not game[recorded_flag]
        return game.get(field) is None

    missing_counts = {field: sum(source_value_missing(game, field) for game in games) for field in candidate.required_fields}
    windows = {}
    for label, first_season, last_season in WINDOWS:
        observations = []
        for game in games:
            if game.get("game_type") != "REG" or not game.get("completed"):
                continue
            if not first_season <= game["season"] <= last_season:
                continue
            side = candidate.select(game)
            if side is None:
                continue
            outcome, pnl = _evaluate_bet(candidate, game, side)
            observations.append((outcome, pnl))

        wins = sum(outcome == 1.0 for outcome, _ in observations)
        losses = sum(outcome == 0.0 for outcome, _ in observations)
        pushes = sum(outcome == 0.5 for outcome, _ in observations)
        pnl = sum(value for _, value in observations)
        resolved = wins + losses
        windows[label] = {
            "seasons": f"{first_season}-{last_season}",
            "bets": len(observations),
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate_pct": round(100.0 * wins / resolved, 2) if resolved else None,
            "flat_stake_pnl": round(pnl, 2),
            "roi_pct": round(100.0 * pnl / (100.0 * len(observations)), 2) if observations else None,
        }

    enough_data = windows["development"]["bets"] >= 100 and windows["validation"]["bets"] >= 40 and windows["holdout"]["bets"] >= 40
    positive_each_window = all(windows[name]["roi_pct"] is not None and windows[name]["roi_pct"] > 0 for name, _, _ in WINDOWS)
    if not enough_data:
        status = "INSUFFICIENT_SAMPLE"
        next_step = "Collect more settled observations; do not promote."
    elif positive_each_window:
        status = "HOLDOUT_PASSED"
        next_step = "Register for prospective paper trading; holdout results are not a profit guarantee."
    else:
        status = "HOLDOUT_FAILED"
        next_step = "Keep the rule archived; do not tune it on the holdout period."

    return {
        "strategy_id": candidate.id,
        "name": candidate.name,
        "lineage_parent": candidate.lineage_parent,
        "hypothesis": candidate.hypothesis,
        "market": candidate.market,
        "rule": candidate.rule,
        "required_fields": list(candidate.required_fields),
        "missing_value_counts_in_loaded_games": missing_counts,
        "windows": windows,
        "status": status,
        "next_step": next_step,
        "performance_claim": None,
    }


def build_report(source_dir: str = "data/source") -> dict:
    source_path = Path(source_dir) / "games.csv"
    games = NFLDataLoader(source_dir).load_all()
    completed = [game for game in games if game.get("completed")]
    return {
        "schema_version": 1,
        "research_class": "PAPER_TRADING_STRATEGY_LAB",
        "source": {
            "path": source_path.as_posix(),
            "sha256": _source_hash(source_path),
            "loaded_games": len(games),
            "completed_games": len(completed),
            "latest_completed_gameday": max(game["gameday"] for game in completed),
        },
        "policy": {
            "development_window": "2000-2019",
            "validation_window": "2020-2022",
            "untouched_holdout_window": "2023-2025",
            "stake": "$100 flat per qualifying observation",
            "promotion_gate": "At least 100 development, 40 validation, and 40 holdout bets; positive ROI in all three windows.",
            "warning": "Passing this historical gate authorizes prospective paper testing only. It is not evidence of guaranteed future profit.",
        },
        "candidates": [evaluate_candidate(candidate, games) for candidate in CANDIDATES],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate pre-declared NFL strategy candidates without holdout tuning.")
    parser.add_argument("--source-dir", default="data/source")
    parser.add_argument("--output", default="data/strategy_lab.json")
    parser.add_argument("--check", action="store_true", help="Fail when the checked-in report differs from a fresh evaluation.")
    args = parser.parse_args()

    report = build_report(args.source_dir)
    rendered = json.dumps(report, indent=2) + "\n"
    output = Path(args.output)
    if args.check:
        if not output.exists() or output.read_text() != rendered:
            raise SystemExit(f"Strategy lab report is stale: run python -m engine.strategy_lab --output {output}")
        print(f"Strategy lab report is reproducible: {output}")
        return
    output.write_text(rendered)
    print(f"Wrote {len(report['candidates'])} strategy evaluations to {output}")


if __name__ == "__main__":
    main()
