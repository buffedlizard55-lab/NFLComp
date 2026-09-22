"""Re-derive the research claims the snapshot can support, and label the rest.

``engine/backtest_engine.py`` authors ``data/research_experiments.json`` as a
hand-written research dossier, and several of its findings (a 56.8% Under rate
in 15-19 mph wind, a 58.1% Thursday home cover rate, a +6.8 cent Kalshi edge)
read like measured results. Some of those *are* measurable from the bundled
``data/source/games.csv`` snapshot; others need play-by-play, player tracking or
an archived order book that this repository does not ship.

This module keeps the two apart:

* ``studies`` — recomputed here from the snapshot, with sample size, effect
  size, a Wilson 95% interval and, where a price is recorded, a flat-stake
  result. Each study declares the snapshot columns it used.
* ``declared_assumptions`` — catalog claims the snapshot cannot re-derive,
  published with the reason so no document can present them as measurements.
* ``cross_checks`` — where a declared number overlaps a computed study, both
  values are kept; disagreement beyond tolerance is reported, never resolved by
  overwriting either side.

Nothing here invents an observation: a study with too small a sample is still
reported, with its sample size, rather than being tuned into significance.

Usage::

    python3 -m engine.empirical_studies            # rebuild data/empirical_studies.json
    python3 -m engine.empirical_studies --check     # prove the checked-in file re-derives
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Flat stake used for every study result, so studies stay comparable.
STAKE = 100.0

#: Declared tolerance for a hand-typed catalogue number to count as agreeing
#: with the snapshot re-derivation (percentage points).
CROSS_CHECK_TOLERANCE_PCT = 1.0

#: Experiments in ``data/research_experiments.json`` that this snapshot cannot
#: re-derive, with the artifact that would be required instead.
UNSUPPORTED_EXPERIMENTS = {
    "EXP_002_BACKUP_QB_SPREAD_SHOCK": "requires per-game starting-QB and open/close line history beyond the bundled columns",
    "EXP_003_KALSHI_BINARY_VS_POISSON": "requires an archived Kalshi order book with timestamps",
    "EXP_005_OL_CONTINUITY": "requires snap counts / offensive-line participation",
    "EXP_006_DEF_PRESSURE": "requires play-by-play pressure and sack attribution",
    "EXP_007_GAME_SCRIPT": "requires play-by-play pace and pass-rate tracking",
    "EXP_008_PLAYER_PROP_USAGE": "requires player-level target share and route participation",
}

#: Declared experiment -> the study that re-derives it from the snapshot.
RE_DERIVED_BY = {
    "EXP_001_WEATHER_WIND_THRESHOLD": "STUDY_WIND_TOTALS",
    "EXP_004_TNF_SHORT_REST_TRAVEL": "STUDY_TNF_REST_TRAVEL",
}

#: Study -> the personas whose hypothesis that study speaks to.
STUDY_STRATEGIES = {
    "STUDY_WIND_TOTALS": ["STRAT_WEATHER_WIND_003_v1", "STRAT_WEATHER_WIND_003_v2", "STRAT_WEATHER_WIND_003_v3"],
    "STUDY_TNF_REST_TRAVEL": ["STRAT_REST_TNF_005_v1", "STRAT_REST_TNF_005_v2", "STRAT_REST_TNF_005_v3",
                              "STRAT_TNF_UNDER_012_v1"],
    "STUDY_DIVISIONAL_HIGH_TOTAL_UNDER": ["STRAT_DIV_TOTAL_040_v1"],
    "STUDY_HOME_UNDERDOG_ATS": ["STRAT_HOME_DOG_042_v1"],
    "STUDY_DOME_TOTALS": ["STRAT_DOME_PACE_004_v1", "STRAT_DOME_PACE_004_v2"],
}


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def wilson_interval(successes: int, trials: int, z: float = 1.959963985) -> tuple[float, float] | None:
    """Two-sided 95% Wilson score interval for a binomial proportion."""
    if trials <= 0:
        return None
    phat = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (phat + z * z / (2 * trials)) / denominator
    spread = z * math.sqrt((phat * (1 - phat) + z * z / (4 * trials)) / trials) / denominator
    return (round(100.0 * max(0.0, centre - spread), 2), round(100.0 * min(1.0, centre + spread), 2))


def _rate(successes: int, trials: int) -> float | None:
    return round(100.0 * successes / trials, 2) if trials else None


def _float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Snapshot loading
# ---------------------------------------------------------------------------

def load_games(source_dir: str | Path) -> list[dict]:
    """Load ``games.csv`` as floats where numeric, keeping missing values as None.

    Sign convention: the raw snapshot's ``spread_line`` is positive when the
    *home* team is favoured (home win rate rises from 23% at -7 or lower to 80%
    at +7 or higher). The loader negates it so that a negative value is a home
    handicap, matching ``engine.settlement``. The negation is applied here too;
    without it a cover-rate study inverts every result. Under the corrected
    convention home teams cover 48.97% of 6,794 decided games, which is the
    ~50% a correctly signed ATS measurement should produce.
    """
    path = Path(source_dir) / "games.csv"
    if not path.exists():
        return []
    games = []
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for row in csv.DictReader(handle):
            if row.get("game_type") != "REG":
                continue
            home_score = _float(row.get("home_score"))
            away_score = _float(row.get("away_score"))
            games.append({
                "game_id": row.get("game_id"),
                "season": int(_float(row.get("season")) or 0),
                "week": int(_float(row.get("week")) or 0),
                "gameday": row.get("gameday"),
                "weekday": row.get("weekday"),
                "roof": (row.get("roof") or "").strip(),
                "wind": _float(row.get("wind")),
                "temp": _float(row.get("temp")),
                # Home handicap: negative means the home team gives the points.
                "spread_line": (-_float(row.get("spread_line"))
                                if _float(row.get("spread_line")) is not None else None),
                "total_line": _float(row.get("total_line")),
                "home_rest": _float(row.get("home_rest")),
                "away_rest": _float(row.get("away_rest")),
                "div_game": _float(row.get("div_game") or 0) == 1.0,
                "home_score": home_score,
                "away_score": away_score,
                "under_odds": _float(row.get("under_odds")),
                "over_odds": _float(row.get("over_odds")),
                "home_spread_odds": _float(row.get("home_spread_odds")),
                "away_spread_odds": _float(row.get("away_spread_odds")),
            })
    games.sort(key=lambda g: (g["gameday"] or "", g["game_id"] or ""))
    return games


def _completed(game: dict) -> bool:
    return game["home_score"] is not None and game["away_score"] is not None


def _american_profit(odds: float | None) -> float:
    """Flat-stake profit for a winning $100 ticket at American odds."""
    if odds is None:
        return STAKE * (100.0 / 110.0)  # conventional -110 when no price is recorded
    if odds > 0:
        return STAKE * (odds / 100.0)
    return STAKE * (100.0 / abs(odds))


# ---------------------------------------------------------------------------
# Studies
# ---------------------------------------------------------------------------

def study_wind_totals(games: list[dict]) -> dict:
    """Outdoor games bucketed by recorded wind, measured against the closing total."""
    buckets = [
        ("wind_0_to_10_mph", 0.0, 10.0),
        ("wind_11_to_14_mph", 11.0, 14.0),
        ("wind_15_to_19_mph", 15.0, 19.0),
        ("wind_20_plus_mph", 20.0, None),
    ]
    findings = {}
    for name, low, high in buckets:
        rows = [g for g in games
                if g["roof"] == "outdoors" and g["wind"] is not None and g["total_line"] is not None
                and _completed(g) and g["wind"] >= low and (high is None or g["wind"] <= high)]
        totals = [g["home_score"] + g["away_score"] for g in rows]
        unders = sum(1 for g in rows if (g["home_score"] + g["away_score"]) < g["total_line"])
        pushes = sum(1 for g in rows if (g["home_score"] + g["away_score"]) == g["total_line"])
        decided = len(rows) - pushes
        priced = [g for g in rows if g["under_odds"] is not None]
        pnl = 0.0
        for game in rows:
            outcome_total = game["home_score"] + game["away_score"]
            if outcome_total == game["total_line"]:
                continue
            if outcome_total < game["total_line"]:
                pnl += _american_profit(game["under_odds"])
            else:
                pnl -= STAKE
        findings[name] = {
            "wind_mph_range": f"{low:g}-{high:g}" if high is not None else f"{low:g}+",
            "sample": len(rows),
            "mean_total_points": round(sum(totals) / len(totals), 2) if totals else None,
            "under_count": unders,
            "push_count": pushes,
            "decided_count": decided,
            "under_rate_pct": _rate(unders, decided),
            "under_rate_ci95_pct": wilson_interval(unders, decided),
            "flat_stake_pnl_usd": round(pnl, 2),
            "games_with_recorded_under_price": len(priced),
        }
    return {
        "id": "STUDY_WIND_TOTALS",
        "title": "Recorded wind speed against closing totals, outdoor games",
        "hypothesis": "Outdoor totals fall as recorded wind rises, so Under tickets win more often above ~15 mph.",
        "method": "Bucket regular-season outdoor games by the snapshot's game-time wind column; compare the final "
                  "combined score against the closing total_line; flat $100 Under at the recorded under price "
                  "(conventional -110 when the snapshot records no price).",
        "snapshot_columns": ["season", "week", "roof", "wind", "total_line", "under_odds", "home_score", "away_score"],
        "seasons": _season_span(games),
        "market": "TOTAL",
        "findings": findings,
        "limitations": "The wind column is a single game-time observation, not a stadium sensor series; the price "
                       "column is missing for most seasons before 2020, so the flat-stake figure is only partly "
                       "observed and the under rate is the primary measurement.",
    }


def study_tnf_rest_travel(games: list[dict]) -> dict:
    """Thursday games, split by the travelling team's rest and travel burden."""
    thursday = [g for g in games if g["weekday"] == "Thursday" and g["spread_line"] is not None and _completed(g)]

    def cover_stats(rows):
        covers = 0
        decided = 0
        pnl = 0.0
        for game in rows:
            margin = game["home_score"] - game["away_score"] + game["spread_line"]
            if margin == 0:
                continue
            decided += 1
            if margin > 0:
                covers += 1
                pnl += _american_profit(game["home_spread_odds"])
            else:
                pnl -= STAKE
        return {
            "sample": len(rows),
            "home_cover_count": covers,
            "push_count": len(rows) - decided,
            "decided_count": decided,
            "home_cover_rate_pct": _rate(covers, decided),
            "home_cover_ci95_pct": wilson_interval(covers, decided),
            "flat_stake_pnl_usd": round(pnl, 2),
        }

    short_rest = [g for g in thursday if (g["away_rest"] is not None and g["away_rest"] <= 4)]
    equal_or_more = [g for g in thursday if not (g["away_rest"] is not None and g["away_rest"] <= 4)]
    return {
        "id": "STUDY_TNF_REST_TRAVEL",
        "title": "Thursday games: home cover rate by travelling team rest",
        "hypothesis": "A Thursday home team beats the spread more often when the visitor had four days or fewer.",
        "method": "Regular-season Thursday games; settle the home side against the closing spread_line; compare "
                  "visitors on <=4 days rest with the rest of the Thursday sample.",
        "snapshot_columns": ["weekday", "away_rest", "home_rest", "spread_line", "home_spread_odds",
                             "home_score", "away_score"],
        "seasons": _season_span(games),
        "market": "SPREAD",
        "findings": {
            "all_thursday_games": cover_stats(thursday),
            "visitor_on_four_days_or_less": cover_stats(short_rest),
            "visitor_rested_five_days_or_more": cover_stats(equal_or_more),
        },
        "limitations": "Travel distance is not in the snapshot, so the cross-country split the research dossier "
                       "claims cannot be re-derived here; the reported split is rest only.",
    }


def study_divisional_high_total_under(games: list[dict]) -> dict:
    """Divisional games carrying a high closing total, measured towards the Under."""
    rows = [g for g in games if g["div_game"] and g["total_line"] is not None and g["total_line"] >= 47.0
            and _completed(g)]
    unders = sum(1 for g in rows if (g["home_score"] + g["away_score"]) < g["total_line"])
    pushes = sum(1 for g in rows if (g["home_score"] + g["away_score"]) == g["total_line"])
    decided = len(rows) - pushes
    pnl = 0.0
    for game in rows:
        outcome_total = game["home_score"] + game["away_score"]
        if outcome_total == game["total_line"]:
            continue
        if outcome_total < game["total_line"]:
            pnl += _american_profit(game["under_odds"])
        else:
            pnl -= STAKE
    return {
        "id": "STUDY_DIVISIONAL_HIGH_TOTAL_UNDER",
        "title": "Divisional games with a total of 47 or higher, Under rate",
        "hypothesis": "The strategy lab's declared rule - divisional games priced at 47.0 or above go Under more "
                      "often than the price implies.",
        "method": "Compare the final combined score with the closing total_line across all regular-season divisional "
                  "games at 47.0 or above, using the whole snapshot rather than only the lab windows.",
        "snapshot_columns": ["div_game", "total_line", "under_odds", "home_score", "away_score"],
        "seasons": _season_span(games),
        "market": "TOTAL",
        "findings": {
            "all_divisional_high_totals": {
                "sample": len(rows),
                "under_count": unders,
                "push_count": pushes,
                "under_rate_pct": _rate(unders, decided),
                "under_rate_ci95_pct": wilson_interval(unders, decided),
                "flat_stake_pnl_usd": round(pnl, 2),
            }
        },
        "limitations": "This is the full-history rate, not the strategy lab's walk-forward holdout; a rate inside "
                       "the confidence interval is not a claim of profitability.",
    }


def study_home_underdog_ats(games: list[dict]) -> dict:
    """Home underdogs against the spread, including the 2002-2011 window a published claim cites."""
    def cover_stats(rows):
        covers = 0
        decided = 0
        pnl = 0.0
        for game in rows:
            margin = game["home_score"] - game["away_score"] + game["spread_line"]
            if margin == 0:
                continue
            decided += 1
            if margin > 0:
                covers += 1
                pnl += _american_profit(game["home_spread_odds"])
            else:
                pnl -= STAKE
        return {
            "sample": len(rows),
            "cover_count": covers,
            "push_count": len(rows) - decided,
            "decided_count": decided,
            "cover_rate_pct": _rate(covers, decided),
            "cover_rate_ci95_pct": wilson_interval(covers, decided),
            "flat_stake_pnl_usd": round(pnl, 2),
        }

    dogs = [g for g in games if g["spread_line"] is not None and g["spread_line"] > 0 and _completed(g)]
    claimed_window = [g for g in dogs if 2002 <= g["season"] <= 2011]
    return {
        "id": "STUDY_HOME_UNDERDOG_ATS",
        "title": "Home underdogs covering the closing spread",
        "hypothesis": "Home underdogs cover the spread at a rate above the price implied by the market.",
        "method": "Home spread conventions in the snapshot are home handicaps, so a positive spread_line is a home "
                  "underdog; settle home_team - away_team + spread_line and report cover rates for the published "
                  "2002-2011 window and for the whole snapshot.",
        "snapshot_columns": ["spread_line", "home_spread_odds", "home_score", "away_score", "season"],
        "seasons": _season_span(games),
        "market": "SPREAD",
        "findings": {
            "published_2002_2011_window": cover_stats(claimed_window),
            "whole_snapshot": cover_stats(dogs),
        },
        "limitations": "Cover rate alone is not a tradable edge: the price paid for the spread is not part of the "
                       "claim, and flat-stake PnL here assumes a conventional -110 where the snapshot has no price.",
    }


def study_dome_totals(games: list[dict]) -> dict:
    """Climate-controlled venues compared with outdoor venues."""
    def totals(rows):
        values = [g["home_score"] + g["away_score"] for g in rows]
        unders = sum(1 for g in rows if (g["home_score"] + g["away_score"]) < g["total_line"])
        pushes = sum(1 for g in rows if (g["home_score"] + g["away_score"]) == g["total_line"])
        decided = len(rows) - pushes
        return {
            "sample": len(rows),
            "under_count": unders,
            "push_count": pushes,
            "decided_count": decided,
            "mean_total_points": round(sum(values) / len(values), 2) if values else None,
            "under_rate_pct": _rate(unders, decided),
            "under_rate_ci95_pct": wilson_interval(unders, decided),
        }

    indoor = [g for g in games if g["roof"] in {"dome", "closed"} and g["total_line"] is not None and _completed(g)]
    outdoor = [g for g in games if g["roof"] == "outdoors" and g["total_line"] is not None and _completed(g)]
    return {
        "id": "STUDY_DOME_TOTALS",
        "title": "Closing totals in climate-controlled venues against outdoor venues",
        "hypothesis": "Climate-controlled venues score closer to the closing total than outdoor venues.",
        "method": "Group regular-season games by the snapshot's roof column and compare realised combined points with "
                  "the closing total_line.",
        "snapshot_columns": ["roof", "temp", "wind", "total_line", "home_score", "away_score"],
        "seasons": _season_span(games),
        "market": "TOTAL",
        "findings": {
            "climate_controlled": totals(indoor),
            "outdoors": totals(outdoor),
        },
        "limitations": "Roof values are recorded as dome/closed/open/outdoors by the provider; a retractable roof "
                       "left open is not distinguishable from one closed at kickoff beyond this column.",
    }


STUDIES = (
    study_wind_totals,
    study_tnf_rest_travel,
    study_divisional_high_total_under,
    study_home_underdog_ats,
    study_dome_totals,
)


def _season_span(games: list[dict]) -> str:
    seasons = [g["season"] for g in games if g["season"]]
    return f"{min(seasons)}-{max(seasons)}" if seasons else "n/a"


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def _headline(study: dict) -> str:
    """One sentence carrying the study's primary measured number."""
    findings = study["findings"]
    if study["id"] == "STUDY_WIND_TOTALS":
        bucket = findings["wind_15_to_19_mph"]
        return (f"{bucket['under_rate_pct']}% Under rate (95% CI {bucket['under_rate_ci95_pct'][0]}-"
                f"{bucket['under_rate_ci95_pct'][1]}%) on {bucket['sample']} outdoor games at 15-19 mph, "
                f"mean total {bucket['mean_total_points']}")
    if study["id"] == "STUDY_TNF_REST_TRAVEL":
        bucket = findings["visitor_on_four_days_or_less"]
        return (f"{bucket['home_cover_rate_pct']}% home cover rate on {bucket['sample']} Thursday games with a "
                f"visitor on four days or fewer")
    if study["id"] == "STUDY_DIVISIONAL_HIGH_TOTAL_UNDER":
        bucket = findings["all_divisional_high_totals"]
        return (f"{bucket['under_rate_pct']}% Under rate across {bucket['sample']} divisional games at 47.0 or "
                f"above, flat-stake {bucket['flat_stake_pnl_usd']:+,.2f} USD")
    if study["id"] == "STUDY_HOME_UNDERDOG_ATS":
        published = findings["published_2002_2011_window"]
        whole = findings["whole_snapshot"]
        return (f"{published['cover_rate_pct']}% cover rate in 2002-2011 ({published['sample']} games) and "
                f"{whole['cover_rate_pct']}% across the whole snapshot ({whole['sample']} games)")
    if study["id"] == "STUDY_DOME_TOTALS":
        indoor = findings["climate_controlled"]
        outdoor = findings["outdoors"]
        return (f"mean total {indoor['mean_total_points']} indoors against {outdoor['mean_total_points']} outdoors; "
                f"Under rate {indoor['under_rate_pct']}% against {outdoor['under_rate_pct']}%")
    return "no headline"


def _cross_checks(studies: dict[str, dict], data_dir: Path, declared_experiments=None) -> list[dict]:
    """Compare hand-declared dossier numbers with the re-derived studies.

    ``declared_experiments`` lets a caller pass the dossier it has just built
    (as the backtest engine does) instead of re-reading the file on disk, so the
    comparison is never one run behind.
    """
    experiments = declared_experiments
    if experiments is None:
        try:
            experiments = json.loads((data_dir / "research_experiments.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
    by_id = {e.get("experiment_id"): e for e in experiments}
    checks = []

    def compare(experiment_id, path, declared, computed, label):
        checks.append({
            "experiment_id": experiment_id,
            "study_id": RE_DERIVED_BY.get(experiment_id),
            "metric": label,
            "declared_in_dossier": declared,
            "re_derived_from_snapshot": computed,
            "difference_pct_points": (round(computed - declared, 2)
                                      if isinstance(computed, (int, float)) and isinstance(declared, (int, float))
                                      else None),
            "agrees": (abs(computed - declared) <= CROSS_CHECK_TOLERANCE_PCT
                       if isinstance(computed, (int, float)) and isinstance(declared, (int, float)) else False),
            "resolution": "difference retained; neither value is overwritten",
        })

    wind = by_id.get("EXP_001_WEATHER_WIND_THRESHOLD")
    study = studies.get("STUDY_WIND_TOTALS")
    if wind and study:
        declared = (wind.get("findings") or {}).get("wind_15_to_19_mph", {}).get("under_rate_pct")
        computed = study["findings"]["wind_15_to_19_mph"]["under_rate_pct"]
        compare("EXP_001_WEATHER_WIND_THRESHOLD", None, declared, computed,
                "Under rate, 15-19 mph outdoor wind")

    tnf = by_id.get("EXP_004_TNF_SHORT_REST_TRAVEL")
    study = studies.get("STUDY_TNF_REST_TRAVEL")
    if tnf and study:
        declared = (tnf.get("findings") or {}).get("tnf_home_vs_road_short_rest", {}).get("cover_rate_pct")
        computed = study["findings"]["visitor_on_four_days_or_less"]["home_cover_rate_pct"]
        compare("EXP_004_TNF_SHORT_REST_TRAVEL", None, declared, computed,
                "Home cover rate, Thursday with visitor on <=4 days rest")
    return checks


def build_report(data_dir: str | Path = ROOT / "data", declared_experiments=None) -> dict:
    """Compute every supported study and classify the unsupported dossier claims."""
    data_dir = Path(data_dir)
    games = load_games(data_dir / "source")
    studies = []
    study_index = {}
    for builder in STUDIES:
        study = builder(games)
        study["headline"] = _headline(study)
        study["strategy_id"] = (STUDY_STRATEGIES.get(study["id"]) or [None])[0]
        study["strategy_ids"] = STUDY_STRATEGIES.get(study["id"], [])
        study["evidence_class"] = "DERIVED_DATA"
        studies.append(study)
        study_index[study["id"]] = study

    cross_checks = _cross_checks(study_index, data_dir, declared_experiments)
    unsupported = []
    experiments = declared_experiments
    if experiments is None:
        try:
            experiments = json.loads((data_dir / "research_experiments.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            experiments = []
    for experiment in experiments:
        experiment_id = experiment.get("experiment_id")
        if experiment_id in UNSUPPORTED_EXPERIMENTS:
            unsupported.append({
                "experiment_id": experiment_id,
                "title": experiment.get("title"),
                "evidence_class": "DECLARED_ASSUMPTION",
                "reason": UNSUPPORTED_EXPERIMENTS[experiment_id],
                "snapshot_supported": False,
            })
        elif experiment_id in RE_DERIVED_BY:
            unsupported.append({
                "experiment_id": experiment_id,
                "title": experiment.get("title"),
                "evidence_class": "DERIVED_DATA",
                "reason": f"re-derived by {RE_DERIVED_BY[experiment_id]} from the checked-in snapshot",
                "snapshot_supported": True,
            })

    return {
        "generated_by": "engine/empirical_studies.py::build_report",
        "classification": "DERIVED_DATA",
        "source": {
            "path": "data/source/games.csv",
            "games_loaded": len(games),
            "regular_season_games": len(games),
            "seasons": _season_span(games),
        },
        "policy": {
            "stake": f"${STAKE:,.0f} flat per qualifying observation",
            "interval": "Wilson score interval, 95%, two-sided",
            "cross_check_tolerance_pct_points": CROSS_CHECK_TOLERANCE_PCT,
            "warning": "A cover rate or Under rate inside its confidence interval is not evidence of a durable edge; "
                       "these studies measure the snapshot, they do not forecast it.",
        },
        "studies": studies,
        "study_count": len(studies),
        "snapshot_supported_hypotheses": [s["id"] for s in studies],
        "declared_assumptions": unsupported,
        "cross_checks": cross_checks,
        "cross_check_disagreements": [c for c in cross_checks if not c.get("agrees")],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--out", default=None)
    parser.add_argument("--check", action="store_true",
                        help="fail if the checked-in report does not re-derive from the snapshot")
    args = parser.parse_args(argv)

    report = build_report(args.data_dir)
    out_path = Path(args.out) if args.out else Path(args.data_dir) / "empirical_studies.json"
    rendered = json.dumps(report, indent=2) + "\n"

    if args.check:
        try:
            current = out_path.read_text(encoding="utf-8")
        except OSError:
            print(f"{out_path} is missing; run python3 -m engine.empirical_studies")
            return 1
        if current != rendered:
            print(f"{out_path} is stale; run python3 -m engine.empirical_studies")
            return 1
        print(f"{out_path} re-derives from the snapshot ({report['study_count']} studies, "
              f"{len(report['cross_check_disagreements'])} cross-check disagreement(s))")
        return 0

    out_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {out_path}: {report['study_count']} studies, "
          f"{len(report['declared_assumptions'])} classified dossier claims, "
          f"{len(report['cross_check_disagreements'])} cross-check disagreement(s)")
    for disagreement in report["cross_check_disagreements"]:
        print(f"  DISAGREES: {disagreement['metric']}: dossier {disagreement['declared_in_dossier']} "
              f"vs snapshot {disagreement['re_derived_from_snapshot']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
