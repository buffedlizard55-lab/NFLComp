"""
NFLComp Quantitative Engine Unit and Integration Tests - Expanded Edition
Tests:
- Data Loader integrity
- Elo and Poisson models
- New models: OL, Defensive, GameScript, Travel, Logistic, Bayesian, Monte Carlo, GB, Ensemble, Live WP
- Strategy signal evaluation across all categories
- PnL calculations including new markets
- Bet ledger consistency
- Audit verifier zero-hallucination checks
- MasterSite research coverage
"""

import unittest
import os
import re
import sys
import json
import random
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.data_loader import NFLDataLoader
from engine.ledger import append_bet, chain_hash, verify_chain, verify_ledger
from engine.publication import (
    CLAIM_PATTERNS,
    expected_site_claims,
    published_facts,
    render_badges,
    render_status_block,
    site_claims,
)
from engine.research_discovery import discover_candidates, compare_versions
from engine.strategy_lab import build_report
from engine.settlement import settle_spread, settle_total
from engine.models import (
    DynamicNFLEloEngine,
    BivariatePoissonScoringModel,
    OffensiveLineModel,
    DefensivePressureModel,
    GameScriptModel,
    TravelFatigueModel,
    LogisticRegressionModel,
    BayesianHierarchicalModel,
    MonteCarloModel,
    GradientBoostingModel,
    RandomForestModel,
    EnsembleModel,
    LiveWinProbabilityModel,
    american_to_decimal,
    american_to_implied_prob,
    calculate_pnl,
    calculate_clv,
    KalshiExecutionSimulator,
    evaluate_injury_impact
)
from engine.strategy_registry import ALL_STRATEGY_DEFINITIONS, get_strategy_instances
from engine.audit_verifier import NFLAuditVerifier
from engine import empirical_studies, narrative, risk_analytics
from engine.empirical_studies import (
    build_report as build_study_report,
    load_games as load_study_games,
    wilson_interval,
)
from engine.risk_analytics import (
    bootstrap_roi,
    brier_score,
    calibration_bins,
    kelly_fraction,
    kelly_full_fraction,
    log_loss,
    sharpe_ratio,
    sortino_ratio,
)

class TestNFLCompExpanded(unittest.TestCase):
    def setUp(self):
        random.seed(42)
        self.loader = NFLDataLoader("data/source")
        self.games = self.loader.load_all()

    def test_data_loader_games(self):
        self.assertGreater(len(self.games), 7000)
        completed = [g for g in self.games if g["completed"]]
        self.assertGreater(len(completed), 7200)
        g2026 = [g for g in self.games if g["season"] == 2026]
        self.assertEqual(len(g2026), 272)
        w1 = [g for g in g2026 if g["week"] == 1]
        self.assertEqual(len(w1), 16)
        self.assertTrue(all(g["completed"] for g in w1))

    def test_elo_model(self):
        elo = DynamicNFLEloEngine()
        pred = elo.predict_game("KC", "DEN")
        self.assertIn("p_home", pred)
        self.assertIn("p_away", pred)
        self.assertAlmostEqual(pred["p_home"] + pred["p_away"], 1.0, places=4)
        self.assertGreater(pred["p_home"], 0.50)

    def test_poisson_model(self):
        poisson = BivariatePoissonScoringModel()
        lh, la = poisson.calculate_lambdas("KC", "LV")
        self.assertGreater(lh, 0)
        self.assertGreater(la, 0)
        grid = poisson.simulate_probabilities(lh, la)
        self.assertIn("spread_dist", grid)
        self.assertIn("total_dist", grid)
        p_cover = poisson.eval_market_prob(grid, "SPREAD", -3.5, "home")
        self.assertGreater(p_cover, 0.0)
        self.assertLess(p_cover, 1.0)

    def test_offensive_line_model(self):
        ol_model = OffensiveLineModel()
        context = {"rolling_metrics": {}, "injuries_by_team": {}}
        adv, breakdown = ol_model.evaluate_ol_advantage("KC", "DEN", {}, context)
        self.assertIsInstance(adv, float)
        self.assertIn("home_ol_lost", breakdown)

    def test_defensive_pressure_model(self):
        def_model = DefensivePressureModel()
        context = {"rolling_metrics": {}}
        adv, breakdown = def_model.evaluate_defense_advantage("KC", "DEN", context)
        self.assertIsInstance(adv, float)
        self.assertIn("pressure_adv", breakdown)

    def test_game_script_model(self):
        gs_model = GameScriptModel()
        context = {"rolling_metrics": {}}
        script = gs_model.project_game_script("KC", "DEN", -3.5, 45.5, context)
        self.assertIn("projected_plays", script)
        self.assertIn("home_pass_rate", script)
        self.assertGreater(script["projected_plays"], 100)

    def test_travel_fatigue_model(self):
        travel_model = TravelFatigueModel()
        dist, tz = travel_model.calculate_travel("SEA", "MIA", is_home=False)
        self.assertGreater(dist, 2000)
        self.assertGreaterEqual(tz, 2)
        penalty = travel_model.fatigue_penalty(dist, tz, 2, False)
        self.assertGreater(penalty, 0)

    def test_logistic_regression_model(self):
        log_model = LogisticRegressionModel()
        game = {"home_team": "KC", "away_team": "DEN", "spread_line": -3.5, "rest_diff": 1, "wind": 10, "is_dome": False}
        context = {
            "elo_engine": DynamicNFLEloEngine(),
            "injuries_by_team": {},
            "rolling_metrics": {}
        }
        features = log_model.features_from_game(game, context)
        self.assertIn("elo_diff", features)
        prob = log_model.predict_proba(features)
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)

    def test_bayesian_model(self):
        bayes = BayesianHierarchicalModel()
        bayes.update("KC", 0.15)
        bayes.update("DEN", -0.05)
        prob, diff = bayes.predict("KC", "DEN")
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)

    def test_monte_carlo_model(self):
        mc = MonteCarloModel(n_sim=500)
        res = mc.simulate_game(24.0, 20.0, -3.5, 44.0)
        self.assertIn("p_home_cover", res)
        self.assertIn("p_over", res)
        self.assertGreaterEqual(res["p_home_cover"], 0.0)

    def test_gradient_boosting_model(self):
        gb = GradientBoostingModel()
        features = {"wind": 16.0, "temp": 30.0, "pace": 0.8, "elo_total": 45.0, "injury": 2.5}
        proj = gb.predict(features)
        self.assertGreater(proj, 30)
        self.assertLess(proj, 55)

    def test_ensemble_model(self):
        ensemble = EnsembleModel()
        game = {"home_team": "KC", "away_team": "DEN", "spread_line": -3.5, "total_line": 45.0}
        context = {
            "elo_engine": DynamicNFLEloEngine(),
            "poisson_model": BivariatePoissonScoringModel(),
            "injuries_by_team": {},
            "rolling_metrics": {}
        }
        res = ensemble.predict_game(game, context)
        self.assertIn("ensemble_prob", res)
        self.assertIn("components", res)

    def test_live_wp_model(self):
        live_model = LiveWinProbabilityModel()
        wp = live_model.calculate_live_wp(14, 21, 4, 300, 2, 5, 65, "away", 2, 1)
        self.assertGreaterEqual(wp, 0.0)
        self.assertLessEqual(wp, 1.0)
        edge = live_model.evaluate_live_edge(wp, 30.0, "YES")
        self.assertIsInstance(edge, float)

    def test_odds_conversion(self):
        self.assertAlmostEqual(american_to_decimal(-110), 1.90909, places=4)
        self.assertAlmostEqual(american_to_decimal(150), 2.50, places=4)
        self.assertAlmostEqual(american_to_implied_prob(-110), 0.5238, places=3)
        self.assertAlmostEqual(american_to_implied_prob(150), 0.40, places=3)

    def test_pnl_math(self):
        pnl_win = calculate_pnl(100.0, -110.0, 1.0)
        self.assertAlmostEqual(pnl_win, 90.91, places=2)
        pnl_loss = calculate_pnl(100.0, -110.0, 0.0)
        self.assertEqual(pnl_loss, -100.0)
        pnl_push = calculate_pnl(100.0, -110.0, 0.5)
        self.assertEqual(pnl_push, 0.0)
        # Test alt spread positive odds
        pnl_alt_win = calculate_pnl(100.0, 150.0, 1.0)
        self.assertAlmostEqual(pnl_alt_win, 150.0, places=1)

    def test_kalshi_simulation(self):
        sim = KalshiExecutionSimulator()
        order = sim.simulate_order(0.60, "YES", 100)
        self.assertEqual(order["filled_contracts"], 100)
        self.assertGreater(order["fill_price_cents"], 55.0)
        settle_win = sim.settle_contract(order, 1)
        self.assertTrue(settle_win["is_win"])
        self.assertGreater(settle_win["net_pnl"], 0.0)

    def test_strategy_instances_expanded(self):
        strats = get_strategy_instances()
        self.assertGreaterEqual(len(strats), 45, f"Expected >=45 strategies, got {len(strats)}")
        categories = set(s.category for s in strats)
        self.assertGreaterEqual(len(categories), 10, f"Expected >=10 categories, got {categories}")
        # Check required categories
        required = ["Offensive Line & Protection", "Defensive Matchups & Scheme", "Player Prop Strategies", "Game Script & Situational", "Live & In-Game Strategies"]
        for rc in required:
            self.assertIn(rc, categories, f"Missing required category {rc}")
        for s in strats:
            self.assertIsNotNone(s.id)
            self.assertIsNotNone(s.username)
            self.assertIsNotNone(s.hypothesis)

    def test_injury_evaluation(self):
        sample_injuries = [
            {"player": "Starting QB", "position": "QB", "game_status": "OUT", "practice_status": "DNP"},
            {"player": "Left Tackle", "position": "LT", "game_status": "QUESTIONABLE", "practice_status": "DNP"},
            {"player": "Cornerback", "position": "CB1", "game_status": "ACTIVE", "practice_status": "FULL"}
        ]
        pts_lost, breakdown = evaluate_injury_impact(sample_injuries)
        self.assertGreater(pts_lost, 4.0)
        self.assertGreaterEqual(len(breakdown), 2)

    def test_discovery_flags_unavailable_data_without_claiming_edge(self):
        candidates = discover_candidates([{"wind": 18, "temp": 42, "roof": "outdoors", "total_line": 44}], source_id="snapshot-1")
        weather = next(c for c in candidates if c["candidate_id"] == "WEATHER_TOTAL")
        self.assertEqual(weather["status"], "READY_FOR_TEST")
        self.assertIsNone(weather["performance_claim"])
        rest = next(c for c in candidates if c["candidate_id"] == "REST_TOTAL_INTERACTION")
        self.assertEqual(rest["status"], "BLOCKED_MISSING_DATA")
        comparison = compare_versions(weather, rest)
        self.assertEqual(comparison["comparison_status"], "REQUIRES_OUT_OF_SAMPLE_TEST")
        self.assertIsNone(comparison["improvement_claim"])

    def test_market_settlement_uses_home_handicap_convention(self):
        # Home -3.5 wins by 7 and covers; home -3.5 wins by 3 and does not.
        self.assertEqual(settle_spread(7, -3.5, "home"), 1.0)
        self.assertEqual(settle_spread(3, -3.5, "home"), 0.0)
        self.assertEqual(settle_spread(3, -3.0, "home"), 0.5)
        self.assertEqual(settle_spread(3, -3.5, "away"), 1.0)
        self.assertEqual(settle_total(48, 47.0, "over"), 1.0)
        self.assertEqual(settle_total(47, 47.0, "under"), 0.5)

    def test_strategy_lab_uses_fixed_chronological_windows(self):
        report = build_report("data/source")
        self.assertEqual(report["policy"]["untouched_holdout_window"], "2023-2025")
        self.assertEqual(len(report["candidates"]), 2)
        by_id = {candidate["strategy_id"]: candidate for candidate in report["candidates"]}
        rest = by_id["STRAT_REST_TNF_005_v3"]
        division = by_id["STRAT_DIV_TOTAL_040_v1"]
        self.assertEqual(rest["windows"]["holdout"]["bets"], 81)
        self.assertEqual(division["windows"]["holdout"]["bets"], 74)
        # After correcting the spread sign convention from away-spread to home-spread,
        # the rest differential strategy shows a negative holdout ROI, correctly
        # flagging as HOLDOUT_FAILED rather than the previously inflated PASSED.
        self.assertEqual(rest["status"], "HOLDOUT_FAILED")
        self.assertEqual(division["status"], "HOLDOUT_PASSED")
        self.assertIsNone(rest["performance_claim"])
        self.assertIsNone(division["performance_claim"])

    def test_new_strategy_lab_rules_emit_only_observed_market_signals(self):
        strategies = {strategy.id: strategy for strategy in get_strategy_instances()}
        rest = strategies["STRAT_REST_TNF_005_v3"]
        division = strategies["STRAT_DIV_TOTAL_040_v1"]
        rest_game = {
            "game_id": "TEST_REST", "home_team": "SF", "away_team": "SEA",
            "home_rest": 10, "away_rest": 6, "rest_diff": 4,
            "spread_line": -2.5, "home_spread_odds": -110.0, "away_spread_odds": -110.0,
            "home_spread_odds_recorded": True, "away_spread_odds_recorded": True,
        }
        division_game = {
            "game_id": "TEST_DIV", "div_game": True, "total_line": 47.0,
            "under_odds": -110.0, "under_odds_recorded": True,
        }
        self.assertEqual(rest.evaluate_game(rest_game, {})[0]["selection"], "SF -2.5")
        self.assertEqual(division.evaluate_game(division_game, {})[0]["selection"], "Under 47.0")
        rest_game["rest_diff"] = 3
        self.assertEqual(rest.evaluate_game(rest_game, {}), [])
        division_game["div_game"] = False
        self.assertEqual(division.evaluate_game(division_game, {}), [])
        rest_game["rest_diff"] = 4
        rest_game["home_spread_odds_recorded"] = False
        self.assertEqual(rest.evaluate_game(rest_game, {}), [])

    def test_hash_chained_ledger_detects_tampering(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bets.jsonl")
            append_bet(path, {"bet_id": "B-1", "stake": 10, "result": "WIN"})
            append_bet(path, {"bet_id": "B-2", "stake": 10, "result": "LOSS"})
            valid, errors = verify_ledger(path)
            self.assertTrue(valid, errors)
            with open(path, "r+", encoding="utf-8") as fh:
                text = fh.read().replace('"stake": 10', '"stake": 99', 1)
                fh.seek(0); fh.write(text); fh.truncate()
            valid, errors = verify_ledger(path)
            self.assertFalse(valid)
            self.assertTrue(any("hash mismatch" in error for error in errors))

    def test_audit_verifier_expanded(self):
        """The published data must satisfy every audit check, not merely most."""
        verifier = NFLAuditVerifier("data")
        audit_res = verifier.run_full_audit()
        failed = [c["name"] for c in verifier.audit_checks if not c["passed"]]
        self.assertEqual(failed, [], f"audit failures: {failed}")
        self.assertGreaterEqual(audit_res["total_checks"], 20)
        self.assertEqual(audit_res["failed_checks"], 0)


class TestEmpiricalStudies(unittest.TestCase):
    """Studies must be real measurements, and claims must be labelled."""

    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.data = self.root / "data"
        self.report = json.loads((self.data / "empirical_studies.json").read_text(encoding="utf-8"))

    def test_wilson_interval_brackets_the_point_estimate(self):
        low, high = wilson_interval(56, 100)
        self.assertLess(low, 56.0)
        self.assertGreater(high, 56.0)
        self.assertLess(low, high)
        self.assertIsNone(wilson_interval(0, 0))

    def test_sample_spread_is_read_as_a_home_handicap(self):
        """A positive raw spread_line means the home team is favoured.

        Reading the column with the opposite sign inverts every ATS result, so
        the study loader negates it and home covers must land near 50%.
        """
        games = load_study_games(self.data / "source")
        rows = [g for g in games if g["spread_line"] is not None and g["home_score"] is not None]
        decided = [g for g in rows if (g["home_score"] - g["away_score"] + g["spread_line"]) != 0]
        covers = sum(1 for g in decided if (g["home_score"] - g["away_score"] + g["spread_line"]) > 0)
        rate = 100.0 * covers / len(decided)
        self.assertGreater(rate, 45.0, "home cover rate below 45% suggests an inverted sign convention")
        self.assertLess(rate, 55.0, "home cover rate above 55% suggests an inverted sign convention")
        favourites = [g for g in rows if g["spread_line"] < 0]
        wins = sum(1 for g in favourites if g["home_score"] > g["away_score"])
        self.assertGreater(wins / len(favourites), 0.5,
                           "a negative home handicap must be the favoured side")

    def test_every_study_reports_a_sample_and_a_measurement(self):
        self.assertGreaterEqual(self.report["study_count"], 4)
        for study in self.report["studies"]:
            self.assertEqual(study["evidence_class"], "DERIVED_DATA")
            self.assertTrue(study.get("snapshot_columns"), study["id"] + " must name its columns")
            self.assertIn("headline", study)
            for name, finding in study["findings"].items():
                self.assertGreater(finding["sample"], 0, study["id"] + "." + name + " has no sample")
                self.assertTrue(
                    any(key.endswith("_pct") or key.startswith("mean_") for key in finding),
                    study["id"] + "." + name + " reports no measurement")

    def test_declared_dossier_claims_are_not_presented_as_measurements(self):
        """Unsupported claims must be labelled, and disagreements preserved."""
        dossier = json.loads((self.data / "research_experiments.json").read_text(encoding="utf-8"))
        by_id = {e["experiment_id"]: e for e in dossier}
        for entry in self.report["declared_assumptions"]:
            self.assertEqual(entry["evidence_class"], by_id[entry["experiment_id"]]["evidence_class"])
        for check in self.report["cross_checks"]:
            experiment = by_id[check["experiment_id"]]
            self.assertIn("snapshot_cross_check", experiment)
            recorded = experiment["snapshot_cross_check"][0]
            self.assertEqual(recorded["declared_in_dossier"], check["declared_in_dossier"])
            self.assertEqual(recorded["re_derived_from_snapshot"], check["re_derived_from_snapshot"])
            if not check["agrees"]:
                self.assertEqual(experiment["claim_status"], "DISPUTED_BY_SNAPSHOT")
                self.assertIn("retained", check["resolution"])

    def test_report_re_derives_from_the_snapshot(self):
        """Recomputing from games.csv must reproduce the checked-in report.

        The report is written as JSON, so tuples become lists on the round trip;
        normalise before comparing.
        """
        rebuilt = json.loads(json.dumps(build_study_report(str(self.data))))
        self.assertEqual(rebuilt["studies"], self.report["studies"])
        self.assertEqual(rebuilt["cross_checks"], self.report["cross_checks"])
        self.assertEqual(rebuilt["declared_assumptions"], self.report["declared_assumptions"])
        # The report must be reproducible, so it may not carry a wall-clock stamp.
        self.assertNotIn("generated_at", self.report)
        self.assertEqual(self.report["generated_by"], "engine/empirical_studies.py::build_report")


    def test_reported_rates_re_derive_from_their_own_counts(self):
        """A study percentage must equal its own successes over decided games.

        This is what keeps a bucket from quoting a rate while its counts describe
        a different sample: pushes are excluded from the denominator, exactly as
        the settlement rule excludes them.
        """
        checked = 0
        for study in self.report["studies"]:
            for name, finding in study["findings"].items():
                decided = finding.get("decided_count", finding["sample"] - finding.get("push_count", 0))
                if "push_count" in finding:
                    self.assertEqual(finding["sample"] - finding["push_count"], decided,
                                     study["id"] + "." + name + " reports inconsistent push counts")
                for key in ("under_rate_pct", "home_cover_rate_pct", "cover_rate_pct"):
                    if key not in finding:
                        continue
                    count_key = key.replace("_rate_pct", "_count")
                    success_key = {"under_rate_pct": "under_count",
                                   "home_cover_rate_pct": "home_cover_count",
                                   "cover_rate_pct": "cover_count"}[key]
                    if success_key not in finding:
                        continue
                    self.assertGreater(decided, 0, study["id"] + "." + name + " has no decided games")
                    expected = round(100.0 * finding[success_key] / decided, 2)
                    self.assertAlmostEqual(finding[key], expected, places=1,
                                           msg=study["id"] + "." + name + " quotes a rate its counts do not support")
                    checked += 1
        self.assertGreater(checked, 0, "no rate was checked; the study format changed")

    def test_wilson_interval_matches_a_hand_computation(self):
        low, high = wilson_interval(56, 100)
        self.assertAlmostEqual(low, 46.24, places=1)
        self.assertAlmostEqual(high, 65.34, places=1)
        # A thin sample must widen the interval, never narrow it.
        thin_low, thin_high = wilson_interval(6, 10)
        self.assertLess(thin_low, low)
        self.assertGreater(thin_high, high)

    def test_flat_stake_result_is_absent_when_the_snapshot_has_no_price(self):
        """No recorded price means no PnL line, rather than a defaulted one."""
        dome = next(s for s in self.report["studies"] if s["id"] == "STUDY_DOME_TOTALS")
        for finding in dome["findings"].values():
            self.assertNotIn("flat_stake_pnl_usd", finding)
            self.assertIn("mean_total_points", finding)
        wind = next(s for s in self.report["studies"] if s["id"] == "STUDY_WIND_TOTALS")
        for finding in wind["findings"].values():
            self.assertLessEqual(finding["games_with_recorded_under_price"], finding["sample"])

    def test_disputed_claim_is_recorded_as_an_irregularity(self):
        register = json.loads((self.data / "irregularities.json").read_text(encoding="utf-8"))
        disputed = [c for c in self.report["cross_checks"] if not c["agrees"]]
        self.assertTrue(disputed, "the snapshot's own disagreement must stay visible")
        for check in disputed:
            matches = [r for r in register if check["experiment_id"] in r["id"]]
            self.assertTrue(matches, check["experiment_id"] + " must be logged in the irregularity register")
            self.assertEqual(matches[0]["status"], "LOGGED_AND_RESOLVED")


class TestRiskAnalytics(unittest.TestCase):
    """Risk statistics must be correct arithmetic, not plausible-looking text."""

    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.data = self.root / "data"
        self.report = json.loads((self.data / "risk_analytics.json").read_text(encoding="utf-8"))

    def test_sharpe_and_sortino_penalise_downside_only(self):
        steady = [1.0, 1.0, 1.0, 1.0]
        volatile = [2.0, -1.0, 2.0, -1.0]
        self.assertIsNone(sharpe_ratio(steady, 1.0), "zero variance has no Sharpe")
        self.assertGreater(sharpe_ratio(volatile, 1.0), 0)
        self.assertGreater(sortino_ratio(volatile, 1.0), sharpe_ratio(volatile, 1.0))
        self.assertIsNone(sortino_ratio([1.0, 2.0], 1.0), "no downside means no Sortino denominator")

    def test_brier_log_loss_and_calibration_error(self):
        perfect = [(1.0, 1.0), (0.0, 0.0)]
        uninformative = [(0.5, 1.0), (0.5, 0.0)]
        self.assertEqual(brier_score(perfect), 0.0)
        self.assertGreater(brier_score(uninformative), brier_score(perfect))
        self.assertLess(log_loss(perfect), log_loss(uninformative))
        table, ece = calibration_bins([(0.55, 1.0)] * 10 + [(0.55, 0.0)] * 10)
        buckets = [row for row in table if row["bets"]]
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0]["bets"], 20)
        self.assertAlmostEqual(buckets[0]["mean_model_prob"], 0.55, places=4)
        self.assertAlmostEqual(buckets[0]["observed_win_rate"], 0.5, places=4)
        self.assertAlmostEqual(ece, 5.0, places=1, msg="50% observed against a 55% forecast is a 5 point gap")

    def test_kelly_is_negative_when_the_price_beats_the_forecast(self):
        self.assertLess(kelly_full_fraction(0.50, 1.9091), 0.0)
        self.assertIsNone(kelly_fraction(0.50, 1.0), "decimal odds of 1.0 cannot be priced")
        self.assertAlmostEqual(kelly_fraction(0.60, 2.0), 0.25 * 0.20, places=6)

    def test_bootstrap_is_seeded_and_brackets_the_observed_mean(self):
        returns = [0.9, -1.0] * 200
        first = bootstrap_roi(returns, 100.0)
        second = bootstrap_roi(returns, 100.0)
        self.assertEqual(first, second, "a seeded bootstrap must reproduce exactly")
        self.assertLessEqual(first["roi_pct_ci95"][0], first["roi_pct_ci95"][1])
        observed = 100.0 * sum(returns) / len(returns)
        self.assertLessEqual(first["roi_pct_ci95"][0], observed)
        self.assertGreaterEqual(first["roi_pct_ci95"][1], observed)
        self.assertLessEqual(first["roi_pct_ci95"][0], first["roi_pct_median"])
        self.assertLessEqual(first["roi_pct_median"], first["roi_pct_ci95"][1])
        # A losing series can still resample positive sometimes, but it must not
        # look like a winning system most of the time.
        self.assertLess(first["probability_roi_positive_pct"], 50.0)
        winners = bootstrap_roi([1.0] * 400, 100.0)
        self.assertEqual(winners["probability_roi_positive_pct"], 100.0)
        self.assertEqual(winners["roi_pct_ci95"], [100.0, 100.0])

    def test_published_risk_report_reconciles_with_the_ledger(self):
        ledger = json.loads((self.data / "bets_ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(self.report["source"]["published_records"], len(ledger))
        recalibrated = risk_analytics.calibration_section(ledger)
        self.assertEqual(self.report["calibration"]["brier_score"], recalibrated["brier_score"])
        self.assertEqual(self.report["calibration"]["expected_calibration_error_pct_points"],
                         recalibrated["expected_calibration_error_pct_points"])
        by_persona = {}
        for bet in ledger:
            by_persona[bet["strategy_id"]] = by_persona.get(bet["strategy_id"], 0) + 1
        for record in self.report["personas"]:
            self.assertEqual(record["published_bets"], by_persona.get(record["strategy_id"], 0))
            if record["insufficient_sample"]:
                self.assertLess(record["settled_bets"], self.report["policy"]["minimum_settled_bets"])

    def test_bootstrap_interval_is_reported_against_the_observed_roi(self):
        for record in self.report["personas"]:
            bootstrap = record.get("bootstrap")
            if not bootstrap:
                continue
            self.assertEqual(bootstrap["seed"], self.report["policy"]["bootstrap_seed"])
            self.assertLessEqual(bootstrap["roi_pct_ci95"][0], record["observed_roi_pct"])
            self.assertGreaterEqual(bootstrap["roi_pct_ci95"][1], record["observed_roi_pct"])


class TestProseClaimsAreBound(unittest.TestCase):
    """Hand-typed quantities must fail the lint instead of shipping."""

    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.data = self.root / "data"
        self.facts = published_facts(str(self.data))

    def test_lint_catches_a_stale_persona_count(self):
        violations = narrative.prose_claim_violations(
            "- **Strategy Universe:** **60 autonomous betting personas** across 14 disciplines.",
            self.facts, str(self.data), source="synthetic.md")
        self.assertTrue(any("personas" in v for v in violations), violations)
        self.assertTrue(any("disciplines" in v for v in violations), violations)

    def test_lint_accepts_a_correct_claim_and_ignores_generated_blocks(self):
        personas = self.facts["strategies"]
        clean = "The platform maintains %s strategy personas today." % personas
        self.assertEqual(narrative.prose_claim_violations(clean, self.facts, str(self.data)), [])
        generated = "%s\n- 60 autonomous betting personas\n%s" % (
            narrative.EXEC_SUMMARY_START, narrative.EXEC_SUMMARY_END)
        self.assertEqual(narrative.prose_claim_violations(generated, self.facts, str(self.data)), [])

    def test_published_documents_pass_the_lint(self):
        documents = [self.root / "README.md"] + sorted((self.root / "docs").glob("*.md"))
        violations = []
        for document in documents:
            violations += narrative.prose_claim_violations(
                document.read_text(encoding="utf-8"), self.facts, str(self.data), source=document.name)
        self.assertEqual(violations, [], "hand-typed claims disagree with the data files")

    def test_generated_blocks_match_their_renderers(self):
        """Each generated block lives in the document that owns it, and is current."""
        placement = {
            "executive_summary": "README.md",
            "roster": "README.md",
            "findings": "README.md",
            "sources": "README.md",
            "strategy_lab": "README.md",
            "irregularities": "docs/IRREGULARITIES.md",
        }
        blocks = narrative.render_blocks(self.facts, str(self.data))
        for name, (marker, block) in blocks.items():
            document = self.root / placement[name]
            text = document.read_text(encoding="utf-8")
            self.assertIn(marker, text, name + " block missing from " + placement[name])
            self.assertIn(block.strip(), text, name + " block is stale in " + placement[name])
        self.assertEqual(set(placement), set(blocks),
                         "every generated block must be placed in a document")

    def test_roster_block_covers_every_leaderboard_persona(self):
        leaderboard = json.loads((self.data / "leaderboard.json").read_text(encoding="utf-8"))
        block = narrative.render_roster_table(str(self.data))
        for row in leaderboard:
            self.assertIn("`%s`" % row["id"], block)
        silent = [row for row in leaderboard if not (row.get("total_bets") or 0)]
        if silent:
            self.assertIn("| n/a |", block)


    def test_roster_never_publishes_a_rate_without_settled_bets(self):
        block = narrative.render_roster_table(str(self.data))
        leaderboard = json.loads((self.data / "leaderboard.json").read_text(encoding="utf-8"))
        open_rows = [row for row in leaderboard if not (row.get("total_bets") or 0)]
        self.assertTrue(open_rows, "the roster is expected to carry personas without settled bets")
        for row in open_rows:
            line = next(l for l in block.splitlines() if "`%s`" % row["id"] in l)
            self.assertIn("n/a (open)", line)
            self.assertIn("| n/a |", line)

    def test_executive_summary_quotes_the_data_files(self):
        block = narrative.render_executive_summary(self.facts, str(self.data))
        for value in (f"{self.facts['games_tracked']:,} games",
                      f"{self.facts['published_bets']:,} hash-chained wagers",
                      f"{self.facts['strategies']} personas",
                      f"{self.facts['audit_checks_passed']}/{self.facts['audit_checks_total']}"):
            self.assertIn(value, block)
        for stale in ("60 autonomous betting personas", "134,255", "@AltSpread_Value_v2"):
            self.assertNotIn(stale, block)

    def test_irregularity_block_lists_every_logged_entry(self):
        register = json.loads((self.data / "irregularities.json").read_text(encoding="utf-8"))
        block = narrative.render_irregularity_table(str(self.data))
        self.assertEqual(block.count("| `IRR-"), len(register))
        for entry in register:
            self.assertIn(entry["id"], block)

    def test_site_registers_every_claim_and_every_view(self):
        """A number shown on the dashboard must be one the checker knows about."""
        html = (self.root / "index.html").read_text(encoding="utf-8")
        spans = set(re.findall(r'id="(claim-[a-z0-9-]+)"', html))
        self.assertTrue(spans, "the dashboard binds no claims")
        self.assertLessEqual(spans, set(CLAIM_PATTERNS),
                             "index.html carries a bound number the checker does not know about")
        tabs = set(re.findall(r'data-tab="([a-z0-9-]+)"', html))
        views = set(re.findall(r'<section id="view-([a-z0-9-]+)"', html))
        self.assertEqual(tabs - views, set(), "a nav tab points at a view that does not exist")


class TestPublishedArtifactsReconcile(unittest.TestCase):
    """Every published number, hash and claim must re-derive from the data files."""

    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.data = cls.root / "data"
        cls.ledger = json.loads((cls.data / "bets_ledger.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((cls.data / "ledger_manifest.json").read_text(encoding="utf-8"))
        cls.summary = json.loads((cls.data / "summary.json").read_text(encoding="utf-8"))
        cls.leaderboard = json.loads((cls.data / "leaderboard.json").read_text(encoding="utf-8"))
        cls.facts = published_facts(cls.data)

    def test_published_ledger_hash_chain_re_derives(self):
        ok, errors, head = verify_chain(self.ledger)
        self.assertTrue(ok, f"published ledger chain does not verify: {errors[:3]}")
        self.assertEqual(head, self.manifest["chain_head_hash"])
        self.assertEqual(self.ledger[-1]["hash"], self.manifest["chain_head_hash"])

    def test_a_tampered_record_breaks_the_chain(self):
        """Changing a settled record must be detectable without the generator."""
        tampered = [dict(record) for record in self.ledger[:5]]
        tampered[2]["pnl"] = tampered[2]["pnl"] + 1000.0
        self.assertNotEqual(tampered[2]["hash"], chain_hash(tampered[2], tampered[2]["previous_hash"]))
        ok, errors, _ = verify_chain(tampered)
        self.assertFalse(ok)
        self.assertTrue(any("does not match its contents" in error for error in errors))

    def test_ledger_manifest_reconciles_with_summary_and_leaderboard(self):
        self.assertEqual(self.manifest["published_bets"], len(self.ledger))
        self.assertEqual(self.manifest["all_time_bets"], self.summary["total_simulated_bets"])
        self.assertEqual(self.manifest["bets_outside_published_window"],
                         self.manifest["all_time_bets"] - len(self.ledger))
        published_pnl = round(sum(b["pnl"] for b in self.ledger), 2)
        tolerance = 0.011 * len(self.ledger) + 0.01
        self.assertLess(abs(self.manifest["published_pnl"] - published_pnl), tolerance)
        self.assertLess(abs(self.summary["ledger_published_pnl"] - published_pnl), tolerance)
        per_strategy: dict[str, float] = {}
        for bet in self.ledger:
            per_strategy[bet["strategy_id"]] = per_strategy.get(bet["strategy_id"], 0.0) + bet["pnl"]
        for row in self.leaderboard:
            expected = round(per_strategy.get(row["id"], 0.0), 2)
            slack = 0.011 * row["published_ledger_bets"] + 0.01
            self.assertLess(abs(row["published_ledger_pnl"] - expected), slack,
                            f"{row['id']} published PnL does not re-derive from the ledger")
            self.assertAlmostEqual(row["all_time_pnl"], row["total_pnl"], places=6)

    def test_readme_published_block_is_current(self):
        from scripts.render_readme import render

        readme_path = self.root / "README.md"
        current = readme_path.read_text(encoding="utf-8")
        expected = render(current, render_status_block(self.facts), render_badges(self.facts))
        self.assertEqual(current, expected, "README claims are stale; run scripts/render_readme.py")

    def test_site_claims_match_data(self):
        html = (self.root / "index.html").read_text(encoding="utf-8")
        found = site_claims(html)
        for claim in CLAIM_PATTERNS:
            self.assertIn(claim, found, f"{claim} must be bound in index.html")
        self.assertEqual(found, expected_site_claims(self.facts),
                         "index.html advertises numbers the data does not support")

    def test_week_slice_counts_follow_the_signal_queue(self):
        """The dashboard's live-slate numbers must come from the queue itself."""
        upcoming = json.loads((self.data / "upcoming_bets.json").read_text(encoding="utf-8"))
        slice_facts = self.facts["current_week_slice"]
        week = [b for b in upcoming
                if b.get("season") == slice_facts["season"] and b.get("week") == slice_facts["week"]]
        self.assertEqual(slice_facts["signals"], len(week))
        self.assertEqual(slice_facts["games"], len({b["game_id"] for b in week}))
        self.assertEqual(self.facts["season_span"],
                         f"{self.summary['season_first']}-{self.summary['season_last']}")

    def test_published_state_is_dated_from_the_data(self):
        """as_of_date must come from the played games, never a hand-typed date."""
        loader = NFLDataLoader(str(self.data / "source"))
        games = loader.load_all()
        latest = max(g["gameday"] for g in games if g["completed"])
        self.assertEqual(self.summary["as_of_date"], latest)

    def test_live_window_matches_the_snapshot(self):
        """summary's live slate must equal the engine's derivation, not a literal."""
        from engine.backtest_engine import derive_as_of_date, derive_live_window

        loader = NFLDataLoader(str(self.data / "source"))
        games = loader.load_all()
        season, week = derive_live_window(games)
        self.assertEqual(self.summary["current_season"], season)
        self.assertEqual(self.summary["current_week"], week)
        self.assertEqual(self.summary["as_of_date"], derive_as_of_date(games))
        completed_reg = [g for g in games
                         if g["season"] == season and g["completed"] and g.get("game_type") == "REG"]
        if week is not None:
            earlier = {g["week"] for g in completed_reg if g["week"] < week}
            for w in earlier:
                unplayed = [g for g in games if g["season"] == season and g["week"] == w and not g["completed"]]
                self.assertEqual(unplayed, [], f"week {w} earlier than the live week is not fully settled")

    def test_sync_manifest_is_present_and_hashes_match(self):
        from engine.source_sync import check_manifest

        ok, problems = check_manifest(str(self.data / "source"))
        hard = [p for p in problems if "pending review" not in p]
        self.assertEqual(hard, [], f"source sync manifest does not verify: {hard}")
        self.assertTrue((self.data / "source" / "sync_manifest.json").exists())


class TestLiveWindowDerivation(unittest.TestCase):
    """The paper-trading slate is computed from data, regressions included."""

    @staticmethod
    def _game(season, week, completed, game_type="REG"):
        return {
            "season": season,
            "week": week,
            "game_type": game_type,
            "completed": completed,
            "gameday": f"{season}-09-0{min(week, 9)}",
        }

    def test_partially_played_week_stays_live(self):
        from engine.backtest_engine import derive_live_window

        games = ([self._game(2026, 1, True)] * 16
                 + [self._game(2026, 2, True)] * 3 + [self._game(2026, 2, False)] * 13
                 + [self._game(2026, 3, False)] * 16)
        self.assertEqual(derive_live_window(games), (2026, 2))

    def test_week_advances_only_after_final_game_settles(self):
        from engine.backtest_engine import derive_live_window

        games = ([self._game(2026, 1, True)] * 16 + [self._game(2026, 2, True)] * 16
                 + [self._game(2026, 3, False)] * 16)
        self.assertEqual(derive_live_window(games), (2026, 3))

    def test_latest_season_wins(self):
        from engine.backtest_engine import derive_live_window

        games = ([self._game(2025, 1, True)] * 16 + [self._game(2025, 2, True)] * 16
                 + [self._game(2026, 1, True)] * 16 + [self._game(2026, 2, False)] * 16)
        self.assertEqual(derive_live_window(games), (2026, 2))

    def test_no_completed_games_returns_none(self):
        from engine.backtest_engine import derive_live_window

        self.assertEqual(derive_live_window([self._game(2026, 1, False)]), (None, None))
        self.assertEqual(derive_live_window([]), (None, None))

    def test_playoff_games_do_not_confuse_the_anchor(self):
        from engine.backtest_engine import derive_live_window

        games = ([self._game(2026, 1, True)] * 16 + [self._game(2026, 18, True)] * 16
                 + [self._game(2026, 19, False, "POST"), self._game(2026, 20, True, "POST")])
        # All regular season open weeks are gone -> live window advances past 18.
        season, week = derive_live_window(games)
        self.assertEqual(season, 2026)
        self.assertIs(week, None)


class TestSourceSyncDiff(unittest.TestCase):
    """Upstream revisions are classified and never silently absorbed."""

    HEADER = ("game_id,season,week,gameday,away_team,away_score,home_team,home_score,"
              "result,total,overtime,away_moneyline,home_moneyline,spread_line,"
              "away_spread_odds,home_spread_odds,total_line,under_odds,over_odds,"
              "away_qb_name,home_qb_name,away_qb_id,home_qb_id,away_coach,home_coach,referee,temp,wind")

    def _build(self, **per_game):
        rows = []
        for gid, fields in per_game.items():
            base = {
                "game_id": gid, "season": "2026", "week": "2", "gameday": "2026-09-21",
                "away_team": "MIA", "away_score": "", "home_team": "SF", "home_score": "",
                "result": "", "total": "", "overtime": "",
                "away_moneyline": "", "home_moneyline": "", "spread_line": "",
                "away_spread_odds": "", "home_spread_odds": "", "total_line": "",
                "under_odds": "", "over_odds": "",
                "away_qb_name": "", "home_qb_name": "", "away_qb_id": "", "home_qb_id": "",
                "away_coach": "", "home_coach": "", "referee": "", "temp": "", "wind": "",
            }
            base.update(fields)
            order = self.HEADER.split(",")
            rows.append(",".join(base[k] for k in order))
        return (self.HEADER + "\n" + "\n".join(rows) + "\n").encode("utf-8")

    def test_result_posting_is_info_and_not_settled(self):
        from engine.source_sync import diff_games_rows

        old = self._build(**{"2026_02_MIA_SF": {}})
        new = self._build(**{"2026_02_MIA_SF": {
            "away_score": "13", "home_score": "35", "result": "22", "total": "48", "overtime": "0"}})
        revisions, summary = diff_games_rows(old, new)
        posted = [r for r in revisions if r["type"] == "RESULT_POSTED"]
        self.assertEqual(len({r["field"] for r in posted}), 5)
        self.assertTrue(all(r["severity"] == "INFO" for r in posted))
        self.assertTrue(all(not r["settled_at_revision"] for r in posted))
        self.assertEqual(summary["posted_fields"], 5)

    def test_score_correction_on_settled_game_is_high_and_flagged(self):
        from engine.source_sync import diff_games_rows

        settled = {"away_score": "13", "home_score": "35", "result": "22", "total": "48", "overtime": "0"}
        old = self._build(**{"2026_02_MIA_SF": settled})
        changed = dict(settled, home_score="36", result="23", total="49")
        new = self._build(**{"2026_02_MIA_SF": changed})
        revisions, summary = diff_games_rows(old, new)
        corrections = [r for r in revisions if r["type"] == "RESULT_CORRECTED"]
        self.assertEqual(len(corrections), 3)
        self.assertTrue(all(r["severity"] == "HIGH" for r in corrections))
        self.assertTrue(all(r["settled_at_revision"] for r in corrections))
        self.assertEqual(summary["revised_fields"], 3)

    def test_qb_reassignment_is_medium_pre_kickoff(self):
        from engine.source_sync import diff_games_rows

        old = self._build(**{"2026_03_ATL_GB": {"away_qb_name": "Tua Tagovailoa", "away_qb_id": "00-0036212"}})
        new = self._build(**{"2026_03_ATL_GB": {"away_qb_name": "Michael Penix Jr.", "away_qb_id": "00-0039917"}})
        revisions, summary = diff_games_rows(old, new)
        qbs = [r for r in revisions if r["type"] == "QB_REASSIGNED"]
        self.assertEqual(len(qbs), 2)
        self.assertTrue(all(r["severity"] == "MEDIUM" for r in qbs))
        self.assertTrue(all(not r["settled_at_revision"] for r in qbs))

    def test_line_move_detected_separately_from_posting(self):
        from engine.source_sync import diff_games_rows

        old = self._build(**{"2026_02_MIA_SF": {"spread_line": "13.5", "away_spread_odds": "-110"}})
        new = self._build(**{"2026_02_MIA_SF": {"spread_line": "12.5", "away_spread_odds": "-110"}})
        revisions, summary = diff_games_rows(old, new)
        moved = [r for r in revisions if r["type"] == "LINE_MOVED"]
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["field"], "spread_line")
        self.assertEqual(summary["posted_fields"], 0)
        self.assertEqual(summary["revised_fields"], 1)

    def test_manifest_hash_check_detects_tampering(self):
        import hashlib as _hl
        from engine.source_sync import check_manifest

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "games.csv"
            path.write_bytes(b"game_id\nX\n")
            manifest = {
                "classification": "SOURCE_PROVENANCE",
                "synced_at_utc": "2026-09-22T00:00:00Z",
                "files": {"games.csv": {"fetch": {"sha256": _hl.sha256(b"game_id\nX\n").hexdigest()}}},
                "revisions": [],
            }
            (Path(tmp) / "sync_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            ok, problems = check_manifest(tmp)
            self.assertTrue(ok, problems)
            path.write_bytes(b"game_id\nTAMPERED\n")
            ok, problems = check_manifest(tmp)
            self.assertFalse(ok)
            self.assertTrue(any("sha256" in p for p in problems))

    def test_irregularity_promotion_carries_review_flags(self):
        from engine.source_sync import revisions_for_irregularity_register

        manifest = {
            "synced_at_utc": "2026-09-22T00:00:00Z",
            "upstream_repo": "https://github.com/nflverse/nfldata",
            "revision_summary": {"total_revisions": 2, "by_type": {"RESULT_CORRECTED": 1, "QB_REASSIGNED": 1}},
            "revisions": [
                {"file": "games.csv", "type": "RESULT_CORRECTED", "key": "2026_02_MIA_SF",
                 "field": "home_score", "old": "35", "new": "36", "severity": "HIGH",
                 "settled_at_revision": True},
                {"file": "games.csv", "type": "QB_REASSIGNED", "key": "2026_03_ATL_GB",
                 "field": "away_qb_name", "old": "A", "new": "B", "severity": "MEDIUM",
                 "settled_at_revision": False},
            ],
        }
        items = revisions_for_irregularity_register(manifest)
        self.assertEqual(len(items), 2)
        flagged = next(i for i in items if "RESULT_CORRECTED" in i["id"])
        self.assertEqual(flagged["status"], "FLAGGED")
        self.assertEqual(flagged["severity"], "HIGH")
        logged = next(i for i in items if "QB_REASSIGNED" in i["id"])
        self.assertEqual(logged["status"], "LOGGED_AND_RESOLVED")

if __name__ == "__main__":
    unittest.main()
