"""Generated narrative blocks and the hand-typed-prose lint for NFLComp.

`data/` is the single source of truth for every published number, but the
sections *around* the generated status block in ``README.md`` were written by
hand, and two of them drifted badly (an executive summary still advertising 60
personas at a 27.15% ROI lead, and a source list naming 41 sources). Rather than
fixing those sentences by hand and waiting for the next drift, the sections are
rendered from the data files:

* :func:`render_executive_summary` — the headline bullets.
* :func:`render_roster_table` — one row per ``data/leaderboard.json`` entry.
* :func:`render_findings` — the top personas, quoted from ``data/strategies.json``
  with their measured numbers and an explicit note when the hypothesis is a
  design assumption the snapshot cannot re-derive.
* :func:`render_source_table` — one row per ``data/registry.json`` entry.

Anything a human still types is checked by :func:`prose_claim_violations`, which
compares a scanned quantity against the data file it should have come from and
returns a violation for every disagreement. Historical sentences may keep an old
number as long as the current value follows it (for example ``personas 60→70``);
a bare ``60 personas`` is a claim about today and fails.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

EXEC_SUMMARY_START = "<!-- EXEC_SUMMARY_START -->"
EXEC_SUMMARY_END = "<!-- EXEC_SUMMARY_END -->"
ROSTER_START = "<!-- ROSTER_START -->"
ROSTER_END = "<!-- ROSTER_END -->"
FINDINGS_START = "<!-- FINDINGS_START -->"
FINDINGS_END = "<!-- FINDINGS_END -->"
SOURCES_START = "<!-- SOURCES_START -->"
SOURCES_END = "<!-- SOURCES_END -->"
IRREGULARITIES_START = "<!-- IRREGULARITIES_START -->"
IRREGULARITIES_END = "<!-- IRREGULARITIES_END -->"
LAB_START = "<!-- STRATEGY_LAB_START -->"
LAB_END = "<!-- STRATEGY_LAB_END -->"

GENERATED = "generated — do not edit by hand"

#: block name -> (start marker, end marker)
BLOCK_BOUNDS = {
    "executive_summary": (EXEC_SUMMARY_START, EXEC_SUMMARY_END),
    "roster": (ROSTER_START, ROSTER_END),
    "findings": (FINDINGS_START, FINDINGS_END),
    "sources": (SOURCES_START, SOURCES_END),
    "strategy_lab": (LAB_START, LAB_END),
    "irregularities": (IRREGULARITIES_START, IRREGULARITIES_END),
}

#: start marker -> end marker, for callers that only have the marker in hand
BLOCK_ENDS = {start: end for start, end in BLOCK_BOUNDS.values()}


def read(data_dir, name: str, default=None):
    """Read one checked-in data file, falling back only when it is absent."""
    try:
        with (Path(data_dir) / name).open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def _count(value) -> str:
    return "n/a" if value is None else f"{value:,}"


def _money(value) -> str:
    if value is None:
        return "n/a"
    return f"{'-' if value < 0 else ''}${abs(value):,.2f}"


def _rate(value) -> str:
    return "n/a" if value is None else f"{value:.1f}%"


def _roi(value) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


def _cell(value) -> str:
    """Collapse whitespace and escape pipes so a value can sit in a table."""
    text = " ".join(str(value if value is not None else "n/a").split())
    return text.replace("|", "\\|")


def strip_generated_blocks(text: str) -> str:
    """Remove the generated blocks so the lint only judges human prose."""
    for start_marker, end_marker in BLOCK_BOUNDS.values():
        while True:
            start = text.find(start_marker)
            end = text.find(end_marker)
            if start < 0 or end < 0 or end < start:
                break
            text = text[:start] + text[end + len(end_marker):]
    return text


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _bankroll_phrase(leaderboard: list) -> str:
    """Describe the paper bankroll only from what the roster actually records."""
    sizes = sorted({row.get("initial_bankroll") for row in leaderboard if row.get("initial_bankroll")})
    if len(sizes) == 1:
        return f"every one flat-staking a ${sizes[0]:,.0f} paper bankroll"
    if not sizes:
        return "no bankroll recorded in the roster"
    return f"{len(sizes):,} distinct paper bankrolls recorded"


def _disagreement_clause(count: int) -> str:
    if count == 1:
        return "1 cross-check disagreement is retained"
    return f"{count:,} cross-check disagreements are retained"


def render_executive_summary(facts: dict, data_dir) -> str:
    """Headline bullets, each number taken from ``facts`` or ``data/``."""
    lab = read(data_dir, "strategy_lab.json", {}) or {}
    studies = read(data_dir, "empirical_studies.json", {}) or {}
    window = facts.get("published_window") or {}
    source = lab.get("source") or {}
    candidates = lab.get("candidates") or []
    promoted = [c for c in candidates if c.get("status") not in (None, "HOLDOUT_FAILED", "PENDING")]
    lines = [
        EXEC_SUMMARY_START,
        f"_{GENERATED} — `scripts/render_readme.py --check` fails if this block and the data disagree._",
        "",
        f"- **Current simulation window:** {facts.get('current_season') or 'n/a'} regular season, "
        f"week {_count(facts.get('current_week'))}, last completed game {facts.get('as_of_date') or 'n/a'}.",
        f"- **Historical universe:** {_count(facts.get('games_tracked'))} games in `data/source/games.csv` "
        f"({facts.get('season_span') or 'n/a'}), {_count(facts.get('games_completed'))} with a final score and "
        f"{_count(facts.get('games_upcoming'))} still open. The file is hashed into the ledger manifest "
        f"(`sha256:{(source.get('sha256') or 'n/a')[:16]}…`).",
        f"- **Published ledger:** {_count(facts.get('published_bets'))} hash-chained wagers inside the published "
        f"window {window.get('from_season', 'n/a')}–{window.get('to_season', 'n/a')} netting "
        f"{_money(facts.get('published_pnl'))}; {_count(facts.get('all_time_bets'))} simulated wagers all-time "
        f"netting {_money(facts.get('all_time_pnl'))}.",
        f"- **Strategy universe:** {_count(facts.get('strategies'))} personas across "
        f"{_count(facts.get('strategy_categories'))} categories, {_count(facts.get('strategies_with_lineage'))} of "
        f"them carrying a version lineage, {_bankroll_phrase(read(data_dir, 'leaderboard.json', []) or [])}.",
        f"- **Forward slate:** {_count(facts.get('upcoming_signals'))} queued paper signals over "
        f"{_count(facts.get('games_upcoming'))} games without a final score, of which "
        f"{_count(facts.get('open_positions'))} are open positions in the current week.",
        f"- **Research:** {_count(facts.get('research_experiments'))} dossier experiments, "
        f"{_count(facts.get('empirical_studies'))} of them re-derived from the snapshot; claims the bundled data "
        f"cannot re-derive are labelled `DECLARED_ASSUMPTION` instead of being quoted as results, and "
        f"{_disagreement_clause(len(studies.get('cross_check_disagreements') or []))} "
        f"rather than overwritten.",
        f"- **Audit:** {_count(facts.get('audit_checks_passed'))}/{_count(facts.get('audit_checks_total'))} "
        f"automated checks pass, {_count(facts.get('irregularities'))} irregularities are tracked in "
        f"`data/irregularities.json` (listed in `docs/IRREGULARITIES.md`), and no risk statistic is published "
        f"for a persona below "
        f"{_count(facts.get('risk_reporting_floor'))} settled bets.",
        f"- **Strategy lab:** {_count(len(candidates))} pre-declared candidates scored on the untouched "
        f"{(lab.get('policy') or {}).get('untouched_holdout_window', 'n/a')} holdout, "
        f"{_count(len(promoted))} of them past the promotion gate; the rest stay archived untuned.",
        "- **No real orders:** every figure here is a simulation on historical and current-season prices. "
        "Nothing in this repository places, routes, or recommends a real wager.",
        EXEC_SUMMARY_END,
    ]
    return "\n".join(lines)


def render_roster_table(data_dir, limit: int | None = None) -> str:
    """One table row per leaderboard persona; no win rate without settled bets."""
    leaderboard = read(data_dir, "leaderboard.json", []) or []
    rows = leaderboard if limit is None else leaderboard[:limit]
    lines = [
        ROSTER_START,
        f"_{GENERATED} — one row per `data/leaderboard.json` entry"
        + (f", showing the first {len(rows)} of {len(leaderboard)}._"
           if limit else f" ({len(rows)} rows)."),
        "",
        "| Strategy ID | Persona | Category | Version | Win Rate | Bets | PnL (all-time) | ROI | Max DD | Published | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        settled = (row.get("wins") or 0) + (row.get("losses") or 0)
        bets = row.get("total_bets") or 0
        lines.append(
            "| `{}` | `{}` | {} | `{}` | {} | {} | {} | {} | {} | {} | {} |".format(
                row.get("id"), row.get("username"), _cell(row.get("category")), row.get("version"),
                _rate(row.get("win_rate")) if settled else "n/a (open)",
                _count(bets),
                _money(row.get("total_pnl")) if bets else "n/a",
                _roi(row.get("roi")) if bets else "n/a",
                f"${row.get('max_drawdown'):,.2f}" if bets else "n/a",
                f"{_count(row.get('published_ledger_bets'))} bets / {_money(row.get('published_ledger_pnl'))}"
                if row.get("published_ledger_bets") else "0 bets",
                _cell(row.get("status")),
            )
        )
    lines.append(ROSTER_END)
    return "\n".join(lines)


def render_findings(facts: dict, data_dir, limit: int = 6) -> str:
    """The strongest measured rows, each labelled with its evidence class.

    A persona only appears once it has 100 settled bets. The hypothesis text is
    quoted from ``data/strategies.json``; if the study set re-derives it the row
    says so, otherwise the row is labelled a declared design assumption.
    """
    leaderboard = read(data_dir, "leaderboard.json", []) or []
    strategies = {row.get("id"): row for row in (read(data_dir, "strategies.json", []) or [])}
    studies = read(data_dir, "empirical_studies.json", {}) or {}
    documented = {}
    for study in studies.get("studies") or []:
        for strategy_id in study.get("strategy_ids") or [study.get("strategy_id")]:
            documented[strategy_id] = study

    ranked = [row for row in leaderboard
              if ((row.get("wins") or 0) + (row.get("losses") or 0)) >= 100]
    ranked.sort(key=lambda row: row.get("total_pnl", 0.0), reverse=True)

    lines = [
        FINDINGS_START,
        f"_{GENERATED} — quoted from `data/strategies.json`, measured in `data/leaderboard.json`._",
        "",
    ]
    for row in ranked[:limit]:
        meta = strategies.get(row.get("id")) or {}
        settled = (row.get("wins") or 0) + (row.get("losses") or 0)
        hypothesis = " ".join(str(meta.get("hypothesis", "no hypothesis recorded")).split())
        first_sentence = re.split(r"(?<=\.)\s", hypothesis)[0]
        study = documented.get(row.get("id"))
        if study:
            evidence = (f"hypothesis re-derived from the snapshot by `{study.get('id')}`: "
                        f"{_cell(study.get('headline'))}")
        else:
            evidence = ("`DECLARED_ASSUMPTION` — this hypothesis is a design input carried in "
                        "`data/strategies.json`; the bundled snapshot cannot re-derive it, so the figures "
                        "quoted here describe the simulated paper window only")
        lines.append(
            f"- **`{row.get('username')}`** ({_cell(row.get('category'))}, {row.get('market', 'all markets')}) — "
            f"{first_sentence} Measured all-time over {_count(row.get('total_bets'))} simulated wagers "
            f"({_count(settled)} decided): {_rate(row.get('win_rate'))} win rate, "
            f"{_money(row.get('total_pnl'))} net, {_roi(row.get('roi'))} ROI, "
            f"max drawdown ${row.get('max_drawdown') or 0:,.2f}, "
            f"{_count(row.get('published_ledger_bets'))} of those wagers inside the published window "
            f"({_money(row.get('published_ledger_pnl'))}). Evidence: {evidence}."
        )
    if not ranked:
        lines.append("- No persona has reached the 100-settled-bet reporting floor yet.")
    lines.append(FINDINGS_END)
    return "\n".join(lines)


def render_source_table(data_dir) -> str:
    """One row per registry entry, so the source count is never typed by hand."""
    registry = read(data_dir, "registry.json", []) or []
    lines = [
        SOURCES_START,
        f"_{GENERATED} — one row per `data/registry.json` entry ({len(registry)} sources). "
        "Reliability, depth and status are the registry's own recorded strings._",
        "",
        "| # | Source | Data Type | Cost | Reliability | Depth | Status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for index, row in enumerate(registry, 1):
        lines.append("| {} | {} | {} | {} | {} | {} | `{}` |".format(
            index, _cell(row.get("name")), _cell(row.get("data_type")),
            _cell(row.get("cost_classification")), _cell(row.get("reliability_rating")),
            _cell(row.get("historical_depth")), _cell(row.get("status")),
        ))
    lines.append(SOURCES_END)
    return "\n".join(lines)


def render_strategy_lab(data_dir) -> str:
    """The pre-declared lab candidates, scored window by window from the report."""
    lab = read(data_dir, "strategy_lab.json", {}) or {}
    source = lab.get("source") or {}
    policy = lab.get("policy") or {}
    lines = [
        LAB_START,
        f"_{GENERATED} — the source snapshot is `{source.get('path', 'n/a')}` "
        f"(`sha256:{str(source.get('sha256', 'n/a'))[:16]}…`, {_count(source.get('loaded_games'))} games, "
        f"{_count(source.get('completed_games'))} completed, latest {source.get('latest_completed_gameday', 'n/a')})._",
        "",
        f"Promotion gate: {policy.get('promotion_gate', 'n/a')} "
        f"Stake: {policy.get('stake', 'n/a')}.",
        "",
        "| Candidate | Market | Windows | Bets | W-L-P | Win rate | Flat-stake PnL | ROI | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in lab.get("candidates") or []:
        windows = candidate.get("windows") or {}
        for name in ("development", "validation", "holdout"):
            result = windows.get(name) or {}
            lines.append("| {} | {} | {} ({}) | {} | {}-{}-{} | {} | {} | {} | {} |".format(
                ("`%s`" % candidate.get("strategy_id")) if name == "development" else "",
                candidate.get("market") if name == "development" else "",
                name, result.get("seasons", "n/a"),
                _count(result.get("bets")), result.get("wins"), result.get("losses"), result.get("pushes"),
                _rate(result.get("win_rate_pct")), _money(result.get("flat_stake_pnl")),
                _roi(result.get("roi_pct")),
                ("`%s`" % candidate.get("status")) if name == "holdout" else "",
            ))
        lines.append("| | | **Next step** | {} | | | | | |".format(
            _cell(candidate.get("next_step"))))
    if not (lab.get("candidates") or []):
        lines.append("| — | — | — | 0 | — | — | — | — | no candidate pre-declared |")
    lines.append("")
    lines.append(f"_{policy.get('warning', '')}_")
    lines.append(LAB_END)
    return "\n".join(lines)


def render_irregularity_table(data_dir) -> str:
    """The machine-checked irregularity register, straight out of the audit export."""
    register = read(data_dir, "irregularities.json", []) or []
    lines = [
        IRREGULARITIES_START,
        f"_{GENERATED} — the export the audit writes ({len(register)} entries). "
        "An irregularity the audit detects appears here automatically; the long-form notes above are the "
        "human-written record of the earliest discoveries and keep their original numbering._",
        "",
        "| ID | Title | Category | Severity | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in register:
        lines.append("| `{}` | {} | {} | {} | `{}` |".format(
            _cell(entry.get("id")), _cell(entry.get("title")), _cell(entry.get("category")),
            _cell(entry.get("severity")), _cell(entry.get("status")),
        ))
    if not register:
        lines.append("| — | no irregularity recorded | — | — | — |")
    lines.append(IRREGULARITIES_END)
    return "\n".join(lines)


def render_blocks(facts: dict, data_dir) -> dict[str, tuple[str, str]]:
    """``{block name: (start marker, rendered text)}`` for the renderer script."""
    return {
        "executive_summary": (EXEC_SUMMARY_START, render_executive_summary(facts, data_dir)),
        "roster": (ROSTER_START, render_roster_table(data_dir)),
        "findings": (FINDINGS_START, render_findings(facts, data_dir)),
        "sources": (SOURCES_START, render_source_table(data_dir)),
        "strategy_lab": (LAB_START, render_strategy_lab(data_dir)),
        "irregularities": (IRREGULARITIES_START, render_irregularity_table(data_dir)),
    }


# ---------------------------------------------------------------------------
# Prose claim lint
# ---------------------------------------------------------------------------

#: (pattern with one numeric capture group, fact name, what the number must be)
PROSE_CLAIMS = (
    (r"(\d[\d,]*)\s+(?:autonomous\s+)?(?:betting\s+)?personas\b", "strategies",
     "the catalogued persona count"),
    (r"(\d[\d,]*)\s+strategy\s+personas\b", "strategies", "the catalogued persona count"),
    (r"(\d[\d,]*)\s+(?:catalogued\s+)?strategy\s+versions\b", "strategy_versions",
     "the number of strategy records"),
    (r"(\d[\d,]*)\s+(?:distinct\s+|quantitative\s+|research\s+)?(?:disciplines|categories)\b",
     "strategy_categories", "the number of populated strategy categories"),
    (r"[Aa]ll\s+(\d[\d,]*)\s+games\b", "games_tracked", "the game count of the snapshot"),
    (r"(\d[\d,]*)\s+completed\s+(?:NFL\s+)?games\b", "games_completed",
     "the number of games with a final score"),
    (r"(\d[\d,]*)\s+upcoming\s+(?:NFL\s+)?games\b", "games_upcoming",
     "the number of games without a final score"),
    (r"(\d[\d,]*)\s+published\s+wagers\b", "published_bets", "the published ledger size"),
    (r"(\d[\d,]*)\s+(?:raw\s+)?simulated\s+wagers\b", "all_time_bets",
     "the all-time simulated wager count"),
    (r"(\d[\d,]*)\s+(?:verified\s+|probed\s+|primary\s+|registered\s+)?sources\b", "registry_sources",
     "the number of probed data sources"),
    (r"(\d[\d,]*)\s+market\s+types\b", "market_types", "the number of priced market types"),
    (r"(\d[\d,]*)\s+(?:research\s+)?experiments\b", "research_experiments",
     "the number of dossier experiments"),
    (r"(\d[\d,]*)\s+(?:automated\s+)?audit\s+checks\b", "audit_checks_total",
     "the number of audit checks"),
    (r"(\d[\d,]*)\s+tracked\s+irregularit(?:y|ies)\b", "irregularities",
     "the number of logged irregularities"),
    (r"(\d[\d,]*)\s+game\s+(?:historical\s+)?archive\b", "games_tracked",
     "the game count of the snapshot"),
)

_SKIP_LINE = re.compile(r"^\s*(?:\||>|```|\$|#\s*(?:python3|node|gh|git)\b)")


def prose_claim_violations(text: str, facts: dict, data_dir, source: str = "document") -> list[str]:
    """One message per hand-typed quantity that contradicts the data files.

    Generated blocks are ignored: they are verified by re-rendering them, not by
    reading them back.
    """
    violations: list[str] = []
    for number, line in enumerate(strip_generated_blocks(text).splitlines(), 1):
        if _SKIP_LINE.match(line):
            continue
        for pattern, fact_name, description in PROSE_CLAIMS:
            expected = facts.get(fact_name)
            if expected is None:
                continue
            for match in re.finditer(pattern, line):
                claimed = int(match.group(1).replace(",", ""))
                if claimed != expected:
                    violations.append(
                        f"{source}:{number} says '{match.group(0).strip()}' but {description} is "
                        f"{expected:,} — quote the data file or move the number into a generated block"
                    )
    return violations
