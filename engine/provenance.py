"""Evidence and provenance helpers used by research exports.

A record is not historical evidence merely because it exists in JSON.  These
helpers make source snapshots, retrieval time, availability time, and derived
transformations explicit so callers can refuse unverifiable prices.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_snapshot(path: str | Path, *, source_id: str, retrieved_at: str | None = None,
                    available_through: str | None = None) -> dict[str, Any]:
    target = Path(path)
    return {
        "source_id": source_id,
        "path": str(target),
        "sha256": sha256_file(target),
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "available_through": available_through,
        "classification": "SOURCE_DATA",
    }


def observed_price(game: dict, market: str, side: str) -> float | None:
    """Return only a side-specific observed price; never substitute -110."""
    fields = {
        ("SPREAD", "home"): "home_spread_odds",
        ("SPREAD", "away"): "away_spread_odds",
        ("TOTAL", "over"): "over_odds",
        ("TOTAL", "under"): "under_odds",
        ("MONEYLINE", "home"): "home_moneyline",
        ("MONEYLINE", "away"): "away_moneyline",
    }
    field = fields.get((market, side))
    value = game.get(field) if field else None
    return float(value) if value is not None else None


def validate_point_in_time(decision_time: str, *, source_available_at: str | None) -> tuple[bool, str]:
    if not source_available_at:
        return False, "source availability timestamp missing"
    decision = datetime.fromisoformat(decision_time.replace("Z", "+00:00"))
    available = datetime.fromisoformat(source_available_at.replace("Z", "+00:00"))
    if available > decision:
        return False, "source was retrieved after decision time"
    return True, "ok"


def load_json(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)
