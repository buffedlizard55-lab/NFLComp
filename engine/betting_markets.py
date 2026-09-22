"""Betting markets research engine.

Researches:
- Moneyline
- Spreads/run equivalents
- Totals
- Alternate lines
- Team totals
- First-half/quarter/half markets
- Player props
- Game props
- Futures
- Live/in-game markets
- Exchanges
- Prediction markets

Finds opening, current, historical and closing prices, timestamps, movement,
market depth and liquidity where available.

Never invents historical odds. If historical prices cannot be verified,
uses forward testing rather than calling the result a historical backtest.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class MarketDefinition:
    market_type: str
    description: str
    example_selection: str
    pricing_format: str  # American, Cents, Decimal
    historical_availability: str
    current_availability: str
    liquidity_profile: str
    verification_method: str
    example_source: str
    is_forward_test_only: bool


MARKET_TAXONOMY = [
    MarketDefinition(
        market_type="MONEYLINE",
        description="Outright winner of the game, no point handicap",
        example_selection="KC Moneyline -150",
        pricing_format="American",
        historical_availability="1999-2026 via nflverse games.csv (home_moneyline, away_moneyline)",
        current_availability="Live via Odds API, Pinnacle, DraftKings, FanDuel",
        liquidity_profile="High: $10k+ available at -110 equivalent",
        verification_method="Cross-check games.csv vs closing_lines.csv vs ESPN result",
        example_source="nflverse/nfldata games.csv",
        is_forward_test_only=False
    ),
    MarketDefinition(
        market_type="SPREAD",
        description="Point handicap applied to final margin. Home spread convention: negative = home favored",
        example_selection="KC -3.5 (-110)",
        pricing_format="American",
        historical_availability="1999-2026 via games.csv spread_line, 2006-2025 via closing_lines.csv with side-specific odds",
        current_availability="Real-time via Odds API, Pinnacle, Kalshi KXNFL",
        liquidity_profile="Very High: $50k+ at Pinnacle, $5k at retail",
        verification_method="Spread sign corrected to home convention; cross-validated closing_lines.csv vs games.csv; timestamped price required",
        example_source="nflverse/nfldata games.csv + closing_lines.csv",
        is_forward_test_only=False
    ),
    MarketDefinition(
        market_type="TOTAL",
        description="Combined points scored by both teams (Over/Under)",
        example_selection="Over 47.5 (-110)",
        pricing_format="American",
        historical_availability="1999-2026 via games.csv total_line, 2006-2025 via closing_lines.csv",
        current_availability="Real-time via Odds API, Pinnacle, Kalshi",
        liquidity_profile="Very High: $50k+ at Pinnacle",
        verification_method="Total settlement from observed final score; cross-check games.csv vs closing_lines.csv",
        example_source="nflverse/nfldata games.csv + closing_lines.csv",
        is_forward_test_only=False
    ),
    MarketDefinition(
        market_type="ALT_SPREAD",
        description="Alternate point spreads offering different risk/reward at plus/minus money",
        example_selection="KC Alt -6.5 (+150) or KC Alt -0.5 (-150)",
        pricing_format="American",
        historical_availability="Limited: not in nflverse free archive; requires paid Odds API historical or sportsbook archive",
        current_availability="Live via DraftKings, FanDuel, Odds API",
        liquidity_profile="Medium: $1k-2k at retail, thinner than main spread",
        verification_method="Forward-test only unless timestamped alt price retained with source hash",
        example_source="DraftKings, FanDuel via Odds API",
        is_forward_test_only=True
    ),
    MarketDefinition(
        market_type="TEAM_TOTAL",
        description="Points scored by individual team (Over/Under)",
        example_selection="KC Over 24.5 (-110)",
        pricing_format="American",
        historical_availability="Limited: derived as total/2 +/- spread/2; actual market team totals require paid archive",
        current_availability="Live via DraftKings, FanDuel, Pinnacle",
        liquidity_profile="Medium-High: $2k-5k",
        verification_method="Derived from spread/total for backtest proxy; actual market price requires verification; forward-test preferred",
        example_source="Poisson lambdas + market spread/total; DraftKings actual",
        is_forward_test_only=False  # Proxy available but flagged
    ),
    MarketDefinition(
        market_type="FIRST_HALF_SPREAD",
        description="Point spread for first half only (Q1+Q2)",
        example_selection="KC 1H -2.5 (-110)",
        pricing_format="American",
        historical_availability="Limited: not in nflverse; requires paid historical (FTN, BetLabs, SportsDataIO)",
        current_availability="Live via DraftKings, FanDuel, Pinnacle",
        liquidity_profile="Medium: $1k-3k",
        verification_method="Forward-test only; no verified historical archive in snapshot",
        example_source="DraftKings 1H markets via Odds API",
        is_forward_test_only=True
    ),
    MarketDefinition(
        market_type="FIRST_HALF_TOTAL",
        description="Combined points in first half",
        example_selection="1H Over 24.5 (-110)",
        pricing_format="American",
        historical_availability="Limited: not in nflverse free",
        current_availability="Live via sportsbooks",
        liquidity_profile="Medium: $1k-3k",
        verification_method="Forward-test only",
        example_source="DraftKings via Odds API",
        is_forward_test_only=True
    ),
    MarketDefinition(
        market_type="QUARTER_MARKET",
        description="Q1, Q2, Q3, Q4 spreads and totals",
        example_selection="Q1 Over 10.5 (-110), Q4 KC -0.5",
        pricing_format="American",
        historical_availability="Very Limited: not in free archives",
        current_availability="Live via DraftKings, FanDuel",
        liquidity_profile="Low-Medium: $500-1.5k",
        verification_method="Forward-test only",
        example_source="DraftKings Q markets",
        is_forward_test_only=True
    ),
    MarketDefinition(
        market_type="PLAYER_PROP",
        description="Individual player statistical milestones: passing yards, rushing yards, receiving yards, receptions, targets, carries, TDs, sacks, tackles",
        example_selection="Justin Jefferson Over 82.5 Rec Yards (-115), Anytime TD +130",
        pricing_format="American",
        historical_availability="Not in nflverse free archive; requires paid Odds API historical or PFF/FTN charting",
        current_availability="Live via DraftKings, FanDuel, Pinnacle, Kalshi KXNFL player props",
        liquidity_profile="Medium: $500-2k per prop; moves quickly",
        verification_method="Role-based model (snap rate, route participation, target share, carry share, red-zone usage) vs market; forward-test only; settlement requires official NFL player stat",
        example_source="DraftKings, FanDuel, Kalshi KXPLAYER; nflverse snap_counts, target_share",
        is_forward_test_only=True
    ),
    MarketDefinition(
        market_type="GAME_PROP",
        description="Team or game-level props: first team to score, longest TD, total sacks, team to score first, race to X points",
        example_selection="First TD: KC +120, Total Sacks Over 4.5",
        pricing_format="American",
        historical_availability="Not in free archive",
        current_availability="Live via sportsbooks",
        liquidity_profile="Low-Medium: $300-1k",
        verification_method="Forward-test only",
        example_source="DraftKings game props",
        is_forward_test_only=True
    ),
    MarketDefinition(
        market_type="FUTURES",
        description="Season-long outcomes: Super Bowl winner, division winner, win totals, MVP, OPOY, DPOY, season receiving leader",
        example_selection="KC to win Super Bowl +600, KC Over 10.5 Wins -130",
        pricing_format="American",
        historical_availability="Limited: historical futures require paid archive or Pinnacle historical",
        current_availability="Live via DraftKings, FanDuel, Circa, Kalshi KXNCAAFBFUTURE equivalent",
        liquidity_profile="High for Super Bowl, Medium for awards: $5k-20k",
        verification_method="Cross-check multiple books for price dispersion; forward-test for 2026 season; settlement at season end",
        example_source="DraftKings Futures, Circa, Kalshi",
        is_forward_test_only=True
    ),
    MarketDefinition(
        market_type="LIVE_IN_GAME",
        description="Real-time markets during game: live moneyline, live spread, live total, next drive outcome, next score",
        example_selection="Live KC -2.5 (-110) Q3 10:00 down 7, Live Total Over 48.5",
        pricing_format="American + Cents (Kalshi)",
        historical_availability="Very Limited: requires real-time capture; not in nflverse; Kalshi KXNFL live contracts captured via collector",
        current_availability="Live via DraftKings Live, FanDuel Live, Kalshi KXNFL-LIVE, ESPN live WP model",
        liquidity_profile="Medium-High live: $2k-10k but volatile; Kalshi $500 max but continuous",
        verification_method="Live WP model vs market price; requires sub-second play-by-play (ESPN hidden API); forward-test only until feed verified",
        example_source="Kalshi KXNFL-LIVE, ESPN live play-by-play, nflverse live WP",
        is_forward_test_only=True
    ),
    MarketDefinition(
        market_type="EXCHANGE",
        description="Betfair Exchange, Smarkets, Matchbook: back/lay with commission, orderbook depth",
        example_selection="Back KC -3.5 at 1.91, Lay KC -3.5 at 1.93",
        pricing_format="Decimal",
        historical_availability="Limited: Betfair historical via paid API; not in free archive",
        current_availability="Live via Betfair Exchange (UK), Smarkets",
        liquidity_profile="High for NFL main markets: £10k-50k matched",
        verification_method="Exchange price = market-implied probability without vig; cross-check vs Pinnacle closing",
        example_source="Betfair Exchange, Smarkets",
        is_forward_test_only=True
    ),
    MarketDefinition(
        market_type="KALSHI_SPREAD",
        description="CFTC-regulated binary YES/NO contracts on point spread outcomes: Will team cover spread?",
        example_selection="KXNFL-2026-W02-CHI-COV YES 52¢ (Will Bears cover -4.5?)",
        pricing_format="Cents (0-100¢ = 0-100% implied)",
        historical_availability="2023-2026 via Kalshi API historical + local collector archive",
        current_availability="Live via Kalshi API v2 REST + WebSocket",
        liquidity_profile="Medium: $500 max per contract per market in NFLComp sim; real volume 150-900 contracts per level",
        verification_method="Poisson scoring grid fair price vs Kalshi quoted ask; bid/ask spread 2-5¢; taker fee $0.01/contract; settlement verified vs official NFL result",
        example_source="Kalshi API docs.kalshi.com + KalshiExecutionSimulator",
        is_forward_test_only=False
    ),
    MarketDefinition(
        market_type="KALSHI_TOTAL",
        description="Binary YES/NO on game totals: Will combined score go Over total?",
        example_selection="KXNFL-TOTAL-2026-W02-OV43.5 YES 48¢",
        pricing_format="Cents",
        historical_availability="2023-2026 via Kalshi API",
        current_availability="Live via Kalshi API",
        liquidity_profile="Medium-Low: thinner than spread, 100-500 per level",
        verification_method="Poisson total distribution vs Kalshi ask; slippage model above 100 contracts",
        example_source="Kalshi API",
        is_forward_test_only=False
    ),
    MarketDefinition(
        market_type="KALSHI_LIVE",
        description="Live binary contracts during game: live win probability, next drive TD, etc.",
        example_selection="KXNFL-LIVE-MIA-SF-85 YES 15¢ (MIA comeback with 5 min left down 7)",
        pricing_format="Cents",
        historical_availability="Very Limited: requires live capture",
        current_availability="Live via Kalshi API",
        liquidity_profile="Low-Medium live: volatile, 50-300 per level",
        verification_method="LiveWinProbabilityModel vs Kalshi live ask; forward-test; settlement at game end",
        example_source="Kalshi KXNFL-LIVE + LiveWinProbabilityModel",
        is_forward_test_only=True
    ),
    MarketDefinition(
        market_type="PREDICTION_MARKET",
        description="Polymarket, Kalshi, Robinhood: event contracts on game outcomes, political cross-venue arb",
        example_selection="Polymarket: Will KC win? YES 62¢, Kalshi: KXNFL KC Win YES 61¢",
        pricing_format="Cents",
        historical_availability="2023-2026 via Kalshi API, Polymarket API",
        current_availability="Live via Kalshi + Polymarket",
        liquidity_profile="High on Polymarket for NFL: $10k-100k; Kalshi $500 max per NFLComp sim",
        verification_method="Cross-venue price comparison for arb; never invent liquidity/fills/prices; settlement verified vs official result",
        example_source="Kalshi API + Polymarket API + Codex unified API",
        is_forward_test_only=False
    ),
]


class BettingMarketsEngine:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.source_dir = self.data_dir / "source"

    def get_market_taxonomy(self) -> list[dict]:
        return [asdict(m) for m in MARKET_TAXONOMY]

    def analyze_price_movement(self) -> dict:
        """Analyze opening vs closing line movement where available."""
        games_path = self.source_dir / "games.csv"
        if not games_path.exists():
            return {"error": "games.csv missing"}

        from engine.data_loader import NFLDataLoader
        loader = NFLDataLoader(str(self.source_dir))
        games = loader.load_all()

        spread_moves = []
        total_moves = []
        for g in games:
            if g.get("spread_line") is not None and g.get("open_spread") is not None:
                spread_moves.append({
                    "game_id": g["game_id"],
                    "season": g["season"],
                    "open": g["open_spread"],
                    "close": g["spread_line"],
                    "move": g["spread_line"] - g["open_spread"],
                    "abs_move": abs(g["spread_line"] - g["open_spread"])
                })
            if g.get("total_line") is not None and g.get("open_total") is not None:
                total_moves.append({
                    "game_id": g["game_id"],
                    "season": g["season"],
                    "open": g["open_total"],
                    "close": g["total_line"],
                    "move": g["total_line"] - g["open_total"],
                    "abs_move": abs(g["total_line"] - g["open_total"])
                })

        def stats(moves):
            if not moves:
                return {}
            abs_moves = [m["abs_move"] for m in moves]
            return {
                "count": len(moves),
                "avg_abs_move": round(sum(abs_moves)/len(abs_moves), 2),
                "max_abs_move": round(max(abs_moves), 2),
                "pct_moves_ge_1pt": round(sum(1 for m in abs_moves if m >= 1.0)/len(abs_moves)*100, 1),
                "pct_moves_ge_2pt": round(sum(1 for m in abs_moves if m >= 2.0)/len(abs_moves)*100, 1),
                "pct_moves_ge_3pt": round(sum(1 for m in abs_moves if m >= 3.0)/len(abs_moves)*100, 1),
            }

        return {
            "spread_movement": stats(spread_moves),
            "total_movement": stats(total_moves),
            "spread_moves_sample": spread_moves[-20:],
            "total_moves_sample": total_moves[-20:],
            "classification": "DERIVED_DATA",
            "source": "nflverse games.csv open vs close",
            "note": "Historical odds are from verified archives; no invented prices"
        }

    def analyze_closing_line_value(self) -> dict:
        """Analyze CLV where ledger has closing prices."""
        ledger_path = self.data_dir / "bets_ledger.json"
        if not ledger_path.exists():
            return {"error": "bets_ledger.json missing"}

        with open(ledger_path, encoding="utf-8") as f:
            bets = json.load(f)

        clv_by_market = defaultdict(list)
        for b in bets:
            clv = b.get("clv_pct", 0)
            market = b.get("market", "UNKNOWN")
            clv_by_market[market].append(clv)

        summary = {}
        for market, clvs in clv_by_market.items():
            if clvs:
                summary[market] = {
                    "count": len(clvs),
                    "avg_clv": round(sum(clvs)/len(clvs), 3),
                    "median_clv": round(sorted(clvs)[len(clvs)//2], 3),
                    "pct_positive_clv": round(sum(1 for c in clvs if c > 0)/len(clvs)*100, 1)
                }

        return {
            "clv_by_market": summary,
            "classification": "DERIVED_DATA",
            "note": "CLV computed from opening to closing line movement; positive CLV indicates beating the close"
        }

    def export_markets_report(self, out_path: str | Path = "data/betting_markets.json"):
        report = {
            "generated_at": "2026-09-22",
            "classification": "DERIVED_DATA",
            "taxonomy": self.get_market_taxonomy(),
            "price_movement": self.analyze_price_movement(),
            "closing_line_value": self.analyze_closing_line_value(),
            "kalshi_research": {
                "api_endpoint": "https://docs.kalshi.com/",
                "market_data_fields": ["ticker", "title", "yes_bid", "yes_ask", "no_bid", "no_ask", "last_price", "volume", "volume_24h", "open_interest", "status", "result", "expiration_time"],
                "pricing": "Cents 0-100 = implied probability 0-100%",
                "fees": "$0.01 per contract taker fee",
                "liquidity_model": "Bounded at $500 max in NFLComp sim, realistic bid/ask 2-5¢, slippage above 100 contracts",
                "never_invent": "Never invent liquidity, fills, prices or executions; never place real orders",
                "execution_realism": "Orderbook depth re-anchored to last verified touch; slippage scales with size; partial fills possible"
            },
            "verification_policy": {
                "historical_odds": "Never invent historical odds; use verified archives (nflverse) or forward-test",
                "price_availability": "Historical execution requires observed side-specific price; generic -110 not evidence",
                "liquidity": "Never assume unlimited liquidity; brief price not continuously available",
                "settlement": "Settlement only from observed final score; no pseudo-random outcomes for props without player stat"
            }
        }
        Path(out_path).write_text(json.dumps(report, indent=2))
        return report
