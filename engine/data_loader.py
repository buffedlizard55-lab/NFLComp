"""
NFLComp Data Loader and Preprocessor
Loads, cleans, validates, and cross-references all primary NFL datasets:
- nflverse/nfldata games (1999-2026)
- closing sportsbook lines
- opening lines
- FiveThirtyEight calibrated Elo ratings
- referee / officials data
- team metadata and stadium environments
- official NFL injury reports
"""

import csv
import json
import os
import math
from datetime import datetime

class NFLDataLoader:
    def __init__(self, data_dir="data/source"):
        self.data_dir = data_dir
        self.games = []
        self.closing_lines = {}
        self.initial_lines = {}
        self.elo_by_game = {}
        self.officials_by_game = {}
        self.teams_meta = {}
        self.injuries = {}
        self.irregularities = []

    def load_all(self):
        self._load_teams()
        self._load_closing_lines()
        self._load_initial_lines()
        self._load_elo_ratings()
        self._load_officials()
        self._load_injuries()
        self._load_games()
        return self.games

    def _load_teams(self):
        path = os.path.join(self.data_dir, "teams.csv")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for r in reader:
                team = r.get("team")
                if team and team not in self.teams_meta:
                    self.teams_meta[team] = {
                        "team": team,
                        "full_name": r.get("full", ""),
                        "location": r.get("location", ""),
                        "nickname": r.get("nickname", ""),
                        "nfl_id": r.get("nfl_team_id", ""),
                        "pfr": r.get("pfr", ""),
                    }

    def _load_closing_lines(self):
        path = os.path.join(self.data_dir, "closing_lines.csv")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for r in reader:
                gid = r.get("game_id") or r.get("alt_game_id")
                if not gid:
                    continue
                if gid not in self.closing_lines:
                    self.closing_lines[gid] = []
                self.closing_lines[gid].append(r)

    def _load_initial_lines(self):
        path = os.path.join(self.data_dir, "initial_lines.csv")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for r in reader:
                gid = r.get("about")
                if not gid:
                    continue
                if gid not in self.initial_lines:
                    self.initial_lines[gid] = []
                self.initial_lines[gid].append(r)

    def _load_elo_ratings(self):
        path = os.path.join(self.data_dir, "fivethirtyeight_elo_games.csv")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for r in reader:
                # Key by date + team1 + team2
                date = r.get("date", "")
                t1 = r.get("team1", "")
                t2 = r.get("team2", "")
                season = r.get("season", "")
                key = f"{season}_{date}_{t1}_{t2}"
                self.elo_by_game[key] = {
                    "elo1": float(r["elo1"]) if r.get("elo1") else None,
                    "elo2": float(r["elo2"]) if r.get("elo2") else None,
                    "elo_prob1": float(r["elo_prob1"]) if r.get("elo_prob1") else None,
                    "neutral": r.get("neutral") == "1",
                    "playoff": r.get("playoff") != "",
                }

    def _load_officials(self):
        path = os.path.join(self.data_dir, "officials.csv")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for r in reader:
                gid = r.get("game_id")
                if not gid:
                    continue
                if gid not in self.officials_by_game:
                    self.officials_by_game[gid] = []
                self.officials_by_game[gid].append(r)

    def _load_injuries(self):
        path = os.path.join(self.data_dir, "injury_report.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            try:
                self.injuries = json.load(f)
            except Exception as e:
                self.irregularities.append({
                    "type": "INJURY_PARSE_ERROR",
                    "detail": str(e),
                    "file": path
                })

    def _load_games(self):
        path = os.path.join(self.data_dir, "games.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing {path}")

        # Team standardizer mapping
        team_alias = {
            "OAK": "LV", "SD": "LAC", "STL": "LA", "WSH": "WAS"
        }

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for r in reader:
                gid = r.get("game_id", "")
                season = int(r.get("season", 0))
                week = int(r.get("week", 0))
                gameday = r.get("gameday", "")
                gametime = r.get("gametime", "")
                away_team = r.get("away_team", "")
                home_team = r.get("home_team", "")
                
                # Normalize team codes
                away_norm = team_alias.get(away_team, away_team)
                home_norm = team_alias.get(home_team, home_team)

                away_score = int(r["away_score"]) if r.get("away_score") and r["away_score"] != "" else None
                home_score = int(r["home_score"]) if r.get("home_score") and r["home_score"] != "" else None
                result = int(r["result"]) if r.get("result") and r["result"] != "" else (home_score - away_score if home_score is not None and away_score is not None else None)
                total = int(r["total"]) if r.get("total") and r["total"] != "" else (home_score + away_score if home_score is not None and away_score is not None else None)
                
                # Betting lines
                spread_line = float(r["spread_line"]) if r.get("spread_line") and r["spread_line"] != "" else None
                total_line = float(r["total_line"]) if r.get("total_line") and r["total_line"] != "" else None
                away_ml = float(r["away_moneyline"]) if r.get("away_moneyline") and r["away_moneyline"] != "" else None
                home_ml = float(r["home_moneyline"]) if r.get("home_moneyline") and r["home_moneyline"] != "" else None
                away_spread_odds = float(r["away_spread_odds"]) if r.get("away_spread_odds") and r["away_spread_odds"] != "" else -110.0
                home_spread_odds = float(r["home_spread_odds"]) if r.get("home_spread_odds") and r["home_spread_odds"] != "" else -110.0
                over_odds = float(r["over_odds"]) if r.get("over_odds") and r["over_odds"] != "" else -110.0
                under_odds = float(r["under_odds"]) if r.get("under_odds") and r["under_odds"] != "" else -110.0

                # Weather & Environment
                temp = float(r["temp"]) if r.get("temp") and r["temp"] != "" else None
                wind = float(r["wind"]) if r.get("wind") and r["wind"] != "" else (0.0 if r.get("roof") in ["dome", "closed"] else None)
                roof = r.get("roof", "outdoors")
                surface = r.get("surface", "grass")

                # Rest
                away_rest = int(r["away_rest"]) if r.get("away_rest") and r["away_rest"] != "" else 7
                home_rest = int(r["home_rest"]) if r.get("home_rest") and r["home_rest"] != "" else 7

                # Coaches, QBs, Refs
                away_qb = r.get("away_qb_name", "")
                home_qb = r.get("home_qb_name", "")
                away_coach = r.get("away_coach", "")
                home_coach = r.get("home_coach", "")
                referee = r.get("referee", "")

                # Opening lines lookup
                init_lines = self.initial_lines.get(gid, [])
                open_spread = None
                open_total = None
                for il in init_lines:
                    if il.get("type") == "SPREAD" and il.get("side") == home_team:
                        try:
                            open_spread = float(il["line"])
                        except:
                            pass
                    elif il.get("type") == "TOTAL" and il.get("side") == "Over":
                        try:
                            open_total = float(il["line"])
                        except:
                            pass

                # Elo lookup
                elo_key = f"{season}_{gameday}_{home_team}_{away_team}"
                elo_info = self.elo_by_game.get(elo_key, {})

                is_completed = home_score is not None and away_score is not None

                game_obj = {
                    "game_id": gid,
                    "season": season,
                    "week": week,
                    "game_type": r.get("game_type", "REG"),
                    "gameday": gameday,
                    "weekday": r.get("weekday", ""),
                    "gametime": gametime,
                    "away_team": away_norm,
                    "home_team": home_norm,
                    "away_score": away_score,
                    "home_score": home_score,
                    "result": result, # home - away
                    "total": total, # home + away
                    "completed": is_completed,
                    "spread_line": spread_line, # home spread (+ means home is underdog, - means home is favorite)
                    "total_line": total_line,
                    "away_moneyline": away_ml,
                    "home_moneyline": home_ml,
                    "away_spread_odds": away_spread_odds,
                    "home_spread_odds": home_spread_odds,
                    "over_odds": over_odds,
                    "under_odds": under_odds,
                    # Preserve whether each price was observed in the source. The
                    # numeric fields above retain legacy -110 fallbacks for older
                    # strategies, but evidence-gated research must require these.
                    "away_spread_odds_recorded": bool(r.get("away_spread_odds")),
                    "home_spread_odds_recorded": bool(r.get("home_spread_odds")),
                    "over_odds_recorded": bool(r.get("over_odds")),
                    "under_odds_recorded": bool(r.get("under_odds")),
                    "open_spread": open_spread,
                    "open_total": open_total,
                    "spread_move": (spread_line - open_spread) if (spread_line is not None and open_spread is not None) else 0.0,
                    "total_move": (total_line - open_total) if (total_line is not None and open_total is not None) else 0.0,
                    "temp": temp,
                    "wind": wind,
                    "roof": roof,
                    "surface": surface,
                    "is_dome": roof in ["dome", "closed"],
                    "away_rest": away_rest,
                    "home_rest": home_rest,
                    "rest_diff": home_rest - away_rest, # + means home has more rest
                    "div_game": r.get("div_game") == "1",
                    "away_qb": away_qb,
                    "home_qb": home_qb,
                    "away_coach": away_coach,
                    "home_coach": home_coach,
                    "referee": referee,
                    "stadium": r.get("stadium", ""),
                    "stadium_id": r.get("stadium_id", ""),
                    "elo_home": elo_info.get("elo1"),
                    "elo_away": elo_info.get("elo2"),
                    "elo_prob_home": elo_info.get("elo_prob1"),
                }

                self.games.append(game_obj)

        # Sort games chronologically
        self.games.sort(key=lambda g: (g["season"], g["week"], g["gameday"], g["gametime"]))
        return self.games
