"""
NFLComp Quantitative Engine Unit and Integration Tests
Tests:
- Data Loader integrity
- Elo and Poisson models
- Strategy signal evaluation
- PnL calculations
- Bet ledger consistency
- Audit verifier zero-hallucination checks
"""

import unittest
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.data_loader import NFLDataLoader
from engine.models import (
    DynamicNFLEloEngine,
    BivariatePoissonScoringModel,
    american_to_decimal,
    american_to_implied_prob,
    calculate_pnl,
    calculate_clv,
    KalshiExecutionSimulator,
    evaluate_injury_impact
)
from engine.strategy_registry import ALL_STRATEGY_DEFINITIONS, get_strategy_instances
from engine.audit_verifier import NFLAuditVerifier

class TestNFLComp(unittest.TestCase):
    def setUp(self):
        self.loader = NFLDataLoader("data/source")
        self.games = self.loader.load_all()

    def test_data_loader_games(self):
        self.assertGreater(len(self.games), 7000)
        completed = [g for g in self.games if g["completed"]]
        self.assertGreater(len(completed), 7200)
        
        # Check 2026 games
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
        self.assertGreater(pred["p_home"], 0.50) # Home team with HFA should have > 50% vs equal rating

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

    def test_odds_conversion(self):
        self.assertAlmostEqual(american_to_decimal(-110), 1.90909, places=4)
        self.assertAlmostEqual(american_to_decimal(150), 2.50, places=4)
        self.assertAlmostEqual(american_to_implied_prob(-110), 0.5238, places=3)
        self.assertAlmostEqual(american_to_implied_prob(150), 0.40, places=3)

    def test_pnl_math(self):
        # Bet $100 on -110 Win
        pnl_win = calculate_pnl(100.0, -110.0, 1.0)
        self.assertAlmostEqual(pnl_win, 90.91, places=2)
        
        # Bet $100 on -110 Loss
        pnl_loss = calculate_pnl(100.0, -110.0, 0.0)
        self.assertEqual(pnl_loss, -100.0)
        
        # Push
        pnl_push = calculate_pnl(100.0, -110.0, 0.5)
        self.assertEqual(pnl_push, 0.0)

    def test_kalshi_simulation(self):
        sim = KalshiExecutionSimulator()
        order = sim.simulate_order(0.60, "YES", 100)
        self.assertEqual(order["filled_contracts"], 100)
        self.assertGreater(order["fill_price_cents"], 55.0)
        settle_win = sim.settle_contract(order, 1)
        self.assertTrue(settle_win["is_win"])
        self.assertGreater(settle_win["net_pnl"], 0.0)

    def test_strategy_instances(self):
        strats = get_strategy_instances()
        self.assertGreaterEqual(len(strats), 20)
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

    def test_audit_verifier(self):
        verifier = NFLAuditVerifier("data")
        audit_res = verifier.run_full_audit()
        self.assertEqual(audit_res["failed_checks"], 0)
        self.assertGreaterEqual(audit_res["passed_checks"], 8)

if __name__ == "__main__":
    unittest.main()
