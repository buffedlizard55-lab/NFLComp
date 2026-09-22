#!/usr/bin/env python3
"""Render the generated "published state" block inside README.md.

The block between ``<!-- CURRENT_STATE_START -->`` and
``<!-- CURRENT_STATE_END -->`` is derived from ``data/`` by
``engine.publication``.  Nothing in it is typed by hand, so the README cannot
claim a bet count, PnL or window that the checked-in data does not support.

Usage::

    python3 scripts/render_readme.py            # write the block
    python3 scripts/render_readme.py --check    # fail if the block is stale
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.publication import (  # noqa: E402
    BADGES_END,
    BADGES_START,
    STATUS_END,
    STATUS_START,
    published_facts,
    render_badges,
    render_status_block,
)


def _block_bounds(readme: str) -> tuple[int, int] | None:
    start = readme.find(STATUS_START)
    end = readme.find(STATUS_END)
    if start < 0 or end < 0 or end < start:
        return None
    return start, end + len(STATUS_END)


def _insertion_point(readme: str) -> int:
    """Insert the generated block before the first top-level section."""
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


def render(readme: str, block: str, badges: str | None = None) -> str:
    """Insert or refresh the generated badges and published-state block."""
    rendered = readme
    if badges is not None:
        rendered = _replace(rendered, badges, BADGES_START, BADGES_END)
    return _replace(rendered, block, STATUS_START, STATUS_END)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--readme", default=str(ROOT / "README.md"))
    parser.add_argument("--check", action="store_true", help="exit 1 if the block on disk is stale")
    args = parser.parse_args(argv)

    facts = published_facts(args.data_dir)
    block = render_status_block(facts)
    badges = render_badges(facts)
    path = Path(args.readme)
    current = path.read_text(encoding="utf-8")
    expected = render(current, block, badges)

    if args.check:
        if expected != current:
            print("README published-state block is stale; run scripts/render_readme.py")
            return 1
        print("README published-state block matches data/")
        return 0

    path.write_text(expected, encoding="utf-8")
    print(f"Rendered published-state block into {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
