#!/usr/bin/env python3
"""Bind the numbers written in index.html prose to the published data.

The site also rewrites these spans at runtime from the loaded JSON, but the
checked-in HTML must already be correct: a reader who views the page (or a
crawler) should never see a claim the data does not support.  The audit suite
fails when the two disagree, and this script is how they are brought back into
agreement.

Usage::

    python3 scripts/render_claims.py            # update the spans in index.html
    python3 scripts/render_claims.py --check    # fail if any span is stale
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.publication import (  # noqa: E402
    CLAIM_PATTERNS,
    expected_site_claims,
    published_facts,
    site_claims,
)


def apply_claims(html: str, expected: dict[str, str]) -> tuple[str, list[str]]:
    stale: list[str] = []
    updated = html
    for claim, value in expected.items():
        pattern, _description = CLAIM_PATTERNS[claim]
        match = re.search(pattern, updated)
        if not match:
            stale.append(f"{claim} is not bound in index.html")
            continue
        if match.group(1).strip() != value:
            updated = updated[:match.start(1)] + value + updated[match.end(1):]
            stale.append(f"{claim}: {match.group(1).strip()} -> {value}")
    return updated, stale


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--html", default=str(ROOT / "index.html"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.html)
    html = path.read_text(encoding="utf-8")
    expected = expected_site_claims(published_facts(args.data_dir))
    updated, changes = apply_claims(html, expected)

    if args.check:
        if changes:
            print("index.html claims are stale:")
            for change in changes:
                print(f"  {change}")
            return 1
        print("index.html claims match the data files")
        return 0

    if updated != html:
        path.write_text(updated, encoding="utf-8")
        print(f"Updated {len(changes)} claim(s) in {path}")
    else:
        print("index.html claims already match the data files")
    for change in changes:
        print(f"  {change}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
