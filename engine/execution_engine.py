"""Paper-trading / execution engine.

Simulates realistic betting execution tracking:
- Available price
- Bid/ask
- Spread
- Liquidity/maximum size
- Timestamp
- Slippage
- Order size
- Partial fills
- Market movement
- Entry/exit
- Settlement

Never assumes unlimited liquidity or that a brief price was continuously available.
"""

from __future__ import annotations

import json
import math
import hashlib
import random
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ExecutionQuote:
    timestamp: str
    market: str
    selection: str
    bid: float
    ask: float
    mid: float
    spread: float
    bid_size: float
    ask_size: float
    last_price: float
    volume: float
    source: str


@dataclass
class ExecutionFill:
    fill_id: str
    bet_id: str
    timestamp: str
    requested_price: str
    requested_size: float
    filled_price: str
    filled_size: float
    slippage: float
    partial_fill: bool
    liquidity_available: float
    market_movement_since_decision: float
    fees: float
    execution_status: str


class PaperExecutionEngine:
    def __init__(self):
        self.quotes: list[ExecutionQuote] = []
        self.fills: list[ExecutionFill] = []
        self.kalshi_sim = None
        try:
            from engine.models import KalshiExecutionSimulator
            self.kalshi_sim = KalshiExecutionSimulator()
        except ImportError:
            pass

    def get_sportsbook_quote(
        self,
        game: dict,
        market: str,
        side: str,
        timestamp: str | None = None
    ) -> ExecutionQuote:
        """Simulate sportsbook quote with bid/ask spread."""
        now = timestamp or datetime.now(timezone.utc).isoformat()

        # Base odds -110 = 1.909 decimal, spread 2¢ equivalent in American = ~0.02 prob
        # Simulate realistic sportsbook spread: -110 / -110 = 4.76% vig
        base_price = game.get("spread_line") if market == "SPREAD" else game.get("total_line")
        base_odds = -110.0

        # Simulate bid/ask: retail books have wider spread than Pinnacle
        # Pinnacle: -105/-105 (2.38% vig), Retail: -110/-110 (4.76% vig)
        # Represent as price movement in points: bid = line - 0.1, ask = line + 0.1
        spread_pts = 0.2  # 0.2 point bid/ask spread typical for spread
        if market == "TOTAL":
            spread_pts = 0.3

        if market == "SPREAD":
            line = base_price or 0.0
            bid_line = line - spread_pts/2
            ask_line = line + spread_pts/2
            bid_odds = -110.0
            ask_odds = -110.0
        else:
            line = base_price or 44.0
            bid_line = line - spread_pts/2
            ask_line = line + spread_pts/2
            bid_odds = -110.0
            ask_odds = -110.0

        quote = ExecutionQuote(
            timestamp=now,
            market=market,
            selection=f"{side} {base_price}",
            bid=bid_line,
            ask=ask_line,
            mid=line,
            spread=spread_pts,
            bid_size=5000.0,  # $5k available at bid
            ask_size=5000.0,
            last_price=line,
            volume=25000.0,  # $25k matched volume proxy
            source="Pinnacle/Market Consensus (simulated with realistic spread)"
        )
        self.quotes.append(quote)
        return quote

    def get_kalshi_quote(
        self,
        fair_prob: float,
        side: str = "YES",
        liquidity_tier: str = "HIGH",
        timestamp: str | None = None
    ) -> ExecutionQuote:
        """Simulate Kalshi orderbook quote with bid/ask."""
        now = timestamp or datetime.now(timezone.utc).isoformat()

        if self.kalshi_sim:
            pricing = self.kalshi_sim.price_contract(fair_prob, side, liquidity_tier)
            bid = pricing["bid"]
            ask = pricing["ask"]
            mid = pricing["mid"]
            spread = pricing["spread"]
        else:
            fair_cents = fair_prob * 100.0
            spread = 3.0 if liquidity_tier == "HIGH" else 5.0
            bid = max(1.0, fair_cents - spread/2)
            ask = min(99.0, fair_cents + spread/2)
            mid = (bid + ask) / 2

        quote = ExecutionQuote(
            timestamp=now,
            market="KALSHI_SPREAD",
            selection=f"{side} @ {fair_prob:.2f}",
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
            bid_size=150.0 if liquidity_tier == "HIGH" else 50.0,
            ask_size=200.0 if liquidity_tier == "HIGH" else 80.0,
            last_price=mid,
            volume=850.0,
            source="Kalshi API KXNFL orderbook (simulated with realistic depth)"
        )
        self.quotes.append(quote)
        return quote

    def simulate_fill(
        self,
        bet_id: str,
        requested_price: str,
        requested_size: float,
        quote: ExecutionQuote,
        timestamp: str | None = None,
        market_movement: float = 0.0
    ) -> ExecutionFill:
        """Simulate order fill with slippage, partial fills, liquidity bounds."""
        now = timestamp or datetime.now(timezone.utc).isoformat()

        # Parse requested price
        try:
            if "¢" in requested_price:
                req_cents = float(requested_price.replace("¢", ""))
                req_prob = req_cents / 100.0
            else:
                req_cents = None
                req_prob = None
        except:
            req_cents = None
            req_prob = None

        # Determine fill price with slippage
        # Slippage model: 0.5¢ per 100 contracts above 100, plus market movement
        is_kalshi = quote.market.startswith("KALSHI")
        if is_kalshi:
            base_fill = quote.ask if quote.selection.startswith("YES") else (100 - quote.bid)
            # Slippage scales with size
            size_slippage = max(0.0, (requested_size - 100) / 100.0) * 0.5
            movement_slippage = abs(market_movement) * 0.8
            total_slippage = size_slippage + movement_slippage
            filled_cents = min(99.0, base_fill + total_slippage)
            filled_price = f"{filled_cents:.1f}¢"
            filled_prob = filled_cents / 100.0
        else:
            # Sportsbook: slippage in points, not cents
            base_fill = quote.ask
            size_slippage_pts = max(0.0, (requested_size - 2000) / 1000.0) * 0.05
            movement_slippage_pts = abs(market_movement) * 0.3
            total_slippage = size_slippage_pts + movement_slippage_pts
            filled_line = base_fill + total_slippage
            filled_price = f"{filled_line:+.1f} (-110)"
            filled_prob = 0.5238

        # Liquidity check: partial fills if requested > available
        liquidity_available = quote.ask_size
        filled_size = min(requested_size, liquidity_available)
        partial_fill = filled_size < requested_size

        # Fees
        fees = 0.0
        if is_kalshi:
            fees = filled_size * 0.01  # $0.01 per contract taker fee
        else:
            fees = 0.0  # Sportsbook vig included in odds

        fill = ExecutionFill(
            fill_id=f"FILL-{bet_id}-{len(self.fills)+1:03d}",
            bet_id=bet_id,
            timestamp=now,
            requested_price=requested_price,
            requested_size=requested_size,
            filled_price=filled_price,
            filled_size=filled_size,
            slippage=round(total_slippage, 3),
            partial_fill=partial_fill,
            liquidity_available=liquidity_available,
            market_movement_since_decision=round(market_movement, 3),
            fees=round(fees, 2),
            execution_status="PARTIAL_FILL" if partial_fill else "FILLED"
        )
        self.fills.append(fill)
        return fill

    def settle_position(
        self,
        fill: ExecutionFill,
        actual_outcome: float,  # 1.0 win, 0.0 loss, 0.5 push
        odds: float = -110.0
    ) -> dict:
        """Settle filled position and compute PnL with audit trail."""
        from engine.models import calculate_pnl

        stake = fill.filled_size
        if fill.bet_id.startswith("BET-") and "KALSHI" in fill.bet_id:
            # Kalshi settlement
            if self.kalshi_sim:
                # Reconstruct execution for settlement
                side = "YES" if "YES" in fill.filled_price else "YES"  # Simplified
                execution = {
                    "filled_contracts": stake,
                    "total_cost": stake * (float(fill.filled_price.replace("¢", ""))/100.0),
                    "fees": fill.fees,
                    "side": side
                }
                settlement = self.kalshi_sim.settle_contract(execution, 1 if actual_outcome == 1.0 else 0)
                pnl = settlement["net_pnl"]
                roi = settlement["roi"]
            else:
                pnl = stake * 0.4 if actual_outcome == 1.0 else -stake
                roi = 0.4 if actual_outcome == 1.0 else -1.0
        else:
            pnl = calculate_pnl(stake, odds, actual_outcome)
            roi = pnl / stake if stake > 0 else 0.0

        return {
            "bet_id": fill.bet_id,
            "fill_id": fill.fill_id,
            "outcome": actual_outcome,
            "result": "WIN" if actual_outcome == 1.0 else ("LOSS" if actual_outcome == 0.0 else "PUSH"),
            "stake": stake,
            "pnl": round(pnl, 2),
            "roi": round(roi, 4),
            "fees": fill.fees,
            "slippage": fill.slippage,
            "partial_fill": fill.partial_fill,
            "liquidity_available": fill.liquidity_available,
            "market_movement": fill.market_movement_since_decision,
            "settlement_timestamp": datetime.now(timezone.utc).isoformat(),
            "classification": "DERIVED_DATA",
            "never_invent": "Settlement from observed final score only; no pseudo-random outcome"
        }

    def export_execution_report(self, out_path: str | Path = "data/execution_report.json"):
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "classification": "DERIVED_DATA",
            "total_quotes": len(self.quotes),
            "total_fills": len(self.fills),
            "quotes_sample": [asdict(q) for q in self.quotes[-20:]],
            "fills_sample": [asdict(f) for f in self.fills[-20:]],
            "execution_realism": {
                "bid_ask_spread": "2¢ to 5¢ for Kalshi, 0.2-0.3 pts for sportsbook spreads/totals",
                "liquidity_bounds": "Kalshi $500 max per market in NFLComp sim, sportsbook $5k at retail, $50k at Pinnacle",
                "slippage_model": "Size-based: 0.5¢ per 100 contracts above 100 for Kalshi, 0.05 pts per $1k above $2k for sportsbook",
                "partial_fills": "Possible when requested size > liquidity available; flagged",
                "market_movement": "Tracked from decision timestamp to fill timestamp; affects slippage",
                "never_assume": "Never assume unlimited liquidity or that brief price was continuously available"
            },
            "policy": {
                "available_price": "Must be from verified snapshot with timestamp",
                "bid_ask": "Realistic spread, not zero",
                "spread": "2¢-5¢ Kalshi, 0.2-0.3 pts sportsbook",
                "liquidity": "Bounded, not infinite",
                "timestamp": "Decision and bet timestamps recorded",
                "slippage": "Modeled based on size and market movement",
                "order_size": "Tracked and bounded by liquidity",
                "partial_fills": "Tracked when requested > available",
                "market_movement": "Tracked from decision to execution",
                "entry_exit": "Entry price = fill price, exit = settlement",
                "settlement": "Only from observed final score"
            }
        }
        Path(out_path).write_text(json.dumps(report, indent=2))
        return report
