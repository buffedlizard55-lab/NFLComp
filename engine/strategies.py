"""
NFLComp Quantitative Strategies Engine (Calibrated with Verified Sourcing)
Correctly aligns with nflverse dataset conventions:
- result = home_score - away_score
- spread_line = home expected margin (positive = home favored, negative = away favored)
- Home covers when result > spread_line
- Away covers when result < spread_line
"""

class NFLStrategy:
    def __init__(self, meta):
        self.meta = meta
        self.id = meta["id"]
        self.username = meta["username"]
        self.name = meta["name"]
        self.version = meta["version"]
        self.category = meta["category"]
        self.hypothesis = meta.get("hypothesis", "")
        self.initial_bankroll = float(meta.get("initial_bankroll", 10000.0))
        self.bankroll = self.initial_bankroll
        self.base_stake = float(meta.get("base_stake", 100.0))
        self.stake_pct = float(meta.get("stake_pct", 0.01))
        self.stake_type = meta.get("stake_type", "FLAT")
        self.min_edge = float(meta.get("min_edge", 0.025))
        self.is_kalshi = meta.get("is_kalshi", False)

    def evaluate_game(self, game, context):
        raise NotImplementedError

# 1. QUARTERBACK EPA STRATEGIES (v1, v2, v3)
class QBEPAStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        if not game.get("home_team") or not game.get("away_team"):
            return []
        
        home = game["home_team"]
        away = game["away_team"]
        market_spread = game.get("spread_line") # positive = home favored
        if market_spread is None:
            return []

        rolling = context.get("rolling_metrics", {})
        h_epa = rolling.get(home, {}).get("pass_epa", 0.0)
        a_epa = rolling.get(away, {}).get("pass_epa", 0.0)
        
        if self.version == "v1":
            # Model expected margin for home team
            model_margin = (h_epa - a_epa) * 16.0 + 1.8 # 1.8 pt home advantage
            edge_pts = model_margin - market_spread
            threshold = 2.0
        elif self.version == "v2":
            h_def = rolling.get(home, {}).get("def_pass_epa", 0.0)
            a_def = rolling.get(away, {}).get("def_pass_epa", 0.0)
            net_h = h_epa - a_def
            net_a = a_epa - h_def
            model_margin = (net_h - net_a) * 15.0 + 2.0
            edge_pts = model_margin - market_spread
            threshold = 2.5
        else: # v3
            h_cpoe = rolling.get(home, {}).get("cpoe", 0.0)
            a_cpoe = rolling.get(away, {}).get("cpoe", 0.0)
            comp_h = h_epa * 0.7 + (h_cpoe / 10.0) * 0.3
            comp_a = a_epa * 0.7 + (a_cpoe / 10.0) * 0.3
            model_margin = (comp_h - comp_a) * 15.0 + 1.9
            edge_pts = model_margin - market_spread
            threshold = 3.0

        if abs(edge_pts) < threshold:
            return []

        bet_home = edge_pts > 0 # model expects home to outperform market spread
        sel_team = home if bet_home else away
        side = "home" if bet_home else "away"
        odds = game.get("home_spread_odds", -110.0) if bet_home else game.get("away_spread_odds", -110.0)
        
        model_prob = 0.50 + min(abs(edge_pts) * 0.018, 0.075)
        implied_p = 0.5238
        edge = model_prob - implied_p

        if edge < self.min_edge:
            return []

        stake = self.base_stake if self.stake_type == "FLAT" else (self.bankroll * self.stake_pct)
        # Display notation: Home is -market_spread, Away is +market_spread
        display_line = -market_spread if bet_home else market_spread
        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "SPREAD",
            "selection": f"{sel_team} {display_line:+.1f}",
            "side": side,
            "market_line": market_spread,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(implied_p, 4),
            "edge": round(edge, 4),
            "stake": round(stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "model_margin": round(model_margin, 2),
                "market_spread": market_spread,
                "spread_edge_pts": round(abs(edge_pts), 2),
                "home_pass_epa": round(h_epa, 3),
                "away_pass_epa": round(a_epa, 3),
                "version": self.version
            }
        }]

# 2. BACKUP QB CONTRARIAN
class BackupQBContrarianStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        spread = game.get("spread_line")
        open_spread = game.get("open_spread")
        if spread is None or open_spread is None:
            return []
        
        move = game.get("spread_move", 0.0) # spread - open_spread
        threshold = 2.0 if self.version == "v1" else 3.0
        if abs(move) < threshold:
            return []

        # If move < 0: line moved against home (e.g. 6.0 down to 2.5) -> fade panic, bet home
        bet_home = move < 0
        sel_team = game["home_team"] if bet_home else game["away_team"]
        side = "home" if bet_home else "away"
        odds = game.get("home_spread_odds", -110.0) if bet_home else game.get("away_spread_odds", -110.0)
        
        model_prob = 0.548
        implied_p = 0.5238
        edge = model_prob - implied_p

        display_line = -spread if bet_home else spread
        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "SPREAD",
            "selection": f"{sel_team} {display_line:+.1f}",
            "side": side,
            "market_line": spread,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(implied_p, 4),
            "edge": round(edge, 4),
            "stake": round(self.base_stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "spread_move_pts": round(move, 1),
                "open_spread": open_spread,
                "closing_spread": spread,
                "thesis": "Fading market overreaction to QB absence"
            }
        }]

# 3. WEATHER WIND TOTALS STRATEGY
class WeatherWindTotalsStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        if game.get("is_dome"):
            return []
        wind = game.get("wind")
        total = game.get("total_line")
        if wind is None or total is None:
            return []
        
        wind_thresh = 15.0 if self.version == "v1" else (16.5 if self.version == "v2" else 18.0)
        min_total = 38.5 if self.version == "v1" else 40.5
        
        if wind < wind_thresh or total < min_total:
            return []

        extra_wind = wind - wind_thresh
        model_prob = 0.545 + min(extra_wind * 0.012, 0.065)
        implied_p = 0.5238
        edge = model_prob - implied_p

        odds = game.get("under_odds", -110.0)
        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "TOTAL",
            "selection": f"Under {total:.1f}",
            "side": "under",
            "market_line": total,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(implied_p, 4),
            "edge": round(edge, 4),
            "stake": round(self.base_stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "wind_mph": wind,
                "temperature_f": game.get("temp"),
                "stadium": game.get("stadium"),
                "version": self.version
            }
        }]

# 4. DOME PACE OVERS
class DomePaceOverStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        if not game.get("is_dome"):
            return []
        total = game.get("total_line")
        if total is None or total > 48.5:
            return []

        rolling = context.get("rolling_metrics", {})
        h_pace = rolling.get(game["home_team"], {}).get("pace_rank", 16)
        a_pace = rolling.get(game["away_team"], {}).get("pace_rank", 16)
        
        if self.version == "v1":
            if (h_pace + a_pace) / 2.0 > 14:
                return []
        else: # v2
            h_proe = rolling.get(game["home_team"], {}).get("proe", 0.0)
            a_proe = rolling.get(game["away_team"], {}).get("proe", 0.0)
            if h_proe < 0.01 or a_proe < 0.01:
                return []

        model_prob = 0.550
        implied_p = 0.5238
        edge = model_prob - implied_p

        odds = game.get("over_odds", -110.0)
        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "TOTAL",
            "selection": f"Over {total:.1f}",
            "side": "over",
            "market_line": total,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(implied_p, 4),
            "edge": round(edge, 4),
            "stake": round(self.base_stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "is_dome": True,
                "home_pace_rank": h_pace,
                "away_pace_rank": a_pace,
                "total_line": total
            }
        }]

# 5. REST DISADVANTAGE & TNF STRATEGY
class RestAdvantageStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        spread = game.get("spread_line")
        if spread is None:
            return []
        
        rest_diff = game.get("rest_diff", 0)
        if self.version == "v1":
            if rest_diff < 3:
                return []
            sel_team = game["home_team"]
            side = "home"
            odds = game.get("home_spread_odds", -110.0)
            model_prob = 0.545
        else: # v2 TNF
            if game.get("weekday") != "Thursday" or game.get("away_rest", 7) > 4:
                return []
            sel_team = game["home_team"]
            side = "home"
            odds = game.get("home_spread_odds", -110.0)
            model_prob = 0.562

        implied_p = 0.5238
        edge = model_prob - implied_p
        if edge < self.min_edge:
            return []

        display_line = -spread
        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "SPREAD",
            "selection": f"{sel_team} {display_line:+.1f}",
            "side": side,
            "market_line": spread,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(implied_p, 4),
            "edge": round(edge, 4),
            "stake": round(self.base_stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "rest_diff_days": rest_diff,
                "home_rest": game.get("home_rest"),
                "away_rest": game.get("away_rest"),
                "weekday": game.get("weekday")
            }
        }]

# 6. ELO QUANT STRATEGIES (v1, v2, v3)
class EloQuantStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        elo_engine = context.get("elo_engine")
        if not elo_engine:
            return []

        pred = elo_engine.predict_game(game["home_team"], game["away_team"])
        market_spread = game.get("spread_line") # positive = home favored
        if market_spread is None:
            return []

        # Model expected margin: -proj_spread (positive = home favored)
        model_margin = -pred["projected_spread"]
        spread_edge = model_margin - market_spread
        
        threshold = 2.0 if self.version == "v1" else (2.8 if self.version == "v2" else 3.5)
        if abs(spread_edge) < threshold:
            return []

        bet_home = spread_edge > 0
        sel_team = game["home_team"] if bet_home else game["away_team"]
        side = "home" if bet_home else "away"
        odds = game.get("home_spread_odds", -110.0) if bet_home else game.get("away_spread_odds", -110.0)
        
        model_prob = 0.50 + min(abs(spread_edge) * 0.015, 0.075)
        implied_p = 0.5238
        edge = model_prob - implied_p

        if edge < self.min_edge:
            return []

        stake = self.base_stake if self.stake_type == "FLAT" else (self.bankroll * self.stake_pct)
        display_line = -market_spread if bet_home else market_spread
        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "SPREAD",
            "selection": f"{sel_team} {display_line:+.1f}",
            "side": side,
            "market_line": market_spread,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(implied_p, 4),
            "edge": round(edge, 4),
            "stake": round(stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "elo_proj_margin": round(model_margin, 2),
                "market_spread": market_spread,
                "spread_edge_pts": round(abs(spread_edge), 2),
                "elo_home": round(pred["r_home"], 1),
                "elo_away": round(pred["r_away"], 1)
            }
        }]

# 7. BIVARIATE POISSON SCORING MODEL (v1, v2)
class PoissonScoringStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        poisson_model = context.get("poisson_model")
        if not poisson_model:
            return []

        total_line = game.get("total_line")
        if total_line is None:
            return []

        lh, la = poisson_model.calculate_lambdas(game["home_team"], game["away_team"])
        grid = poisson_model.simulate_probabilities(lh, la)
        
        proj_total = grid["proj_total"]
        diff = total_line - proj_total
        
        threshold = 2.5 if self.version == "v1" else 3.5
        if abs(diff) < threshold:
            return []

        bet_under = diff > 0
        sel = f"Under {total_line:.1f}" if bet_under else f"Over {total_line:.1f}"
        side = "under" if bet_under else "over"
        odds = game.get("under_odds", -110.0) if bet_under else game.get("over_odds", -110.0)
        
        raw_prob = poisson_model.eval_market_prob(grid, "TOTAL", total_line, side=side)
        model_prob = 0.50 + (raw_prob - 0.50) * 0.40
        implied_p = 0.5238
        edge = model_prob - implied_p

        if edge < self.min_edge:
            return []

        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "TOTAL",
            "selection": sel,
            "side": side,
            "market_line": total_line,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(implied_p, 4),
            "edge": round(edge, 4),
            "stake": round(self.base_stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "poisson_proj_total": round(proj_total, 2),
                "market_total": total_line,
                "lambda_home": round(lh, 2),
                "lambda_away": round(la, 2)
            }
        }]

# 8. REVERSE LINE MOVEMENT / SHARP MONEY (v1, v2, v3)
class RLMStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        spread = game.get("spread_line")
        open_spread = game.get("open_spread")
        if spread is None or open_spread is None:
            return []

        move = game.get("spread_move", 0.0)
        threshold = 1.0 if self.version == "v1" else (1.5 if self.version == "v2" else 2.0)
        if abs(move) < threshold:
            return []

        # If move > 0: line moved in favor of home (e.g. from 3.0 to 4.5) -> steam on home
        bet_home = move > 0
        sel_team = game["home_team"] if bet_home else game["away_team"]
        side = "home" if bet_home else "away"
        odds = game.get("home_spread_odds", -110.0) if bet_home else game.get("away_spread_odds", -110.0)

        model_prob = 0.540 + min(abs(move) * 0.008, 0.04)
        implied_p = 0.5238
        edge = model_prob - implied_p

        display_line = -spread if bet_home else spread
        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "SPREAD",
            "selection": f"{sel_team} {display_line:+.1f}",
            "side": side,
            "market_line": spread,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(implied_p, 4),
            "edge": round(edge, 4),
            "stake": round(self.base_stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "open_spread": open_spread,
                "close_spread": spread,
                "line_move_pts": round(move, 1)
            }
        }]

# 9. INJURY WAR VALUATION STRATEGY
class InjuryValuationStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        inj_data = context.get("injuries_by_team", {})
        h_inj = inj_data.get(game["home_team"], [])
        a_inj = inj_data.get(game["away_team"], [])
        
        if not h_inj and not a_inj:
            return []

        from engine.models import evaluate_injury_impact
        h_pts, h_list = evaluate_injury_impact(h_inj)
        a_pts, a_list = evaluate_injury_impact(a_inj)

        net_inj_diff = a_pts - h_pts # positive = advantage home
        threshold = 1.5 if self.version == "v1" else (2.2 if self.version == "v2" else 3.0)
        
        if abs(net_inj_diff) < threshold:
            return []

        bet_home = net_inj_diff > 0
        spread = game.get("spread_line")
        if spread is None:
            return []

        sel_team = game["home_team"] if bet_home else game["away_team"]
        side = "home" if bet_home else "away"
        odds = game.get("home_spread_odds", -110.0) if bet_home else game.get("away_spread_odds", -110.0)

        model_prob = 0.542 + min(abs(net_inj_diff) * 0.008, 0.04)
        implied_p = 0.5238
        edge = model_prob - implied_p

        display_line = -spread if bet_home else spread
        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "SPREAD",
            "selection": f"{sel_team} {display_line:+.1f}",
            "side": side,
            "market_line": spread,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(implied_p, 4),
            "edge": round(edge, 4),
            "stake": round(self.base_stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "home_injury_pts_lost": round(h_pts, 2),
                "away_injury_pts_lost": round(a_pts, 2),
                "net_injury_advantage_pts": round(net_inj_diff, 2),
                "top_home_absences": [i.get("player", "") for i in h_list[:2]],
                "top_away_absences": [i.get("player", "") for i in a_list[:2]]
            }
        }]

# 10. KALSHI PREDICTION MARKETS STRATEGY
class KalshiPredictionMarketStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        poisson_model = context.get("poisson_model")
        if not poisson_model:
            return []

        spread = game.get("spread_line")
        if spread is None:
            return []

        lh, la = poisson_model.calculate_lambdas(game["home_team"], game["away_team"])
        grid = poisson_model.simulate_probabilities(lh, la)
        
        # Fair prob that home wins by more than spread
        raw_prob = poisson_model.eval_market_prob(grid, "SPREAD", -spread, side="home")
        p_home_cover = 0.50 + (raw_prob - 0.50) * 0.45
        
        fair_cents = p_home_cover * 100.0
        mkt_price_cents = 50.0
        edge_cents = fair_cents - mkt_price_cents

        threshold = 3.5 if self.version == "v1" else 5.5
        if abs(edge_cents) < threshold:
            return []

        buy_yes = edge_cents > 0
        side = "YES" if buy_yes else "NO"
        model_prob = p_home_cover if buy_yes else (1.0 - p_home_cover)
        entry_price_cents = 52.0 if buy_yes else 52.0

        contract_ticker = f"KXNFL-{game['season']}-W{game['week']}-{game['home_team']}-COV"

        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "KALSHI_SPREAD",
            "contract_ticker": contract_ticker,
            "selection": f"{contract_ticker} ({side})",
            "side": side.lower(),
            "market_line": spread,
            "market_price_cents": entry_price_cents,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(entry_price_cents / 100.0, 4),
            "edge": round(model_prob - (entry_price_cents / 100.0), 4),
            "stake": round(self.base_stake, 2),
            "contracts": int(self.base_stake / (entry_price_cents / 100.0)),
            "status": "QUALIFIED",
            "supporting_data": {
                "fair_cents": round(fair_cents, 1),
                "side": side,
                "spread_barrier": spread,
                "kalshi_fees": 1.00
            }
        }]

# 11. REFEREE PENALTY TENDENCIES
class RefereePenaltyTotalsStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        ref = game.get("referee", "")
        if not ref:
            return []
        
        ref_stats = context.get("referee_stats", {}).get(ref, {})
        avg_flags = ref_stats.get("avg_penalties", 12.5)
        total_line = game.get("total_line")
        if total_line is None:
            return []

        if avg_flags >= 14.5 and total_line <= 43.5:
            model_prob = 0.548
            odds = game.get("over_odds", -110.0)
            return [{
                "strategy_id": self.id,
                "username": self.username,
                "game_id": game["game_id"],
                "market": "TOTAL",
                "selection": f"Over {total_line:.1f}",
                "side": "over",
                "market_line": total_line,
                "market_odds": odds,
                "model_prob": round(model_prob, 4),
                "implied_prob": 0.5238,
                "edge": round(model_prob - 0.5238, 4),
                "stake": round(self.base_stake, 2),
                "status": "QUALIFIED",
                "supporting_data": {
                    "referee": ref,
                    "avg_penalties_per_game": round(avg_flags, 1),
                    "total_line": total_line
                }
            }]
        return []

# 12. THURSDAY NIGHT FOOTBALL UNDER
class ThursdayUnderTrendStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        if game.get("weekday") != "Thursday":
            return []
        total = game.get("total_line")
        if total is None or total < 41.0:
            return []

        model_prob = 0.542
        odds = game.get("under_odds", -110.0)
        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "TOTAL",
            "selection": f"Under {total:.1f}",
            "side": "under",
            "market_line": total,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": 0.5238,
            "edge": round(model_prob - 0.5238, 4),
            "stake": round(self.base_stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "day": "Thursday",
                "total_line": total,
                "thesis": "Short 4-day prep creates sloppy execution"
            }
        }]

# 13. COACHING 4TH DOWN AGGRESSIVENESS
class Coaching4thDownStrategy(NFLStrategy):
    def evaluate_game(self, game, context):
        h_coach = game.get("home_coach", "")
        a_coach = game.get("away_coach", "")
        coach_stats = context.get("coach_stats", {})
        
        h_agg = coach_stats.get(h_coach, {}).get("go_for_it_rate", 0.50)
        a_agg = coach_stats.get(a_coach, {}).get("go_for_it_rate", 0.50)
        
        diff = h_agg - a_agg
        if abs(diff) < 0.20:
            return []

        spread = game.get("spread_line")
        if spread is None:
            return []

        bet_home = diff > 0
        sel_team = game["home_team"] if bet_home else game["away_team"]
        side = "home" if bet_home else "away"
        odds = game.get("home_spread_odds", -110.0) if bet_home else game.get("away_spread_odds", -110.0)

        model_prob = 0.545
        implied_p = 0.5238
        display_line = -spread if bet_home else spread
        return [{
            "strategy_id": self.id,
            "username": self.username,
            "game_id": game["game_id"],
            "market": "SPREAD",
            "selection": f"{sel_team} {display_line:+.1f}",
            "side": side,
            "market_line": spread,
            "market_odds": odds,
            "model_prob": round(model_prob, 4),
            "implied_prob": round(implied_p, 4),
            "edge": round(model_prob - implied_p, 4),
            "stake": round(self.base_stake, 2),
            "status": "QUALIFIED",
            "supporting_data": {
                "home_coach": h_coach,
                "home_coach_agg": round(h_agg, 2),
                "away_coach": a_coach,
                "away_coach_agg": round(a_agg, 2)
            }
        }]
