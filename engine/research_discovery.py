"""Data-driven strategy hypothesis discovery.

This module creates *research candidates*, not bets or performance claims. It
only emits a candidate when the required fields exist in the supplied source
snapshot and records which fields are missing. Candidates must pass the normal
point-in-time and market-price gates before becoming a strategy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable


TEMPLATES = (
    ("REST_TOTAL_INTERACTION", "Rest and outdoor conditions jointly change scoring environment", ("away_rest", "home_rest", "total_line", "roof"), "TOTAL"),
    ("OPEN_CLOSE_DRIFT", "Opening-to-closing movement may identify stale prices", ("spread_line", "total_line"), "SPREAD"),
    ("ELO_MARKET_DISAGREEMENT", "Pre-game rating disagreement may predict spread outcomes", ("spread_line", "elo_prob_home"), "SPREAD"),
    ("WEATHER_TOTAL", "Wind and temperature may affect totals when observed before decision time", ("wind", "temp", "total_line", "roof"), "TOTAL"),
)


def discover_candidates(rows: Iterable[dict], *, source_id: str, retrieved_at: str | None = None) -> list[dict]:
    rows = list(rows)
    fields = {key for row in rows for key, value in row.items() if value not in (None, "")}
    now = retrieved_at or datetime.now(timezone.utc).isoformat()
    candidates = []
    for candidate_id, hypothesis, required, market in TEMPLATES:
        missing = [field for field in required if field not in fields]
        candidates.append({
            "candidate_id": candidate_id,
            "version": "v1",
            "hypothesis": hypothesis,
            "market": market,
            "required_fields": list(required),
            "available_fields": sorted(set(required) - set(missing)),
            "missing_fields": missing,
            "source_id": source_id,
            "sample_rows": len(rows),
            "status": "READY_FOR_TEST" if not missing and rows else "BLOCKED_MISSING_DATA",
            "research_class": "HYPOTHESIS",
            "discovered_at": now,
            "performance_claim": None,
        })
    return candidates


def compare_versions(parent: dict, child: dict) -> dict:
    """Return an auditable comparison descriptor; never infer that child improved."""
    return {
        "parent_candidate": parent.get("candidate_id"),
        "child_candidate": child.get("candidate_id"),
        "comparison_status": "REQUIRES_OUT_OF_SAMPLE_TEST",
        "improvement_claim": None,
        "comparison_fields": sorted(set(parent.get("required_fields", [])) | set(child.get("required_fields", []))),
    }
