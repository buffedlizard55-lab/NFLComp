"""Risk, calibration and capital-sufficiency analytics for the paper ledger.

The leaderboard reports PnL, ROI, win rate and max drawdown. That is not enough
to say whether a persona's history is *distinguishable* from noise, or whether
its pricing is calibrated. This module adds, from the published ledger alone:

* per-persona risk — Sharpe and Sortino on the per-bet return series, longest
  losing streak, drawdown duration, profit factor and payoff ratio;
* capital sufficiency — the fractional-Kelly stake the persona's own realised
  win rate and average price imply, against the stake it actually used, plus a
  seeded bootstrap of its bet sequence giving a 95% ROI interval and the
  probability of a 25% drawdown;
* calibration — Brier score, log loss and expected calibration error for the
  model probabilities recorded on every settled bet, binned decile by decile,
  with per-market splits;
* portfolio concentration — how much of the published PnL one persona explains,
  and the correlation of per-season PnL between the largest personas.

Every number is derived from ``data/bets_ledger.json``; the bootstrap uses a
seeded local generator so two runs produce identical output. A persona with too
few settled bets is reported with its sample size and ``insufficient_sample``
rather than an implied verdict.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Below this many settled bets a per-persona statistic is not reportable.
MIN_SETTLED_BETS = 100
#: Bootstrap resamples and seed; fixed so the export is reproducible.
BOOTSTRAP_ITERATIONS = 1000
BOOTSTRAP_SEED = 20260917
#: Drawdown level whose bootstrap probability is reported.
DRAWDOWN_LEVEL = 0.25
#: Bins used for the calibration curve.
CALIBRATION_BINS = 10


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = sum(values) / len(values)
    return math.sqrt(sum((v - avg) ** 2 for v in values) / (len(values) - 1))


def sharpe_ratio(returns: list[float], periods_per_year: float) -> float | None:
    """Annualised Sharpe of a per-bet return series with zero risk-free rate."""
    if len(returns) < 2:
        return None
    sd = stdev(returns)
    avg = mean(returns)
    if not sd or not avg:
        return None
    return round((avg / sd) * math.sqrt(periods_per_year), 3)


def sortino_ratio(returns: list[float], periods_per_year: float) -> float | None:
    """Annualised Sortino: mean return over downside deviation only."""
    if len(returns) < 2:
        return None
    avg = mean(returns)
    downside = [r for r in returns if r < 0]
    if not downside or not avg:
        return None
    downside_dev = math.sqrt(sum(r * r for r in downside) / len(returns))
    if downside_dev == 0:
        return None
    return round((avg / downside_dev) * math.sqrt(periods_per_year), 3)


def brier_score(pairs: list[tuple[float, float]]) -> float | None:
    """Mean squared error of a probability forecast; lower is better."""
    if not pairs:
        return None
    return round(sum((p - outcome) ** 2 for p, outcome in pairs) / len(pairs), 5)


def log_loss(pairs: list[tuple[float, float]], epsilon: float = 1e-6) -> float | None:
    if not pairs:
        return None
    total = 0.0
    for probability, outcome in pairs:
        clipped = min(1.0 - epsilon, max(epsilon, probability))
        total += -(outcome * math.log(clipped) + (1 - outcome) * math.log(1 - clipped))
    return round(total / len(pairs), 5)


def calibration_bins(pairs: list[tuple[float, float]], bins: int = CALIBRATION_BINS) -> list[dict]:
    """Decile reliability table plus the expected calibration error."""
    buckets: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for probability, outcome in pairs:
        index = min(bins - 1, max(0, int(probability * bins)))
        buckets[index].append((probability, outcome))
    table = []
    total = len(pairs) or 1
    expected_calibration_error = 0.0
    for index, bucket in enumerate(buckets, 1):
        if not bucket:
            table.append({
                "decile": index,
                "range": f"{(index - 1) / bins:.1f}-{index / bins:.1f}",
                "bets": 0,
                "mean_model_prob": None,
                "observed_win_rate": None,
                "gap_pct_points": None,
            })
            continue
        avg_probability = sum(p for p, _ in bucket) / len(bucket)
        observed = sum(o for _, o in bucket) / len(bucket)
        gap = observed - avg_probability
        expected_calibration_error += abs(gap) * len(bucket) / total
        table.append({
            "decile": index,
            "range": f"{(index - 1) / bins:.1f}-{index / bins:.1f}",
            "bets": len(bucket),
            "mean_model_prob": round(avg_probability, 4),
            "observed_win_rate": round(observed, 4),
            "gap_pct_points": round(100.0 * gap, 2),
        })
    return table, round(100.0 * expected_calibration_error, 3)


def max_drawdown(returns: list[float], stake_unit: float) -> float:
    """Peak-to-trough drawdown of the cumulative PnL series."""
    cumulative = 0.0
    peak = 0.0
    worst = 0.0
    for value in returns:
        cumulative += value
        peak = max(peak, cumulative)
        worst = max(worst, peak - cumulative)
    return round(worst / stake_unit, 4) if stake_unit else 0.0


def longest_losing_streak(returns: list[float]) -> int:
    longest = current = 0
    for value in returns:
        if value < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def drawdown_duration_bets(returns: list[float]) -> int:
    """Longest run of bets spent below a previous equity peak."""
    cumulative = peak = 0.0
    longest = current = 0
    for value in returns:
        cumulative += value
        if cumulative < peak:
            current += 1
            longest = max(longest, current)
        else:
            peak = cumulative
            current = 0
    return longest


def kelly_full_fraction(win_rate: float, decimal_odds: float) -> float | None:
    """Full-Kelly bankroll fraction, negative when the price implies no bet."""
    if decimal_odds <= 1.0 or not 0.0 < win_rate < 1.0:
        return None
    net = decimal_odds - 1.0
    return (win_rate * net - (1.0 - win_rate)) / net


def kelly_fraction(win_rate: float, decimal_odds: float, fraction: float = 0.25) -> float | None:
    """Fractional Kelly stake for a binary bet at ``decimal_odds`` (never negative)."""
    full = kelly_full_fraction(win_rate, decimal_odds)
    if full is None:
        return None
    return round(max(0.0, full) * fraction, 6)


def bootstrap_roi(returns: list[float], stake: float, iterations: int = BOOTSTRAP_ITERATIONS,
                  seed: int = BOOTSTRAP_SEED, drawdown_level: float = DRAWDOWN_LEVEL) -> dict:
    """Resample the bet sequence to get an ROI interval and drawdown probability.

    Wins and losses are resampled as a block, which preserves the payoff
    distribution (odds vary bet to bet) but not any autocorrelation.
    """
    if not returns:
        return {"iterations": 0}
    generator = random.Random(seed)
    # ``returns`` are per unit staked, so a resampled sequence's ROI is its mean.
    rois = []
    drawdown_hits = 0
    for _ in range(iterations):
        sample = [returns[generator.randrange(len(returns))] for _ in returns]
        rois.append(sum(sample) / len(sample))
        # Drawdown is measured in stake units: a 25% bankroll hit at a 1% flat
        # stake is 25 stake units, independent of the stake's dollar size.
        bankroll_units = 100.0
        if max_drawdown(sample, 1.0) >= drawdown_level * bankroll_units:
            drawdown_hits += 1
    rois.sort()
    def percentile(pct: float) -> float:
        index = min(len(rois) - 1, max(0, int(round(pct / 100.0 * (len(rois) - 1)))))
        return round(100.0 * rois[index], 2)
    return {
        "iterations": iterations,
        "seed": seed,
        "roi_pct_ci95": [percentile(2.5), percentile(97.5)],
        "roi_pct_median": percentile(50),
        "probability_roi_positive_pct": round(100.0 * sum(1 for r in rois if r > 0) / len(rois), 2),
        "probability_of_drawdown_pct": round(100.0 * drawdown_hits / iterations, 2),
        "drawdown_level_pct": round(100.0 * drawdown_level, 1),
    }


# ---------------------------------------------------------------------------
# Ledger analytics
# ---------------------------------------------------------------------------

def _outcome(bet: dict) -> float | None:
    result = bet.get("result")
    if result == "WIN":
        return 1.0
    if result == "LOSS":
        return 0.0
    return None


def _decimal_odds(bet: dict) -> float | None:
    odds = bet.get("odds_val")
    if odds is None:
        return None
    if bet.get("odds_format") == "Cents":
        return round(100.0 / odds, 6) if odds else None
    if odds > 0:
        return 1.0 + odds / 100.0
    if odds < 0:
        return 1.0 + 100.0 / abs(odds)
    return None


def _per_bet_return(bet: dict) -> float | None:
    """Net return per unit staked, from the ledger's own PnL and stake."""
    stake = bet.get("stake") or 0.0
    if not stake:
        return None
    return bet.get("pnl", 0.0) / stake


def _per_year_rate(bets: list[dict]) -> float:
    seasons = {bet.get("season") for bet in bets if bet.get("season")}
    seasons = seasons or {0}
    return len(bets) / max(1, len(seasons))


def persona_risk(bets: list[dict], leaderboard_row: dict) -> dict:
    """Risk statistics for one persona's settled published bets."""
    returns = [r for r in (_per_bet_return(bet) for bet in bets) if r is not None]
    settled = [bet for bet in bets if bet.get("result") in {"WIN", "LOSS"}]
    stake = settled[0].get("stake") if settled else 100.0
    unit_stake = float(stake or 100.0)
    wins = sum(1 for bet in settled if bet["result"] == "WIN")
    losses = len(settled) - wins
    gross_win = sum(bet["pnl"] for bet in settled if bet["pnl"] > 0)
    gross_loss = -sum(bet["pnl"] for bet in settled if bet["pnl"] < 0)
    win_rate = wins / len(settled) if settled else None
    prices = [_decimal_odds(bet) for bet in settled if _decimal_odds(bet)]
    average_price = mean(prices) if prices else None
    record = {
        "strategy_id": leaderboard_row.get("id"),
        "username": leaderboard_row.get("username"),
        "published_bets": len(bets),
        "settled_bets": len(settled),
        "insufficient_sample": len(settled) < MIN_SETTLED_BETS,
        "minimum_settled_bets": MIN_SETTLED_BETS,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "average_decimal_odds": round(average_price, 4) if average_price else None,
        "profit_factor": (round(gross_win / gross_loss, 3) if gross_loss else None),
        "payoff_ratio": (round((gross_win / wins) / (gross_loss / losses), 3) if wins and losses and gross_loss else None),
        "sharpe_annualised": sharpe_ratio(returns, _per_year_rate(bets)) if returns else None,
        "sortino_annualised": sortino_ratio(returns, _per_year_rate(bets)) if returns else None,
        "per_bet_return_stdev": round(stdev(returns), 5) if returns and stdev(returns) is not None else None,
        "max_drawdown_stake_units": max_drawdown(returns, 1.0) if returns else None,
        "longest_losing_streak": longest_losing_streak(returns),
        "longest_drawdown_bets": drawdown_duration_bets(returns),
    }
    if win_rate is not None and average_price:
        full_kelly = kelly_full_fraction(win_rate, average_price)
        quarter_kelly = kelly_fraction(win_rate, average_price)
        record["implied_full_kelly_pct"] = round(100.0 * full_kelly, 4) if full_kelly is not None else None
        record["implied_quarter_kelly_stake_pct"] = (
            round(100.0 * quarter_kelly, 4) if quarter_kelly is not None else None)
        bankroll = leaderboard_row.get("initial_bankroll") or 10000.0
        record["actual_stake_pct_of_initial_bankroll"] = round(100.0 * unit_stake / bankroll, 3)
        # A realised win rate below break-even at the persona's own average price
        # implies no positive stake at all; that is a finding, not a zero size.
        record["history_implies_no_positive_stake"] = bool(full_kelly is not None and full_kelly <= 0)
        if quarter_kelly:
            kelly_stake = quarter_kelly * bankroll
            record["stake_vs_implied_quarter_kelly_ratio"] = round(unit_stake / kelly_stake, 3)
            record["over_betting_implied_quarter_kelly"] = bool(unit_stake > kelly_stake)
    if returns:
        record["bootstrap"] = bootstrap_roi(returns, unit_stake)
        record["observed_roi_pct"] = round(100.0 * sum(returns) / len(returns), 3)
        if record.get("observed_roi_pct") is not None:
            low, high = record["bootstrap"]["roi_pct_ci95"]
            record["observed_roi_inside_bootstrap_ci"] = bool(low <= record["observed_roi_pct"] <= high)
    return record


def calibration_section(bets: list[dict]) -> dict:
    """Brier score, log loss and reliability table by model probability."""
    pairs = []
    by_market: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for bet in bets:
        outcome = _outcome(bet)
        probability = bet.get("model_prob")
        if outcome is None or probability is None:
            continue
        pairs.append((float(probability), outcome))
        by_market[bet.get("market", "UNKNOWN")].append((float(probability), outcome))
    table, expected_calibration_error = calibration_bins(pairs) if pairs else ([], None)
    return {
        "settled_bets_with_model_probability": len(pairs),
        "brier_score": brier_score(pairs),
        "log_loss": log_loss(pairs),
        "expected_calibration_error_pct_points": expected_calibration_error,
        "base_win_rate": round(sum(o for _, o in pairs) / len(pairs), 4) if pairs else None,
        "reliability_table": table,
        "by_market": {
            market: {
                "settled_bets": len(market_pairs),
                "brier_score": brier_score(market_pairs),
                "log_loss": log_loss(market_pairs),
                "expected_calibration_error_pct_points": calibration_bins(market_pairs)[1],
                "base_win_rate": round(sum(o for _, o in market_pairs) / len(market_pairs), 4),
            }
            for market, market_pairs in sorted(by_market.items(), key=lambda item: -len(item[1]))
        },
    }


def portfolio_section(bets: list[dict], risk_records: list[dict]) -> dict:
    """Concentration and co-movement of PnL across personas."""
    pnl_by_persona: dict[str, float] = defaultdict(float)
    season_pnl: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for bet in bets:
        key = bet.get("strategy_id") or bet.get("username") or "UNKNOWN"
        pnl_by_persona[key] += bet.get("pnl", 0.0)
        season = bet.get("season")
        if season is not None:
            season_pnl[key][season] += bet.get("pnl", 0.0)
    total = sum(pnl_by_persona.values())
    magnitudes = {key: abs(value) for key, value in pnl_by_persona.items()}
    total_magnitude = sum(magnitudes.values()) or 1.0
    ranked = sorted(pnl_by_persona.items(), key=lambda item: -abs(item[1]))
    top_share = round(100.0 * abs(ranked[0][1]) / total_magnitude, 2) if ranked else None
    positives = [(key, value) for key, value in pnl_by_persona.items() if value > 0]
    negatives = [(key, value) for key, value in pnl_by_persona.items() if value < 0]
    hhi = round(sum((value / total_magnitude) ** 2 for value in magnitudes.values()), 4)

    # Pearson correlation of per-season PnL between the five largest personas.
    leaders = [key for key, _ in ranked[:5]]
    seasons = sorted({season for values in season_pnl.values() for season in values})
    correlations = []
    for index, first in enumerate(leaders):
        for second in leaders[index + 1:]:
            a = [season_pnl[first].get(season, 0.0) for season in seasons]
            b = [season_pnl[second].get(season, 0.0) for season in seasons]
            avg_a, avg_b = mean(a) or 0.0, mean(b) or 0.0
            var_a = sum((x - avg_a) ** 2 for x in a)
            var_b = sum((y - avg_b) ** 2 for y in b)
            if not var_a or not var_b:
                continue
            covariance = sum((x - avg_a) * (y - avg_b) for x, y in zip(a, b))
            correlations.append({
                "first": first,
                "second": second,
                "pearson_r_by_season_pnl": round(covariance / math.sqrt(var_a * var_b), 3),
                "seasons": len(seasons),
            })
    return {
        "personas_with_published_pnl": len(pnl_by_persona),
        "published_pnl_total_usd": round(total, 2),
        "pnl_magnitude_total_usd": round(total_magnitude, 2),
        "largest_abs_pnl_persona": ranked[0][0] if ranked else None,
        "largest_abs_pnl_share_of_gross_movement_pct": top_share,
        "herfindahl_index_of_gross_pnl": hhi,
        "personas_positive": len(positives),
        "personas_negative": len(negatives),
        "best_persona": max(positives, key=lambda item: item[1]) if positives else None,
        "worst_persona": min(negatives, key=lambda item: item[1]) if negatives else None,
        "top5_season_pnl_correlations": correlations,
        "risk_reporting_floor_settled_bets": MIN_SETTLED_BETS,
        "personas_at_or_above_floor": len([r for r in risk_records
                                           if not r.get("insufficient_sample") and r.get("settled_bets")]),
    }


def build_report(data_dir: str | Path = ROOT / "data") -> dict:
    """Build the whole risk/calibration report from the published ledger."""
    data_dir = Path(data_dir)
    try:
        ledger = json.loads((data_dir / "bets_ledger.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ledger = []
    try:
        leaderboard = json.loads((data_dir / "leaderboard.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        leaderboard = []

    by_persona: dict[str, list[dict]] = defaultdict(list)
    for bet in ledger:
        by_persona[bet.get("strategy_id", "UNKNOWN")].append(bet)

    risk_records = []
    for row in leaderboard:
        bets = by_persona.get(row.get("id"), [])
        record = persona_risk(bets, row)
        record["all_time_bets"] = row.get("all_time_bets")
        record["all_time_pnl_usd"] = row.get("total_pnl")
        risk_records.append(record)
    risk_records.sort(key=lambda record: (record.get("settled_bets") or 0), reverse=True)

    calibration = calibration_section(ledger)
    portfolio = portfolio_section(ledger, risk_records)
    evaluated = [record for record in risk_records if not record.get("insufficient_sample")]
    return {
        "generated_by": "engine/risk_analytics.py::build_report",
        "classification": "DERIVED_DATA",
        "source": {
            "ledger": "data/bets_ledger.json",
            "leaderboard": "data/leaderboard.json",
            "published_records": len(ledger),
            "personas": len(leaderboard),
        },
        "policy": {
            "minimum_settled_bets": MIN_SETTLED_BETS,
            "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "drawdown_level_pct": round(100.0 * DRAWDOWN_LEVEL, 1),
            "annualisation": "Sharpe/Sortino annualised by published bets per season in the window",
            "warning": "These statistics describe the simulated published window. A positive Sharpe or a "
                       "calibrated probability does not imply a profitable edge, and the bootstrap assumes the "
                       "bets are exchangeable, which a real market would not be.",
        },
        "calibration": calibration,
        "portfolio": portfolio,
        "personas": risk_records,
        "summary": {
            "personas": len(risk_records),
            "personas_meeting_reporting_floor": len(evaluated),
            "best_sharpe": max((r for r in evaluated if r.get("sharpe_annualised") is not None),
                               key=lambda r: r["sharpe_annualised"], default={}).get("username"),
            "best_sharpe_value": max((r["sharpe_annualised"] for r in evaluated
                                      if r.get("sharpe_annualised") is not None), default=None),
            "worst_sharpe_value": min((r["sharpe_annualised"] for r in evaluated
                                       if r.get("sharpe_annualised") is not None), default=None),
            "personas_betting_above_implied_quarter_kelly": len(
                [r for r in evaluated if r.get("over_betting_implied_quarter_kelly")]),
            "personas_whose_history_implies_no_positive_stake": len(
                [r for r in evaluated if r.get("history_implies_no_positive_stake")]),
            "portfolio_brier_score": calibration.get("brier_score"),
            "expected_calibration_error_pct_points": calibration.get("expected_calibration_error_pct_points"),
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--out", default=None)
    parser.add_argument("--check", action="store_true",
                        help="fail if the checked-in report does not re-derive from the ledger")
    args = parser.parse_args(argv)

    report = build_report(args.data_dir)
    out_path = Path(args.out) if args.out else Path(args.data_dir) / "risk_analytics.json"
    rendered = json.dumps(report, indent=2) + "\n"

    if args.check:
        try:
            current = out_path.read_text(encoding="utf-8")
        except OSError:
            print(f"{out_path} is missing; run python3 -m engine.risk_analytics")
            return 1
        if current != rendered:
            print(f"{out_path} is stale; run python3 -m engine.risk_analytics")
            return 1
        print(f"{out_path} re-derives from the ledger "
              f"(Brier {report['summary']['portfolio_brier_score']}, "
              f"ECE {report['summary']['expected_calibration_error_pct_points']} pts)")
        return 0

    out_path.write_text(rendered, encoding="utf-8")
    summary = report["summary"]
    print(f"Wrote {out_path}: {summary['personas']} personas "
          f"({summary['personas_meeting_reporting_floor']} above the {MIN_SETTLED_BETS}-bet floor), "
          f"Brier {summary['portfolio_brier_score']}, ECE {summary['expected_calibration_error_pct_points']} pts, "
          f"{summary['personas_betting_above_implied_quarter_kelly']} above implied quarter-Kelly, "
          f"{summary['personas_whose_history_implies_no_positive_stake']} whose own history implies no stake")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
