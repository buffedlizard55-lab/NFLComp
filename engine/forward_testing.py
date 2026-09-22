"""Forward testing engine.

When reliable historical data does not exist, create a forward-testing strategy
instead of inventing history.

Records:
- Strategy/version
- Date/game/week
- Market/selection
- Decision timestamp
- Information available at that time
- Model probability/fair price
- Actual market price
- Simulated stake
- Result/PnL

Clearly distinguishes BACKTEST, FORWARD TEST, and PAPER TRADE.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ForwardTestRecord:
    record_id: str
    strategy_id: str
    strategy_version: str
    classification: str  # FORWARD_TEST, PAPER_TRADE
    season: int
    week: int
    game_id: str
    market: str
    selection: str
    decision_timestamp: str
    bet_timestamp: str | None
    information_available: dict
    model_probability: float
    fair_price: str
    actual_market_price: str
    market_source: str
    simulated_stake: float
    liquidity_available: float
    bid: float | None
    ask: float | None
    spread: float | None
    slippage: float | None
    status: str  # WATCHING, QUALIFIED, READY, PRICE_TOO_HIGH, WAITING, EXECUTED, CANCELLED, EXPIRED
    result: str | None
    pnl: float | None
    roi: float | None
    closing_price: str | None
    source_url: str
    verification_status: str
    notes: str


class ForwardTestingEngine:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.records: list[ForwardTestRecord] = []

    def create_forward_test_signal(
        self,
        strategy_id: str,
        version: str,
        game: dict,
        market: str,
        selection: str,
        model_prob: float,
        market_price: str,
        stake: float,
        supporting_data: dict,
        market_source: str,
        status: str = "WATCHING"
    ) -> ForwardTestRecord:
        now = datetime.now(timezone.utc).isoformat()
        record_id = f"FT-{game.get('season')}-W{game.get('week'):02d}-{strategy_id}-{len(self.records)+1:05d}"

        # Information available at decision time - point-in-time only
        info_available = {
            "rolling_metrics_available": "Only games < decision_timestamp",
            "injury_report": "Friday 4PM ET status only, no future injuries",
            "weather_forecast": "Pre-game forecast, not post-game observation",
            "market_prices": "Opening to current, no future closing prices",
            "results": "No future statistics/results",
            "supporting_data": supporting_data,
            "classification": "FORWARD_TEST",
            "warning": "This is a prospective test, not a historical backtest"
        }

        record = ForwardTestRecord(
            record_id=record_id,
            strategy_id=strategy_id,
            strategy_version=version,
            classification="FORWARD_TEST" if market in ["PLAYER_PROP", "ALT_SPREAD", "KALSHI_LIVE", "FIRST_HALF_SPREAD"] else "PAPER_TRADE",
            season=game.get("season", 2026),
            week=game.get("week", 2),
            game_id=game.get("game_id", "UNKNOWN"),
            market=market,
            selection=selection,
            decision_timestamp=now,
            bet_timestamp=None,
            information_available=info_available,
            model_probability=model_prob,
            fair_price=f"{model_prob*100:.1f}¢" if market.startswith("KALSHI") else f"{model_prob:.3f}",
            actual_market_price=market_price,
            market_source=market_source,
            simulated_stake=stake,
            liquidity_available=500.0 if market.startswith("KALSHI") else 5000.0,
            bid=None,
            ask=None,
            spread=None,
            slippage=None,
            status=status,
            result=None,
            pnl=None,
            roi=None,
            closing_price=None,
            source_url="https://github.com/nflverse/nfldata" if not market.startswith("KALSHI") else "https://docs.kalshi.com/",
            verification_status="FORWARD_TEST_PENDING",
            notes=f"Market {market} classified as { 'FORWARD_TEST' if market in ['PLAYER_PROP', 'ALT_SPREAD', 'KALSHI_LIVE'] else 'PAPER_TRADE'} because historical price archive unavailable; never invent history"
        )
        self.records.append(record)
        return record

    def update_status(
        self,
        record_id: str,
        new_status: str,
        reason: str = ""
    ):
        """Update status with audit trail - never silently modify."""
        for r in self.records:
            if r.record_id == record_id:
                old_status = r.status
                r.status = new_status
                r.notes += f" | Status {old_status}->{new_status}: {reason} at {datetime.now(timezone.utc).isoformat()}"
                return r
        return None

    def settle_forward_test(
        self,
        record_id: str,
        actual_result: str,
        pnl: float,
        closing_price: str
    ):
        for r in self.records:
            if r.record_id == record_id:
                r.result = actual_result
                r.pnl = pnl
                r.closing_price = closing_price
                r.verification_status = "SETTLED_FROM_OBSERVED_RESULT"
                return r
        return None

    def get_records_by_status(self, status: str) -> list[dict]:
        return [asdict(r) for r in self.records if r.status == status]

    def get_records_by_market(self, market: str) -> list[dict]:
        return [asdict(r) for r in self.records if r.market == market]

    def export_report(self, out_path: str | Path = "data/forward_testing.json"):
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "classification": "DERIVED_DATA",
            "total_records": len(self.records),
            "by_status": {
                status: len([r for r in self.records if r.status == status])
                for status in ["WATCHING", "QUALIFIED", "READY", "PRICE_TOO_HIGH", "WAITING", "EXECUTED", "CANCELLED", "EXPIRED"]
            },
            "by_market": {
                market: len([r for r in self.records if r.market == market])
                for market in set(r.market for r in self.records)
            },
            "by_classification": {
                "BACKTEST": 0,  # This engine only does forward test
                "FORWARD_TEST": len([r for r in self.records if r.classification == "FORWARD_TEST"]),
                "PAPER_TRADE": len([r for r in self.records if r.classification == "PAPER_TRADE"])
            },
            "records": [asdict(r) for r in self.records],
            "policy": {
                "never_invent_history": "If historical prices cannot be verified, use forward testing rather than calling the result a historical backtest",
                "record_fields": ["Strategy/version", "Date/game/week", "Market/selection", "Decision timestamp", "Information available", "Model probability/fair price", "Actual market price", "Simulated stake", "Result/PnL"],
                "distinction": "Clearly distinguish BACKTEST, FORWARD_TEST, and PAPER_TRADE",
                "statuses": ["WATCHING", "QUALIFIED", "READY", "PRICE_TOO_HIGH", "WAITING", "EXECUTED", "CANCELLED", "EXPIRED"]
            }
        }
        Path(out_path).write_text(json.dumps(report, indent=2))
        return report
