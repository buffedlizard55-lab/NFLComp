"""Canonical published numbers for NFLComp.

Every count, total and window that the README or the GitHub Pages site states
in prose is derived here from the checked-in data files, in one place.  The
site, the README block and the audit all read from this module, so a claim that
no longer matches the data is a failing check instead of a stale sentence.

Nothing in this module invents a value: a missing file yields ``None`` and the
renderer prints ``n/a`` rather than a guess.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

STATUS_START = "<!-- CURRENT_STATE_START -->"
STATUS_END = "<!-- CURRENT_STATE_END -->"

BADGES_START = "<!-- BADGES_START -->"
BADGES_END = "<!-- BADGES_END -->"

VERIFICATION_START = "<!-- VERIFICATION_START -->"
VERIFICATION_END = "<!-- VERIFICATION_END -->"

BLOCK_HEADING = "### Published state (generated — do not edit by hand)"


def _read(path: Path, default=None):
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def published_facts(data_dir: str | Path) -> dict:
    """Return every number the public claims depend on, keyed by a stable name."""
    root = Path(data_dir)
    summary = _read(root / "summary.json", {}) or {}
    ledger = _read(root / "bets_ledger.json", []) or []
    manifest = _read(root / "ledger_manifest.json", {}) or {}
    leaderboard = _read(root / "leaderboard.json", []) or []
    upcoming = _read(root / "upcoming_bets.json", []) or []
    kalshi = _read(root / "kalshi_trades.json", []) or []
    registry = _read(root / "registry.json", []) or []
    checks = _read(root / "audit_checks.json", []) or []
    experiments = _read(root / "research_experiments.json", []) or []
    strategies = _read(root / "strategies.json", []) or []

    published_pnl = sum(b.get("pnl", 0.0) or 0.0 for b in ledger)
    top = leaderboard[0] if leaderboard else {}
    decoded = [c for c in checks if c.get("passed")]
    return {
        "as_of_date": summary.get("as_of_date"),
        "current_season": summary.get("current_season"),
        "current_week": summary.get("current_week"),
        "games_tracked": summary.get("total_games_tracked"),
        "games_completed": summary.get("completed_games"),
        "games_upcoming": summary.get("upcoming_games"),
        "strategies": summary.get("total_strategies"),
        "strategy_versions": len(strategies) or None,
        "strategy_categories": len({s.get("category") for s in strategies if s.get("category")}) or None,
        "strategies_with_lineage": len([s for s in strategies if s.get("parent_version")]) or None,
        "all_time_bets": summary.get("total_simulated_bets"),
        "all_time_pnl": summary.get("total_simulated_pnl"),
        "published_bets": len(ledger) or None,
        "published_pnl": round(published_pnl, 2) if ledger else None,
        "published_window": manifest.get("published_window"),
        "upcoming_signals": len(upcoming) or None,
        "kalshi_trades": summary.get("total_kalshi_trades") or (len(kalshi) or None),
        "kalshi_published": len(kalshi) or None,
        "registry_sources": len(registry) or None,
        "verified_primary_sources": len([r for r in registry if r.get("status") == "VERIFIED_PRIMARY"]) or None,
        "audit_checks_passed": len(decoded) if checks else None,
        "audit_checks_total": len(checks) or None,
        "research_experiments": len(experiments) or None,
        "top_strategy": top.get("username"),
        "top_pnl": top.get("total_pnl"),
        "top_roi": top.get("roi"),
        "top_bets": top.get("total_bets"),
    }


def _money(value) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.2f}"


def _count(value) -> str:
    if value is None:
        return "n/a"
    return f"{value:,}"


def _window(value) -> str:
    if not value:
        return "n/a"
    return f"{value.get('from_season')}–{value.get('to_season')}"


def render_metric_lines(facts: dict) -> list[tuple[str, str]]:
    """The (metric, rendered value) pairs shared by the README block and the audit."""
    return [
        ("as_of_date", str(facts["as_of_date"]) if facts["as_of_date"] else "n/a"),
        ("current_season_week", f"{facts['current_season']} W{facts['current_week']}"
         if facts["current_season"] else "n/a"),
        ("games_tracked", _count(facts["games_tracked"])),
        ("games_completed", _count(facts["games_completed"])),
        ("games_upcoming", _count(facts["games_upcoming"])),
        ("strategy_personas", _count(facts["strategies"])),
        ("strategy_versions_catalogued", _count(facts["strategy_versions"])),
        ("strategy_categories", _count(facts["strategy_categories"])),
        ("strategies_with_lineage", _count(facts["strategies_with_lineage"])),
        ("all_time_simulated_bets", _count(facts["all_time_bets"])),
        ("all_time_simulated_pnl_usd", _money(facts["all_time_pnl"])),
        ("published_ledger_bets", _count(facts["published_bets"])),
        ("published_ledger_window", _window(facts["published_window"])),
        ("published_ledger_pnl_usd", _money(facts["published_pnl"])),
        ("upcoming_signals", _count(facts["upcoming_signals"])),
        ("kalshi_trades_all_time", _count(facts["kalshi_trades"])),
        ("kalshi_trades_published", _count(facts["kalshi_published"])),
        ("registry_sources", _count(facts["registry_sources"])),
        ("verified_primary_sources", _count(facts["verified_primary_sources"])),
        ("research_experiments", _count(facts["research_experiments"])),
        ("audit_checks_passed", f"{facts['audit_checks_passed']}/{facts['audit_checks_total']}"
         if facts["audit_checks_total"] else "n/a"),
        ("top_strategy", str(facts["top_strategy"]) if facts["top_strategy"] else "n/a"),
        ("top_strategy_pnl_usd", _money(facts["top_pnl"])),
        ("top_strategy_roi_pct", f"{facts['top_roi']:.2f}%" if facts["top_roi"] is not None else "n/a"),
        ("top_strategy_bets", _count(facts["top_bets"])),
    ]


def render_status_block(facts: dict) -> str:
    """Render the README status block from facts (idempotent)."""
    lines = [STATUS_START, BLOCK_HEADING, "", "| metric | value |", "| --- | --- |"]
    for metric, value in render_metric_lines(facts):
        lines.append(f"| {metric} | {value} |")
    lines.append("")
    lines.append("_Generated by `python3 scripts/render_readme.py` from the files in `data/`._")
    lines.append(STATUS_END)
    return "\n".join(lines)


def render_badges(facts: dict) -> str:
    """Render the README badges from the same facts as the status block."""
    audit = (f"{facts['audit_checks_passed']}%2F{facts['audit_checks_total']}%20Passed"
             if facts["audit_checks_total"] else "n%2Fa")
    ledger = (f"{facts['published_bets']:,}%20published%20%2F%20{facts['all_time_bets']:,}%20all-time"
              if facts["published_bets"] and facts["all_time_bets"] else "n%2Fa")
    lines = [
        BADGES_START,
        f"![Audit Checks](https://img.shields.io/badge/Audit%20Checks-{audit}-10b981)",
        f"![Strategy Personas](https://img.shields.io/badge/Personas-{facts['strategies'] or 0}-8b5cf6)",
        f"![Tracked Games](https://img.shields.io/badge/NFL%20Games-{facts['games_tracked'] or 0}-3b82f6)",
        f"![Paper Ledger](https://img.shields.io/badge/Ledger-{ledger}-06b6d4)",
        BADGES_END,
    ]
    return "\n".join(lines)


def parse_status_block(text: str) -> dict[str, str] | None:
    """Return the metric→value map of an embedded status block, or None."""
    start = text.find(STATUS_START)
    end = text.find(STATUS_END)
    if start < 0 or end < 0 or end < start:
        return None
    block = text[start + len(STATUS_START):end]
    values: dict[str, str] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 2 or cells[0] in {"metric", "---"}:
            continue
        values[cells[0]] = cells[1]
    return values


def _sha256(path: Path) -> str | None:
    import hashlib

    try:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def render_verification_block(data_dir: str | Path) -> str:
    """Render the machine-checkable half of docs/VERIFICATION.md.

    Source hashes are computed from the checked-in snapshot files themselves and
    audit rows come from ``data/audit_checks.json``, so the evidence ledger can
    never describe a file or a check that does not exist.
    """
    root = Path(data_dir)
    facts = published_facts(root)
    checks = _read(root / "audit_checks.json", []) or []
    manifest = _read(root / "ledger_manifest.json", {}) or {}
    lines = [VERIFICATION_START, "## Machine-verified evidence (generated — do not edit by hand)", ""]

    lines += ["### Source snapshot hashes", "",
              "SHA-256 computed here from the checked-in snapshot bytes. These are file hashes of the",
              "local snapshot, not a claim about an upstream release asset.", "",
              "| snapshot file | bytes | sha256 |", "| --- | --- | --- |"]
    source_dir = root / "source"
    for name in ("games.csv", "closing_lines.csv", "initial_lines.csv", "teams.csv", "officials.csv"):
        path = source_dir / name
        if not path.exists():
            lines.append(f"| {name} | missing | n/a |")
            continue
        digest = _sha256(path) or "unreadable"
        lines.append(f"| {name} | {path.stat().st_size:,} | `{digest}` |")

    lines += ["", "### Audit results", "",
              "| # | check | category | result | detail |", "| --- | --- | --- | --- | --- |"]
    for index, check in enumerate(checks, 1):
        result = "PASS" if check.get("passed") else "**FAIL**"
        detail = str(check.get("details", "")).replace("|", "\\|")
        lines.append(f"| {index} | `{check.get('name')}` | {check.get('category')} | {result} | {detail} |")

    chain_state = "not published"
    if manifest:
        chain_state = (f"{manifest.get('published_bets'):,} published of {manifest.get('all_time_bets'):,} "
                       f"simulated records; head `{str(manifest.get('chain_head_hash'))[:16]}…`; "
                       f"published window {_window(manifest.get('published_window'))}")
    lines += ["", "### Ledger chain", "",
              f"- Hash rule: `{manifest.get('hash_algorithm', 'n/a')}`",
              f"- State: {chain_state}",
              f"- The published chain starts mid-history: "
              f"{'yes (earlier seasons are aggregated, not published)' if manifest.get('published_head_is_mid_chain') else 'no'}.",
              f"- Published-state totals: {_count(facts['published_bets'])} bets / {_money(facts['published_pnl'])} USD "
              f"inside the window, {_count(facts['all_time_bets'])} bets / {_money(facts['all_time_pnl'])} USD all time.",
              "", VERIFICATION_END]
    return "\n".join(lines)


def parse_verification_block(text: str) -> str | None:
    start = text.find(VERIFICATION_START)
    end = text.find(VERIFICATION_END)
    if start < 0 or end < 0 or end < start:
        return None
    return text[start:end + len(VERIFICATION_END)]


CLAIM_PATTERNS = {
    # claim id -> (regex with one numeric group, human description)
    "claim-personas": (r'id="claim-personas"[^>]*>([^<]+)<', "strategy persona count"),
    "claim-history": (r'id="claim-history"[^>]*>([^<]+)<', "published trade-history count"),
    "claim-upcoming": (r'id="claim-upcoming"[^>]*>([^<]+)<', "upcoming signal count"),
    "claim-registry": (r'id="claim-registry"[^>]*>([^<]+)<', "registered source count"),
}


def site_claims(html: str) -> dict[str, str]:
    """Extract the data-bound numbers embedded in ``index.html``."""
    found: dict[str, str] = {}
    for claim, (pattern, _description) in CLAIM_PATTERNS.items():
        match = re.search(pattern, html)
        if match:
            found[claim] = match.group(1).strip()
    return found


def expected_site_claims(facts: dict) -> dict[str, str]:
    """The values the embedded site claims must carry for the current data."""
    published = facts["published_bets"]
    history = f"{published / 1000:.0f}k" if published else "n/a"
    return {
        "claim-personas": _count(facts["strategies"]),
        "claim-history": history,
        "claim-upcoming": _count(facts["upcoming_signals"]),
        "claim-registry": _count(facts["registry_sources"]),
    }
