"""Append-only, hash-chained paper-bet ledger utilities.

The web JSON export is a read model.  This module provides a small auditable
write format for future live/forward runs: each record commits to the previous
record, so edits and deletions are detectable without trusting the UI.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


def canonical_record(record: dict) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def record_hash(record: dict, previous_hash: str = "") -> str:
    payload = previous_hash.encode() + b"\n" + canonical_record(record)
    return hashlib.sha256(payload).hexdigest()


def append_bet(path: str | Path, record: dict) -> dict:
    """Append a bet and return the signed envelope; never overwrite a ledger."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = ""
    if target.exists():
        with target.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    previous = json.loads(line)["record_hash"]
    envelope = {"previous_hash": previous, "record_hash": record_hash(record, previous), "record": record}
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(envelope, sort_keys=True) + "\n")
    return envelope


def verify_ledger(path: str | Path) -> tuple[bool, list[str]]:
    """Verify chain links, hashes, and duplicate bet IDs."""
    errors: list[str] = []
    previous = ""
    ids: set[str] = set()
    target = Path(path)
    if not target.exists():
        return True, errors
    with target.open(encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            try:
                envelope = json.loads(line)
                record = envelope["record"]
                if envelope.get("previous_hash", "") != previous:
                    errors.append(f"line {number}: previous hash mismatch")
                expected = record_hash(record, previous)
                if envelope.get("record_hash") != expected:
                    errors.append(f"line {number}: record hash mismatch")
                bet_id = record.get("bet_id")
                if bet_id and bet_id in ids:
                    errors.append(f"line {number}: duplicate bet_id {bet_id}")
                if bet_id:
                    ids.add(bet_id)
                previous = envelope.get("record_hash", "")
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(f"line {number}: invalid envelope ({exc})")
    return not errors, errors
