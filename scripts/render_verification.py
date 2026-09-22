#!/usr/bin/env python3
"""Refresh the machine-verified section of docs/VERIFICATION.md.

The block between ``<!-- VERIFICATION_START -->`` and ``<!-- VERIFICATION_END -->``
is derived from the snapshot files and ``data/audit_checks.json``, so the
evidence ledger cannot cite a file hash or an audit result that does not exist.

Usage::

    python3 scripts/render_verification.py
    python3 scripts/render_verification.py --check
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.publication import (  # noqa: E402
    VERIFICATION_END,
    VERIFICATION_START,
    render_verification_block,
)


def render(current: str, block: str) -> str:
    start = current.find(VERIFICATION_START)
    end = current.find(VERIFICATION_END)
    if start >= 0 and end > start:
        return current[:start] + block + current[end + len(VERIFICATION_END):]
    if current and not current.endswith("\n"):
        current += "\n"
    return current + "\n" + block + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--doc", default=str(ROOT / "docs" / "VERIFICATION.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    block = render_verification_block(args.data_dir)
    path = Path(args.doc)
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    expected = render(current, block)
    if args.check:
        if expected != current:
            print(f"{path} machine-verified block is stale; run scripts/render_verification.py")
            return 1
        print(f"{path} machine-verified block matches data/")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(expected, encoding="utf-8")
    print(f"Rendered machine-verified block into {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
