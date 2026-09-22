#!/usr/bin/env python3
"""Render the generated blocks inside README.md (and any document using them).

Five blocks are derived from ``data/`` and must never be typed by hand:

* ``CURRENT_STATE`` (``engine.publication``) — the published metrics and badges.
* ``EXEC_SUMMARY``, ``ROSTER``, ``FINDINGS``, ``SOURCES``
  (``engine.narrative``) — the narrative sections: summary bullets, the full
  strategy roster, the key-results bullets and the data-source registry table.

A block that has been hand-edited is a stale claim: ``--check`` fails, the audit
fails, and re-running this script restores the data-derived text.

Usage::

    python3 scripts/render_readme.py            # write the blocks
    python3 scripts/render_readme.py --check    # fail if any block is stale
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.narrative import BLOCK_ENDS, render_blocks  # noqa: E402
from engine.publication import (  # noqa: E402
    BADGES_END,
    BADGES_START,
    STATUS_END,
    STATUS_START,
    published_facts,
    render_badges,
    render_status_block,
)


def _insertion_point(readme: str) -> int:
    """Insert a block that has no markers yet before the first section."""
    marker = readme.find("\n## ")
    return len(readme) if marker < 0 else marker + 1


def _replace(text: str, block: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start >= 0 and end >= 0 and end > start:
        return text[:start] + block + text[end + len(end_marker):]
    point = _insertion_point(text)
    head, tail = text[:point], text[point:]
    separator = "" if head.endswith("\n\n") or not head else "\n"
    body = tail.lstrip("\n") if tail.strip() else ""
    return f"{head}{separator}{block}\n\n{body}"


def render(readme: str, block: str, badges: str | None = None, narrative=None) -> str:
    """Insert or refresh every generated block in ``readme``."""
    rendered = readme
    if badges is not None:
        rendered = _replace(rendered, badges, BADGES_START, BADGES_END)
    rendered = _replace(rendered, block, STATUS_START, STATUS_END)
    for _name, (marker, text) in (narrative or {}).items():
        end_marker = BLOCK_ENDS[marker]
        rendered = _replace(rendered, text, marker, end_marker)
    return rendered


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--readme", default=str(ROOT / "README.md"))
    parser.add_argument("--check", action="store_true", help="exit 1 if a block on disk is stale")
    parser.add_argument("--blocks", default="all",
                        help="comma-separated subset of "
                             "status,executive_summary,roster,findings,sources")
    args = parser.parse_args(argv)

    wanted = {name.strip() for name in args.blocks.split(",")}
    include_all = "all" in wanted
    facts = published_facts(args.data_dir)
    block = render_status_block(facts)
    badges = render_badges(facts)
    path = Path(args.readme)
    current = path.read_text(encoding="utf-8")

    # Blocks belong to the document that owns their type: the README carries the
    # narrative sections, docs/IRREGULARITIES.md carries the machine-checked
    # register. With --blocks all a block is refreshed where its markers already
    # live (or inserted when the document is meant to carry it), so one command
    # can drive every document without duplicating a table into all of them.
    required = {
        "README.md": {"executive_summary", "roster", "findings", "sources", "strategy_lab"},
    }.get(path.name, set())
    extra = {}
    for name, pair in render_blocks(facts, args.data_dir).items():
        if not include_all and name not in wanted:
            continue
        if pair[0] not in current and not include_all and name not in required:
            continue
        if pair[0] not in current and include_all and name not in required:
            continue
        extra[name] = pair
    expected = current
    if include_all or "status" in wanted:
        expected = _replace(expected, block, STATUS_START, STATUS_END)
        expected = _replace(expected, badges, BADGES_START, BADGES_END)
    for pair in extra.values():
        marker, text = pair
        end_marker = BLOCK_ENDS[marker]
        expected = _replace(expected, text, marker, end_marker)

    if args.check:
        if expected != current:
            print(f"{path.name} has stale generated blocks; run scripts/render_readme.py")
            return 1
        print(f"{path.name} generated blocks match data/")
        return 0

    if expected != current:
        path.write_text(expected, encoding="utf-8")
        print(f"Rendered {len(extra) + (1 if include_all or 'status' in wanted else 0)} block(s) into {path}")
    else:
        print(f"{path.name} generated blocks already match data/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
