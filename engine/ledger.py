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


GENESIS_HASH = "0" * 64

#: Keys the published chain owns.  They are excluded from the payload a record
#: commits to, because a record cannot hash its own hash.
CHAIN_FIELDS = ("previous_hash", "hash")


def canonical_record(record: dict) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def record_hash(record: dict, previous_hash: str = "") -> str:
    payload = previous_hash.encode() + b"\n" + canonical_record(record)
    return hashlib.sha256(payload).hexdigest()


def chain_payload(record: dict) -> str:
    """Serialise the fields a ledger record commits to.

    Every field except ``previous_hash``/``hash`` is included, in sorted key
    order, so a single changed field is detectable from the hash alone.
    """
    committed = {key: record[key] for key in sorted(record) if key not in CHAIN_FIELDS}
    return json.dumps(committed)


def chain_hash(record: dict, previous_hash: str = GENESIS_HASH) -> str:
    """Hash of ``record`` linked to the hash of the record before it."""
    return hashlib.sha256((previous_hash + chain_payload(record)).encode()).hexdigest()


def verify_chain(records: Iterable[dict]) -> tuple[bool, list[str], str]:
    """Verify an exported hash chain without trusting the writer.

    Returns ``(ok, errors, head_hash)``.  The check is purely local: each record
    must commit to the previous record's published hash and must hash to its own
    published hash.  When the export starts mid-history the first record's
    ``previous_hash`` points at a record that is not published here, which is
    reported as an error only if ``previous_hash`` is missing entirely.
    """
    errors: list[str] = []
    previous: str | None = None
    head = GENESIS_HASH
    seen: set[str] = set()
    for index, record in enumerate(records, 1):
        bet_id = record.get("bet_id")
        if not bet_id:
            errors.append(f"record {index}: missing bet_id")
        elif bet_id in seen:
            errors.append(f"record {index}: duplicate bet_id {bet_id}")
        else:
            seen.add(bet_id)
        linked = record.get("previous_hash")
        stored = record.get("hash")
        if stored is None:
            errors.append(f"record {index}: missing hash")
            continue
        if linked is None:
            errors.append(f"record {index}: missing previous_hash")
            continue
        if previous is not None and linked != previous:
            errors.append(f"record {index}: previous_hash does not link to record {index - 1}")
        expected = chain_hash(record, linked)
        if stored != expected:
            errors.append(f"record {index}: hash does not match its contents ({bet_id})")
        previous = stored
        head = stored
    return not errors, errors, head


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


def _load_records(path):
    with Path(path).open(encoding="utf-8") as fh:
        head = fh.read(1)
        fh.seek(0)
        if head == "[":
            return json.load(fh)
        return [json.loads(line)["record"] for line in fh if line.strip()]


def main(argv=None):
    """``python3 -m engine.ledger --verify data/bets_ledger.json``

    Re-derives a published JSON or JSONL ledger from its own bytes.  Exits
    non-zero on the first inconsistency so CI and the Node contract test can use
    the same verifier the generator uses.
    """
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if "--verify" not in args or args.index("--verify") + 1 >= len(args):
        print(__doc__ or "usage: python3 -m engine.ledger --verify PATH")
        return 2
    path = args[args.index("--verify") + 1]
    records = _load_records(path)
    ok, errors, head = verify_chain(records)
    if ok:
        print(f"{path}: {len(records)} records, chain OK, head {head[:16]}…")
        return 0
    print(f"{path}: chain INVALID ({len(errors)} problems)")
    for error in errors[:10]:
        print(f"  {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
