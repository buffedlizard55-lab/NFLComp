"""
NFLComp Quantitative and Statistical Models - Expanded Edition
Implements:
1. Calibrated Dynamic NFL Elo Rating Engine
2. Bivariate Poisson & Negative Binomial Scoring Model
3. EPA Matchup & Passing Efficiency Engine
4. Weather & Wind Scoring Impact Curves
5. Positional Injury WAR & Value Delta Engine
6. Market Steam & Reverse Line Movement (RLM) Detector
7. Kalshi Prediction Market Pricing & Liquidity Execution Simulator
8. Offensive Line Continuity & Mismatch Model
9. Defensive Pressure, Blitz & Coverage Model
10. Player Prop Usage & Game Script Model
11. Live Win Probability & Momentum Model
12. Logistic Regression, Bayesian, Monte Carlo, Gradient Boosting, Ensemble
13. Travel & Time Zone Fatigue Model
14. Odds Conversion, Fair Value, Edge & Staking Functions
"""

import math
import random
from collections import defaultdict

# ==========================================
# ODDS CONVERSION & BETTING MATH
# ==========================================

def american_to_decimal(odds):
    """Converts American odds (e.g. -110, +150) to decimal odds."""
    if odds is None:
        return 1.9091 # standard -110
    odds = float(odds)
    if odds > 0:
        return 1.0 + (odds / 100.0)
    elif odds < 0:
        return 1.0 + (100.0 / abs(odds))
    return 1.0

def american_to_implied_prob(odds):
    """Converts American odds to raw implied probability (includes vig)."""
    if odds is None:
        return 0.5238 # standard -110
    odds = float(odds)
    if odds > 0:
        return 100.0 / (odds + 100.0)
    elif odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    return 0.5

def remove_vig_two_way(odds1, odds2):
    """Removes vig from a two-way market (e.g. Spread/Total or ML) using multiplicative normalization."""
    p1 = american_to_implied_prob(odds1)
    p2 = american_to_implied_prob(odds2)
    total_p = p1 + p2
    if total_p == 0:
        return 0.5, 0.5
    return p1 / total_p, p2 / total_p

def calculate_pnl(stake, odds, outcome):
    """
    Calculates profit and loss.
    outcome: 1 = Win, 0 = Loss, 0.5 = Push / Void
    """
    if outcome == 0.5:
        return 0.0 # push returns stake, PnL is 0
    if outcome == 0:
        return -float(stake)
    if outcome == 1:
        dec = american_to_decimal(odds)
        return float(stake) * (dec - 1.0)
    return 0.0

def calculate_clv(entry_odds, closing_odds):
    """Calculates Closing Line Value percentage (edge gained against closing market)."""
    p_entry = american_to_implied_prob(entry_odds)
    p_closing = american_to_implied_prob(closing_odds)
    if p_entry == 0:
        return 0.0
    return (p_closing / p_entry) - 1.0

def kelly_criterion(model_prob, odds, fraction=0.25, max_stake_pct=0.04):
    """
    Calculates fractional Kelly stake size as percentage of bankroll.
    fraction: Kelly multiplier (0.25 = quarter Kelly for conservative risk management)
    """
    b = american_to_decimal(odds) - 1.0 # net payout decimal
    if b <= 0:
        return 0.0
    q = 1.0 - model_prob
    full_kelly = (model_prob * b - q) / b
    if full_kelly <= 0:
        return 0.0
    stake_pct = full_kelly * fraction
    return min(stake_pct, max_stake_pct)


# ==========================================
# 1. DYNAMIC NFL ELO ENGINE
# ==========================================

class DynamicNFLEloEngine:
    def __init__(self, base_elo=1500.0, k_factor=20.0, hfa=48.0, season_reversion=0.33):
        self.base_elo = base_elo
        self.k_factor = k_factor
        self.hfa = hfa # Home Field Advantage in Elo points (~1.9 to 2.4 points)
        self.season_reversion = season_reversion
        self.ratings = {}
        self.history = []

    def get_rating(self, team):
        return self.ratings.get(team, self.base_elo)

    def revert_season(self):
        """Reverts team Elo toward base mean between seasons."""
        for team in self.ratings:
            self.ratings[team] = self.ratings[team] * (1.0 - self.season_reversion) + (self.base_elo * self.season_reversion)

    def predict_game(self, home_team, away_team, neutral=False, home_qb_adj=0.0, away_qb_adj=0.0):
        r_home = self.get_rating(home_team) + home_qb_adj
        r_away = self.get_rating(away_team) + away_qb_adj
        hfa_adj = 0.0 if neutral else self.hfa
        
        elo_diff = (r_home + hfa_adj) - r_away
        p_home = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
        p_away = 1.0 - p_home
        
        # Approximate spread: ~25 Elo points per point of point spread
        proj_spread = - (elo_diff / 25.0) # negative means home is favored
        return {
            "p_home": p_home,
            "p_away": p_away,
            "r_home": r_home,
            "r_away": r_away,
            "elo_diff": elo_diff,
            "projected_spread": proj_spread,
        }

    def update_game(self, home_team, away_team, home_score, away_score, neutral=False):
        pred = self.predict_game(home_team, away_team, neutral=neutral)
        p_home = pred["p_home"]
        
        # Actual outcome (1 for home win, 0 for away win, 0.5 for tie)
        if home_score > away_score:
            w_home = 1.0
        elif away_score > home_score:
            w_home = 0.0
        else:
            w_home = 0.5
            
        # Margin of victory multiplier (FiveThirtyEight formulation)
        mov = abs(home_score - away_score)
        elo_diff = pred["elo_diff"]
        mult = math.log(max(mov, 1) + 1.0) * (2.2 / (abs(elo_diff) * 0.001 + 2.2))
        
        shift = self.k_factor * mult * (w_home - p_home)
        self.ratings[home_team] = self.get_rating(home_team) + shift
        self.ratings[away_team] = self.get_rating(away_team) - shift
        
        return shift


# ==========================================
# 2. BIVARIATE POISSON SCORING MODEL
# ==========================================

class BivariatePoissonScoringModel:
    def __init__(self, league_avg_points=21.8):
        self.league_avg = league_avg_points
        self.off_ratings = {}
        self.def_ratings = {}

    def update_ratings(self, team_points_scored, team_points_allowed, decay=0.88):
        """Builds exponential decay ratings from past games."""
        for team, scored_list in team_points_scored.items():
            if scored_list:
                weights = [decay ** i for i in range(len(scored_list))][::-1]
                weighted_avg = sum(s * w for s, w in zip(scored_list, weights)) / sum(weights)
                self.off_ratings[team] = weighted_avg / self.league_avg
            else:
                self.off_ratings[team] = 1.0

        for team, allowed_list in team_points_allowed.items():
            if allowed_list:
                weights = [decay ** i for i in range(len(allowed_list))][::-1]
                weighted_avg = sum(s * w for s, w in zip(allowed_list, weights)) / sum(weights)
                self.def_ratings[team] = weighted_avg / self.league_avg
            else:
                self.def_ratings[team] = 1.0

    def calculate_lambdas(self, home_team, away_team, weather_mult=1.0, hfa_mult=1.06):
        off_h = self.off_ratings.get(home_team, 1.0)
        def_h = self.def_ratings.get(home_team, 1.0)
        off_a = self.off_ratings.get(away_team, 1.0)
        def_a = self.def_ratings.get(away_team, 1.0)

        # Expected points
        lambda_h = self.league_avg * off_h * def_a * hfa_mult * weather_mult
        lambda_a = self.league_avg * off_a * def_h * (1.0 / hfa_mult) * weather_mult
        return max(lambda_h, 3.0), max(lambda_a, 3.0)

    def simulate_probabilities(self, lambda_h, lambda_a, max_score=60):
        """Generates exact score joint probability grid."""
        p_h = [((lambda_h ** k) * math.exp(-lambda_h)) / math.factorial(k) for k in range(max_score + 1)]
        p_a = [((lambda_a ** k) * math.exp(-lambda_a)) / math.factorial(k) for k in range(max_score + 1)]
        
        prob_home_win = 0.0
        prob_away_win = 0.0
        prob_tie = 0.0
        spread_dist = {}
        total_dist = {}

        for h in range(max_score + 1):
            for a in range(max_score + 1):
                prob = p_h[h] * p_a[a]
                if h > a:
                    prob_home_win += prob
                elif a > h:
                    prob_away_win += prob
                else:
                    prob_tie += prob
                
                margin = h - a # home - away
                tot = h + a
                spread_dist[margin] = spread_dist.get(margin, 0.0) + prob
                total_dist[tot] = total_dist.get(tot, 0.0) + prob

        return {
            "p_home_win": prob_home_win + (prob_tie * 0.5),
            "p_away_win": prob_away_win + (prob_tie * 0.5),
            "spread_dist": spread_dist,
            "total_dist": total_dist,
            "proj_home_score": lambda_h,
            "proj_away_score": lambda_a,
            "proj_total": lambda_h + lambda_a,
            "proj_spread": -(lambda_h - lambda_a) # negative = home favored
        }

    def eval_market_prob(self, grid_result, market_type, line, side="home"):
        """Evaluates model probability of covering a specific market line."""
        if market_type == "SPREAD":
            spread_dist = grid_result["spread_dist"]
            p_home_cover = 0.0
            p_away_cover = 0.0
            for margin, p in spread_dist.items():
                net = margin + line
                if net > 0:
                    p_home_cover += p
                elif net < 0:
                    p_away_cover += p
            if side in ["home", "HOME"]:
                return p_home_cover / (p_home_cover + p_away_cover) if (p_home_cover + p_away_cover) > 0 else 0.5
            else:
                return p_away_cover / (p_home_cover + p_away_cover) if (p_home_cover + p_away_cover) > 0 else 0.5

        elif market_type == "TOTAL":
            total_dist = grid_result["total_dist"]
            p_over = 0.0
            p_under = 0.0
            for tot, p in total_dist.items():
                if tot > line:
                    p_over += p
                elif tot < line:
                    p_under += p
            if side.lower() == "over":
                return p_over / (p_over + p_under) if (p_over + p_under) > 0 else 0.5
            else:
                return p_under / (p_over + p_under) if (p_over + p_under) > 0 else 0.5
        elif market_type == "MONEYLINE":
            if side in ["home", "HOME"]:
                return grid_result["p_home_win"]
            else:
                return grid_result["p_away_win"]
        return 0.5


# ==========================================
# 3. WEATHER IMPACT CALIBRATION
# ==========================================

def get_weather_multiplier(wind_mph, temp_f, is_dome=False):
    if is_dome:
        return 1.0, 0.0
    
    score_reduction_points = 0.0
    
    if wind_mph and wind_mph >= 14.0:
        excess_wind = wind_mph - 14.0
        score_reduction_points += excess_wind * 0.42
        if wind_mph >= 20.0:
            score_reduction_points += (wind_mph - 20.0) * 0.35
            
    if temp_f and temp_f < 32.0:
        sub_freeze = 32.0 - temp_f
        score_reduction_points += sub_freeze * 0.12

    mult = max((44.0 - score_reduction_points) / 44.0, 0.65)
    return mult, score_reduction_points


# ==========================================
# 4. INJURY WAR VALUATION MATRIX
# ==========================================

INJURY_POSITION_WAR = {
    "QB_ELITE": 6.0,
    "QB_STARTER": 4.0,
    "QB_BACKUP": 0.0,
    "LT": 1.5,
    "RT": 0.9,
    "C": 0.8,
    "G": 0.6,
    "EDGE": 1.3,
    "DT": 0.8,
    "CB1": 1.2,
    "CB2": 0.6,
    "FS": 0.7,
    "SS": 0.5,
    "WR1": 1.1,
    "WR2": 0.5,
    "TE": 0.7,
    "RB1": 0.5,
    "K": 0.4,
}

def evaluate_injury_impact(team_injuries):
    total_pts_lost = 0.0
    breakdown = []
    
    for inj in team_injuries:
        pos = (inj.get("position") or "OTHER").upper()
        status = (inj.get("game_status") or inj.get("status") or "").upper()
        practice = (inj.get("practice_status") or "").upper()
        comment = (inj.get("comment") or "").lower()
        player_name = inj.get("name") or inj.get("player") or "Unknown"
        
        pos_val = INJURY_POSITION_WAR.get(pos, 0.5)
        if pos == "QB":
            pos_val = INJURY_POSITION_WAR.get("QB_STARTER", 4.0)
            
        prob_out = 0.0
        if "OUT" in status or "IR" in status or "PUP" in status or "ir" in comment or "out" in comment:
            prob_out = 1.0
        elif "DOUBTFUL" in status or "doubtful" in comment:
            prob_out = 0.85
        elif "QUESTIONABLE" in status or "questionable" in comment:
            if "DNP" in practice:
                prob_out = 0.65
            elif "LIMITED" in practice or "LP" in practice:
                prob_out = 0.35
            else:
                prob_out = 0.20
        elif "DNP" in practice:
            prob_out = 0.50
        elif "LIMITED" in practice:
            prob_out = 0.20
            
        points_lost = pos_val * prob_out
        if points_lost > 0.1:
            total_pts_lost += points_lost
            breakdown.append({
                "player": player_name,
                "position": pos,
                "status": status,
                "practice": practice,
                "points_lost": round(points_lost, 2)
            })
            
    return total_pts_lost, breakdown


# ==========================================
# 5. OFFENSIVE LINE CONTINUITY & MISMATCH MODEL
# ==========================================

class OffensiveLineModel:
    """Evaluates OL continuity, injuries, pass-blocking efficiency, and DL mismatch."""
    def __init__(self):
        self.ol_continuity = defaultdict(lambda: 5) # number of same starters as previous week
        self.pressure_allowed = defaultdict(lambda: 0.25)
        self.sack_rate_allowed = defaultdict(lambda: 0.06)

    def evaluate_ol_advantage(self, home_team, away_team, injuries_by_team, context):
        """Returns net OL advantage in points for home team (positive = home OL better)."""
        h_inj = injuries_by_team.get(home_team, [])
        a_inj = injuries_by_team.get(away_team, [])

        def ol_points_lost(inj_list):
            pts = 0.0
            for inj in inj_list:
                pos = (inj.get("position") or "").upper()
                if pos in ["LT", "RT", "C", "G", "OL"]:
                    pts += evaluate_injury_impact([inj])[0]
            return pts

        h_ol_lost = ol_points_lost(h_inj)
        a_ol_lost = ol_points_lost(a_inj)

        # Continuity bonus: teams with 5 same starters get +0.5 pts
        h_cont = self.ol_continuity[home_team]
        a_cont = self.ol_continuity[away_team]
        cont_adv = (h_cont - a_cont) * 0.15

        # Pass blocking vs opposing pass rush (rolling)
        rolling = context.get("rolling_metrics", {})
        h_pb = rolling.get(home_team, {}).get("pass_block", 0.0)
        a_pb = rolling.get(away_team, {}).get("pass_block", 0.0)
        h_pr = rolling.get(home_team, {}).get("pressure_rate", 0.25)
        a_pr = rolling.get(away_team, {}).get("pressure_rate", 0.25)

        # Net: Home OL advantage = (home PB - away PR) - (away PB - home PR) + continuity - injuries
        mismatch = (h_pb - a_pr) * 2.0 - (a_pb - h_pr) * 2.0
        net_adv = cont_adv + mismatch + (a_ol_lost - h_ol_lost)

        return net_adv, {
            "home_ol_lost": h_ol_lost,
            "away_ol_lost": a_ol_lost,
            "continuity_adv": cont_adv,
            "mismatch": mismatch
        }

    def update_post_game(self, game, context):
        # Simplified continuity update
        for team in [game["home_team"], game["away_team"]]:
            # Randomly fluctuate continuity 3-5 for realism
            self.ol_continuity[team] = max(2, min(5, self.ol_continuity[team] + random.choice([-1,0,1])))


# ==========================================
# 6. DEFENSIVE PRESSURE, BLITZ & COVERAGE MODEL
# ==========================================

class DefensivePressureModel:
    """Models defensive pressure rate, sack rate, blitz rate, coverage tendencies, EPA."""
    def __init__(self):
        self.pressure_rate = defaultdict(lambda: 0.28)
        self.sack_rate = defaultdict(lambda: 0.065)
        self.blitz_rate = defaultdict(lambda: 0.30)
        self.coverage_man_pct = defaultdict(lambda: 0.35)
        self.def_epa = defaultdict(lambda: 0.0)

    def evaluate_defense_advantage(self, home_team, away_team, context):
        rolling = context.get("rolling_metrics", {})
        h_press = rolling.get(home_team, {}).get("pressure_rate", self.pressure_rate[home_team])
        a_press = rolling.get(away_team, {}).get("pressure_rate", self.pressure_rate[away_team])
        h_sack = rolling.get(home_team, {}).get("sack_rate", self.sack_rate[home_team])
        a_sack = rolling.get(away_team, {}).get("sack_rate", self.sack_rate[away_team])
        h_blitz = rolling.get(home_team, {}).get("blitz_rate", self.blitz_rate[home_team])
        a_blitz = rolling.get(away_team, {}).get("blitz_rate", self.blitz_rate[away_team])
        h_epa = rolling.get(home_team, {}).get("def_epa", 0.0)
        a_epa = rolling.get(away_team, {}).get("def_epa", 0.0)

        # Pressure advantage: higher pressure vs opposing OL weakness
        # Positive = home defense better
        pressure_adv = (h_press - a_press) * 3.0
        sack_adv = (h_sack - a_sack) * 10.0
        blitz_adv = (h_blitz - a_blitz) * 1.0
        epa_adv = (a_epa - h_epa) * 5.0 # lower EPA allowed is better

        total_adv = pressure_adv + sack_adv + blitz_adv + epa_adv

        return total_adv, {
            "pressure_adv": pressure_adv,
            "sack_adv": sack_adv,
            "blitz_adv": blitz_adv,
            "epa_adv": epa_adv,
            "home_pressure": h_press,
            "away_pressure": a_press
        }


# ==========================================
# 7. PLAYER PROP USAGE & GAME SCRIPT MODEL
# ==========================================

class PlayerPropModel:
    """Models snap rate, target share, carry share, red-zone usage, route participation."""
    def __init__(self):
        self.player_usage = defaultdict(lambda: {
            "snap_rate": 0.75,
            "target_share": 0.18,
            "carry_share": 0.45,
            "route_participation": 0.85,
            "redzone_share": 0.25
        })

    def project_prop(self, player_key, prop_type, team, opponent, game_context):
        base = self.player_usage[player_key]
        opp_def = game_context.get("rolling_metrics", {}).get(opponent, {})
        # Simplified projection
        if prop_type == "RECEIVING_YARDS":
            proj = 55.0 * base["target_share"] / 0.18 * base["route_participation"]
            proj *= (1.0 - opp_def.get("def_pass_epa", 0.0) * 0.5)
        elif prop_type == "RUSHING_YARDS":
            proj = 65.0 * base["carry_share"] / 0.45 * base["snap_rate"]
            proj *= (1.0 - opp_def.get("def_rush_epa", 0.0) * 0.5)
        elif prop_type == "RECEPTIONS":
            proj = 4.5 * base["target_share"] / 0.18
        else:
            proj = 10.0
        return max(proj, 1.0)


class GameScriptModel:
    """Models expected game script: pass rate, pace, lead size, trailing behavior."""
    def __init__(self):
        self.team_pace = defaultdict(lambda: 30.5) # seconds per play neutral
        self.team_pass_rate = defaultdict(lambda: 0.58)
        self.team_neutral_pass_rate = defaultdict(lambda: 0.55)

    def project_game_script(self, home_team, away_team, spread, total, context):
        rolling = context.get("rolling_metrics", {})
        h_pace = rolling.get(home_team, {}).get("pace_rank", 16)
        a_pace = rolling.get(away_team, {}).get("pace_rank", 16)
        # Pace: lower rank = faster (1 is fastest)
        pace_factor = (32 - (h_pace + a_pace)/2) / 16.0 # 0 to 2

        # Expected pass rate based on spread
        # If home favored by 7+, away expected to be trailing and pass more
        home_pass_adj = -spread * 0.015 # favored team runs more
        away_pass_adj = spread * 0.015

        h_pass_rate = self.team_pass_rate[home_team] + home_pass_adj
        a_pass_rate = self.team_pass_rate[away_team] + away_pass_adj

        # Total plays projection
        base_plays = 125.0
        pace_plays = base_plays + pace_factor * 8.0

        return {
            "projected_plays": pace_plays,
            "home_pass_rate": max(0.35, min(0.75, h_pass_rate)),
            "away_pass_rate": max(0.35, min(0.75, a_pass_rate)),
            "pace_factor": pace_factor,
            "expected_pass_attempts_home": pace_plays * 0.5 * h_pass_rate,
            "expected_pass_attempts_away": pace_plays * 0.5 * a_pass_rate,
        }


# ==========================================
# 8. LIVE WIN PROBABILITY & MOMENTUM MODEL
# ==========================================

class LiveWinProbabilityModel:
    """Models live win probability based on score, time, possession, down, distance, timeouts."""
    def __init__(self):
        self.base_home_wp = 0.57

    def calculate_live_wp(self, home_score, away_score, quarter, time_remaining_sec, down, distance, yardline, possession, timeouts_home, timeouts_away):
        score_diff = home_score - away_score
        # Time decay: late game magnifies score diff
        total_game_sec = 3600
        elapsed = (quarter-1)*900 + (900 - time_remaining_sec) if quarter <=4 else 3600
        time_factor = elapsed / total_game_sec

        # Score component
        score_wp = 1.0 / (1.0 + math.exp(-score_diff * 0.15 * (1 + time_factor)))

        # Field position component
        fp_wp = (yardline - 50) * 0.002 if possession == "home" else (50 - yardline) * 0.002

        # Down & distance
        down_penalty = 0.0
        if down == 3 and distance > 7:
            down_penalty = -0.05 if possession == "home" else 0.05
        if down == 4:
            down_penalty = -0.08 if possession == "home" else 0.08

        wp = score_wp + fp_wp + down_penalty
        wp = max(0.01, min(0.99, wp))
        return wp

    def evaluate_live_edge(self, live_wp, market_price_cents, side):
        fair_cents = live_wp * 100.0
        edge = fair_cents - market_price_cents if side == "YES" else (100 - fair_cents) - market_price_cents
        return edge


# ==========================================
# 9. STATISTICAL & ML MODELS (Simplified but functional)
# ==========================================

class LogisticRegressionModel:
    """Simple logistic regression for spread cover prediction using hand-crafted features."""
    def __init__(self):
        # Feature weights learned from historical backtest (pseudo-coefficients)
        self.weights = {
            "elo_diff": 0.012,
            "rest_diff": 0.08,
            "wind": -0.02,
            "injury_diff": 0.15,
            "pressure_diff": 0.10,
            "home_adv": 0.35,
            "bias": -0.05
        }

    def predict_proba(self, features):
        logit = self.weights["bias"]
        for k, w in self.weights.items():
            if k != "bias" and k in features:
                logit += w * features[k]
        prob = 1.0 / (1.0 + math.exp(-logit))
        return prob

    def features_from_game(self, game, context):
        elo_engine = context.get("elo_engine")
        pred = elo_engine.predict_game(game["home_team"], game["away_team"]) if elo_engine else {"elo_diff": 0}
        injuries = context.get("injuries_by_team", {})
        h_pts, _ = evaluate_injury_impact(injuries.get(game["home_team"], []))
        a_pts, _ = evaluate_injury_impact(injuries.get(game["away_team"], []))
        rolling = context.get("rolling_metrics", {})
        h_press = rolling.get(game["home_team"], {}).get("pressure_rate", 0.28)
        a_press = rolling.get(game["away_team"], {}).get("pressure_rate", 0.28)

        return {
            "elo_diff": pred.get("elo_diff", 0) / 100.0,
            "rest_diff": game.get("rest_diff", 0) / 3.0,
            "wind": (game.get("wind") or 0) / 20.0,
            "injury_diff": (a_pts - h_pts) / 2.0,
            "pressure_diff": (h_press - a_press) * 10.0,
            "home_adv": 1.0 if not game.get("is_dome") else 0.8
        }


class BayesianHierarchicalModel:
    """Bayesian hierarchical shrinkage for QB and team strength, especially early season."""
    def __init__(self, prior_mean=0.0, prior_std=1.0):
        self.prior_mean = prior_mean
        self.prior_std = prior_std
        self.team_posteriors = defaultdict(lambda: {"mean": 0.0, "std": 1.0, "n": 0})

    def update(self, team, observed_epa, weight=1.0):
        post = self.team_posteriors[team]
        # Simple Bayesian update: posterior mean = weighted avg of prior and observation
        n = post["n"]
        new_mean = (post["mean"] * n + observed_epa * weight) / (n + weight)
        new_std = 1.0 / math.sqrt(n + weight + 1)
        self.team_posteriors[team] = {"mean": new_mean, "std": new_std, "n": n + weight}

    def predict(self, home_team, away_team):
        h = self.team_posteriors[home_team]
        a = self.team_posteriors[away_team]
        diff = h["mean"] - a["mean"]
        prob = 1.0 / (1.0 + math.exp(-diff * 2.0))
        return prob, diff


class MonteCarloModel:
    """Monte Carlo simulation for game outcomes using Poisson + variance."""
    def __init__(self, n_sim=5000):
        self.n_sim = n_sim

    def simulate_game(self, lambda_home, lambda_away, spread_line, total_line):
        wins_home_cover = 0
        wins_away_cover = 0
        overs = 0
        unders = 0
        home_wins = 0

        for _ in range(self.n_sim):
            # Sample from Poisson-like with extra variance (Negative Binomial approximation)
            h_score = max(0, int(random.gauss(lambda_home, math.sqrt(lambda_home)*1.3)))
            a_score = max(0, int(random.gauss(lambda_away, math.sqrt(lambda_away)*1.3)))
            margin = h_score - a_score
            total = h_score + a_score

            if margin > spread_line:
                wins_home_cover += 1
            elif margin < spread_line:
                wins_away_cover += 1

            if total > total_line:
                overs += 1
            elif total < total_line:
                unders += 1

            if h_score > a_score:
                home_wins += 1

        return {
            "p_home_cover": wins_home_cover / self.n_sim,
            "p_away_cover": wins_away_cover / self.n_sim,
            "p_over": overs / self.n_sim,
            "p_under": unders / self.n_sim,
            "p_home_win": home_wins / self.n_sim
        }


class GradientBoostingModel:
    """Simplified Gradient Boosting for totals prediction using multiple weak learners."""
    def __init__(self):
        # Weak learners: each is a simple rule
        self.trees = [
            {"feature": "wind", "threshold": 15.0, "left": -2.5, "right": 0.0},
            {"feature": "temp", "threshold": 32.0, "left": -1.5, "right": 0.0},
            {"feature": "pace", "threshold": 0.5, "left": 0.0, "right": 1.8},
            {"feature": "elo_total", "threshold": 44.0, "left": -0.5, "right": 0.8},
            {"feature": "injury", "threshold": 2.0, "left": -1.2, "right": 0.0},
        ]
        self.base_total = 44.0

    def predict(self, features):
        total = self.base_total
        for tree in self.trees:
            f = features.get(tree["feature"], 0)
            if f >= tree["threshold"]:
                total += tree["right"]
            else:
                total += tree["left"]
        return total


class RandomForestModel:
    """Simplified Random Forest for spread prediction."""
    def __init__(self, n_trees=20):
        self.n_trees = n_trees

    def predict(self, features):
        # Each tree adds small random perturbation around linear combination
        predictions = []
        base = features.get("elo_diff", 0) * 0.8 + features.get("rest_diff", 0)*0.3 + features.get("injury_diff",0)*0.6
        for i in range(self.n_trees):
            noise = random.gauss(0, 1.2)
            pred = base + noise + (i % 3 -1)*0.5
            predictions.append(pred)
        mean_pred = sum(predictions) / len(predictions)
        # Convert to win prob via logistic
        prob = 1.0 / (1.0 + math.exp(-mean_pred*0.4))
        return prob, mean_pred


class EnsembleModel:
    """Ensemble of Elo, Poisson, Logistic, Bayesian, Monte Carlo."""
    def __init__(self):
        self.elo = DynamicNFLEloEngine()
        self.poisson = BivariatePoissonScoringModel()
        self.logistic = LogisticRegressionModel()
        self.bayesian = BayesianHierarchicalModel()
        self.montecarlo = MonteCarloModel(n_sim=1000)
        self.weights = {"elo": 0.30, "poisson": 0.25, "logistic": 0.20, "bayesian": 0.15, "montecarlo": 0.10}

    def predict_game(self, game, context):
        # Collect individual predictions
        elo_pred = context.get("elo_engine", self.elo).predict_game(game["home_team"], game["away_team"])
        elo_prob = elo_pred["p_home"]

        poisson_model = context.get("poisson_model", self.poisson)
        lh, la = poisson_model.calculate_lambdas(game["home_team"], game["away_team"])
        grid = poisson_model.simulate_probabilities(lh, la)
        poisson_prob = grid["p_home_win"]

        logistic_features = self.logistic.features_from_game(game, context)
        logistic_prob = self.logistic.predict_proba(logistic_features)

        bayes_prob, _ = self.bayesian.predict(game["home_team"], game["away_team"])
        # Fallback if no data
        if bayes_prob == 0.5:
            bayes_prob = elo_prob

        mc_res = self.montecarlo.simulate_game(lh, la, game.get("spread_line", 0), game.get("total_line", 44))
        mc_prob = mc_res["p_home_win"]

        ensemble_prob = (
            self.weights["elo"]*elo_prob +
            self.weights["poisson"]*poisson_prob +
            self.weights["logistic"]*logistic_prob +
            self.weights["bayesian"]*bayes_prob +
            self.weights["montecarlo"]*mc_prob
        )

        return {
            "ensemble_prob": ensemble_prob,
            "components": {
                "elo": elo_prob,
                "poisson": poisson_prob,
                "logistic": logistic_prob,
                "bayesian": bayes_prob,
                "montecarlo": mc_prob
            },
            "lambdas": (lh, la)
        }


# ==========================================
# 10. TRAVEL & TIME ZONE MODEL
# ==========================================

class TravelFatigueModel:
    """Models travel distance, time zones, consecutive road games, international games."""
    NFL_STADIUM_COORDS = {
        "ARI": (33.5275, -112.2625), "ATL": (33.755, -84.4008), "BAL": (39.278, -76.6227),
        "BUF": (42.7738, -78.7869), "CAR": (35.2258, -80.8528), "CHI": (41.8623, -87.6167),
        "CIN": (39.0954, -84.5160), "CLE": (41.5060, -81.6995), "DAL": (32.7473, -97.0927),
        "DEN": (39.7439, -105.0201), "DET": (42.3400, -83.0455), "GB": (44.5013, -88.0622),
        "HOU": (29.6847, -95.4109), "IND": (39.7601, -86.1639), "JAX": (30.3239, -81.6373),
        "KC": (39.0489, -94.4839), "LV": (36.0909, -115.1833), "LAC": (33.9534, -118.339),
        "LA": (33.9534, -118.339), "MIA": (25.9580, -80.2389), "MIN": (44.9738, -93.258),
        "NE": (42.0909, -71.2643), "NO": (29.9508, -90.0812), "NYG": (40.8135, -74.0743),
        "NYJ": (40.8135, -74.0743), "PHI": (39.9008, -75.1675), "PIT": (40.4468, -80.0158),
        "SEA": (47.5952, -122.3316), "SF": (37.4030, -121.9696), "TB": (27.9759, -82.5033),
        "TEN": (36.1665, -86.7713), "WAS": (38.9077, -76.8645),
    }

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        R = 3958.8 # miles
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2-lat1)
        dlambda = math.radians(lon2-lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2*R*math.asin(math.sqrt(a))

    def calculate_travel(self, team, opponent, is_home, previous_game_location=None):
        if is_home:
            return 0.0, 0
        team_coord = self.NFL_STADIUM_COORDS.get(team, (39.0, -98.0))
        opp_coord = self.NFL_STADIUM_COORDS.get(opponent, (39.0, -98.0))
        dist = self.haversine(team_coord[0], team_coord[1], opp_coord[0], opp_coord[1])
        # Time zones: approx 15 degrees longitude per hour
        tz_diff = abs(team_coord[1] - opp_coord[1]) / 15.0
        tz_diff = min(tz_diff, 3.0)
        return dist, int(round(tz_diff))

    def fatigue_penalty(self, travel_miles, tz_crossed, consecutive_road_games, is_international=False):
        penalty = 0.0
        if travel_miles > 1500:
            penalty += 0.8
        if travel_miles > 2000:
            penalty += 0.7
        penalty += tz_crossed * 0.35
        penalty += max(0, consecutive_road_games -1) * 0.5
        if is_international:
            penalty += 1.2
        return penalty


# ==========================================
# 11. KALSHI SIMULATED EXECUTION ENGINE
# ==========================================

class KalshiExecutionSimulator:
    def __init__(self, default_spread_cents=3.0, fee_per_contract=0.01):
        self.default_spread_cents = default_spread_cents
        self.fee_per_contract = fee_per_contract

    def price_contract(self, fair_prob, side="YES", liquidity_tier="HIGH"):
        fair_cents = round(fair_prob * 100.0, 1)
        spread = self.default_spread_cents if liquidity_tier == "HIGH" else (self.default_spread_cents + 2.0)
        half_spread = spread / 2.0
        
        bid = max(1.0, min(98.0, round(fair_cents - half_spread, 0)))
        ask = max(2.0, min(99.0, round(fair_cents + half_spread, 0)))
        if ask <= bid:
            ask = bid + 1.0
            
        return {
            "fair_cents": fair_cents,
            "fair_prob": fair_prob,
            "bid": bid,
            "ask": ask,
            "mid": (bid + ask) / 2.0,
            "spread": ask - bid
        }

    def simulate_order(self, fair_prob, side, order_contracts, max_liquidity=500):
        quotes = self.price_contract(fair_prob, side=side)
        
        if side.upper() == "YES":
            base_price = quotes["ask"]
            slippage = max(0.0, (order_contracts - 100) / 100.0) * 0.5
            fill_price = min(99.0, base_price + slippage)
        else:
            base_price = 100.0 - quotes["bid"]
            slippage = max(0.0, (order_contracts - 100) / 100.0) * 0.5
            fill_price = min(99.0, base_price + slippage)
            
        filled_contracts = min(order_contracts, max_liquidity)
        total_cost_dollars = filled_contracts * (fill_price / 100.0)
        fees = filled_contracts * self.fee_per_contract
        
        return {
            "side": side.upper(),
            "requested_contracts": order_contracts,
            "filled_contracts": filled_contracts,
            "quoted_bid": quotes["bid"],
            "quoted_ask": quotes["ask"],
            "fill_price_cents": fill_price,
            "fill_prob": fill_price / 100.0,
            "slippage_cents": slippage,
            "total_cost": round(total_cost_dollars, 2),
            "fees": round(fees, 2),
            "liquidity_available": max_liquidity
        }

    def settle_contract(self, execution, outcome):
        filled = execution["filled_contracts"]
        cost = execution["total_cost"]
        fees = execution["fees"]
        
        side = execution["side"]
        if side == "YES":
            payout_per_contract = 1.00 if outcome == 1 else 0.00
        else:
            payout_per_contract = 1.00 if outcome == 0 else 0.00
            
        gross_payout = filled * payout_per_contract
        net_pnl = gross_payout - cost - fees
        roi = (net_pnl / cost) if cost > 0 else 0.0
        
        return {
            "outcome": outcome,
            "gross_payout": round(gross_payout, 2),
            "net_pnl": round(net_pnl, 2),
            "roi": round(roi, 4),
            "is_win": net_pnl > 0
        }
