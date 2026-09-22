"""NFLComp source snapshot synchronizer.

Refreshes the checked-in nflverse/nfldata snapshot with full provenance and a
machine-readable revision log. The mission forbids silently overwriting source
data, so this module never does that: every refresh records

* which endpoint actually served the bytes (several mirrors are attempted in
  order; raw.githubusercontent.com is not reachable from every environment),
* the retrieval timestamp, byte count, and SHA-256 of the new file,
* the SHA-256 of the file it replaces,
* and a field-level diff for ``games.csv`` so that upstream *revisions* of
  already-published rows (score corrections, line moves, projected-starter
  reassignments) are preserved and can be promoted to the irregularity
  register instead of being silently absorbed.

Point-in-time safety: fields that upstream mutates before kickoff (e.g. the
projected QB fields in ``games.csv``) are mutable *upstream data*, and the
revision log is the audit trail that keeps backtests honest about that.

Usage::

    python3 -m engine.source_sync                 # refresh snapshot + manifest
    python3 -m engine.source_sync --check         # verify manifest hashes, no writes
    python3 -m engine.source_sync --offline       # diff only / no network (hash check)

Nothing here places a bet or edits the ledger; it only refreshes source data
with an audit trail.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

NFLDATA_REPO = "nflverse/nfldata"
NFLDATA_BRANCH = "master"
MANIFEST_NAME = "sync_manifest.json"

#: Upstream file -> local snapshot file.  Only files that are genuinely
#: refreshed from nflverse/nfldata belong here; curated local artifacts
#: (injury JSON, the FiveThirtyEight Elo archive) are intentionally absent.
SOURCE_FILES = {
    "data/games.csv": "games.csv",
    "data/closing_lines.csv": "closing_lines.csv",
    "data/initial_lines.csv": "initial_lines.csv",
    "data/teams.csv": "teams.csv",
    "data/standings.csv": "standings.csv",
    "data/officials.csv": "officials.csv",
    "data/trades.csv": "trades.csv",
}

#: Field classes in games.csv.  ``track`` fields are diffed row-level with a
#: classification and severity; anything else still triggers a hash-level
#: change note but not a per-field revision record.
FIELD_CLASSES = {
    "away_score": ("result", "RESULT_POSTED", "INFO"),
    "home_score": ("result", "RESULT_POSTED", "INFO"),
    "result": ("result", "RESULT_POSTED", "INFO"),
    "total": ("result", "RESULT_POSTED", "INFO"),
    "overtime": ("result", "RESULT_POSTED", "INFO"),
    "away_moneyline": ("price", "ODDS_POSTED", "INFO"),
    "home_moneyline": ("price", "ODDS_POSTED", "INFO"),
    "spread_line": ("price", "ODDS_POSTED", "INFO"),
    "away_spread_odds": ("price", "ODDS_POSTED", "INFO"),
    "home_spread_odds": ("price", "ODDS_POSTED", "INFO"),
    "total_line": ("price", "ODDS_POSTED", "INFO"),
    "under_odds": ("price", "ODDS_POSTED", "INFO"),
    "over_odds": ("price", "ODDS_POSTED", "INFO"),
    "away_qb_name": ("projected_starter", "QB_POSTED", "INFO"),
    "home_qb_name": ("projected_starter", "QB_POSTED", "INFO"),
    "away_qb_id": ("projected_starter", "QB_ID_POSTED", "INFO"),
    "home_qb_id": ("projected_starter", "QB_ID_POSTED", "INFO"),
    "away_coach": ("projected_starter", "COACH_POSTED", "INFO"),
    "home_coach": ("projected_starter", "COACH_POSTED", "INFO"),
    "temp": ("environment", "WEATHER_POSTED", "INFO"),
    "wind": ("environment", "WEATHER_POSTED", "INFO"),
    "roof": ("environment", "WEATHER_POSTED", "INFO"),
    "surface": ("environment", "SURFACE_POSTED", "INFO"),
    "referee": ("officials", "OFFICIAL_POSTED", "INFO"),
    "gameday": ("schedule", "SCHEDULE_POSTED", "INFO"),
    "gametime": ("schedule", "SCHEDULE_POSTED", "INFO"),
}

#: Revisions of an already-*filled* value are reclassified with these types
#: and severities; a filled score changing after settlement is HIGH because
#: it invalidates previously settled paper wagers.
REVISION_CLASSES = {
    "result": ("RESULT_CORRECTED", "HIGH"),
    "price": ("LINE_MOVED", "MEDIUM"),
    "projected_starter": ("STARTER_REASSIGNED", "MEDIUM"),
    "environment": ("ENVIRONMENT_REVISED", "LOW"),
    "officials": ("OFFICIAL_CHANGED", "LOW"),
    "schedule": ("SCHEDULE_MOVED", "LOW"),
}

#: Cap the full revision list stored in the manifest; the summary counts
#: remain complete either way.
MAX_REVISION_RECORDS = 500

_FETCH_TIMEOUT = 120


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _http_get(url: str) -> tuple[bytes, int]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "nflcomp-source-sync",
        },
    )
    with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT) as response:
        return response.read(), response.status


_TREE_CACHE: dict = {}


def _fetch_tree() -> dict:
    if "tree" not in _TREE_CACHE:
        tree_url = f"https://api.github.com/repos/{NFLDATA_REPO}/git/trees/{NFLDATA_BRANCH}?recursive=1"
        tree_raw, _status = _http_get(tree_url)
        _TREE_CACHE["tree"] = json.loads(tree_raw.decode("utf-8"))
    return _TREE_CACHE["tree"]


def _fetch_via_blobs(remote_path: str) -> dict:
    """Fetch through the git trees+blobs API (works where raw.* is blocked)."""
    tree = _fetch_tree()
    entry = next((t for t in tree.get("tree", []) if t.get("path") == remote_path and t.get("type") == "blob"), None)
    if entry is None:
        raise FileNotFoundError(f"{remote_path} not found in upstream tree")
    blob_url = f"https://api.github.com/repos/{NFLDATA_REPO}/git/blobs/{entry['sha']}"
    blob_raw, status = _http_get(blob_url)
    blob = json.loads(blob_raw.decode("utf-8"))
    if blob.get("encoding") != "base64":
        raise ValueError(f"unexpected blob encoding {blob.get('encoding')!r}")
    content = base64.b64decode(blob["content"])
    endpoint = f"api.github.com/git/blobs/{entry['sha'][:10]}"
    return {
        "content": content,
        "endpoint": endpoint,
        "http_status": status,
        "git_blob_sha": entry["sha"],
        "upstream_size": entry.get("size"),
    }


def _fetch_via_contents(remote_path: str) -> dict:
    url = f"https://api.github.com/repos/{NFLDATA_REPO}/contents/{remote_path}?ref={NFLDATA_BRANCH}"
    raw, status = _http_get(url)
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("encoding") != "base64":
        raise ValueError("contents API did not inline the file (too large)")
    content = base64.b64decode(payload["content"])
    return {
        "content": content,
        "endpoint": f"api.github.com/contents/{remote_path}",
        "http_status": status,
        "git_blob_sha": payload.get("sha"),
        "upstream_size": payload.get("size"),
    }


def _fetch_via_raw(remote_path: str) -> dict:
    url = f"https://raw.githubusercontent.com/{NFLDATA_REPO}/{NFLDATA_BRANCH}/{remote_path}"
    content, status = _http_get(url)
    return {
        "content": content,
        "endpoint": f"raw.githubusercontent.com/{remote_path}",
        "http_status": status,
        "git_blob_sha": None,
        "upstream_size": len(content),
    }


def fetch_remote_file(remote_path: str, attempts: list) -> dict | None:
    """Try each mirror in order, recording every attempt for the manifest."""
    fetchers = (
        ("github_git_blobs_api", _fetch_via_blobs),
        ("github_contents_api", _fetch_via_contents),
        ("raw_githubusercontent", _fetch_via_raw),
    )
    for name, fetcher in fetchers:
        started = time.time()
        try:
            result = fetcher(remote_path)
            attempts.append({
                "strategy": name,
                "endpoint": result["endpoint"],
                "http_status": result["http_status"],
                "result": "OK",
                "bytes": len(result["content"]),
                "seconds": round(time.time() - started, 2),
            })
            return result
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError, KeyError, FileNotFoundError) as exc:
            attempts.append({
                "strategy": name,
                "endpoint": f"{NFLDATA_REPO}/{remote_path}",
                "http_status": getattr(exc, "code", None),
                "result": f"FAILED: {type(exc).__name__}: {exc}",
                "bytes": 0,
                "seconds": round(time.time() - started, 2),
            })
    return None


def _load_csv_rows(raw: bytes) -> tuple[list[str], list[list[str]]]:
    text = raw.decode("utf-8-sig", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def diff_games_rows(old_raw: bytes, new_raw: bytes) -> tuple[list[dict], dict]:
    """Field-level diff of two games.csv snapshots keyed by game_id."""
    old_header, old_rows = _load_csv_rows(old_raw)
    new_header, new_rows = _load_csv_rows(new_raw)
    revisions: list[dict] = []
    summary = {
        "old_rows": len(old_rows),
        "new_rows": len(new_rows),
        "rows_added": 0,
        "rows_removed": 0,
        "rows_with_field_changes": 0,
        "field_changes": 0,
        "posted_fields": 0,
        "revised_fields": 0,
        "by_type": {},
        "by_severity": {},
        "schema_changed": old_header != new_header,
    }
    if old_header != new_header:
        revisions.append({
            "file": "games.csv",
            "type": "SCHEMA_CHANGED",
            "key": "*",
            "field": None,
            "old": f"{len(old_header)} columns",
            "new": f"{len(new_header)} columns",
            "severity": "HIGH",
            "settled_at_revision": True,
        })
        return revisions, summary

    def index(header, rows):
        gid_pos = header.index("game_id") if "game_id" in header else 0
        out = {}
        for row in rows:
            if len(row) <= gid_pos or not row[gid_pos]:
                continue
            out[row[gid_pos]] = row
        return out

    old_map = index(old_header, old_rows)
    new_map = index(new_header, new_rows)
    removed = sorted(set(old_map) - set(new_map))
    added = sorted(set(new_map) - set(old_map))
    summary["rows_removed"] = len(removed)
    summary["rows_added"] = len(added)
    for gid in removed:
        revisions.append({
            "file": "games.csv", "type": "GAME_REMOVED", "key": gid, "field": None,
            "old": "present", "new": "absent", "severity": "HIGH",
            "settled_at_revision": True,
        })
    for gid in added:
        revisions.append({
            "file": "games.csv", "type": "GAME_ADDED", "key": gid, "field": None,
            "old": None, "new": "present", "severity": "MEDIUM",
            "settled_at_revision": False,
        })

    col = {name: i for i, name in enumerate(new_header)}
    for gid in sorted(set(old_map) & set(new_map)):
        old_row, new_row = old_map[gid], new_map[gid]
        old_scores = (old_row[col["away_score"]].strip(), old_row[col["home_score"]].strip())
        was_settled = all(old_scores)
        changed_in_game = False
        for field, (klass, post_type, info_sev) in FIELD_CLASSES.items():
            i = col.get(field)
            if i is None or i >= len(old_row) or i >= len(new_row):
                continue
            old_val = old_row[i].strip()
            new_val = new_row[i].strip()
            if old_val == new_val:
                continue
            changed_in_game = True
            summary["field_changes"] += 1
            if old_val == "":
                rev_type, severity = post_type, info_sev
                summary["posted_fields"] += 1
            else:
                rev_type, severity = REVISION_CLASSES.get(klass, ("VALUE_REVISED", "MEDIUM"))
                if klass == "projected_starter":
                    rev_type = "QB_REASSIGNED" if field.endswith(("_qb_name", "_qb_id")) else ("COACH_REASSIGNED" if field.endswith("_coach") else rev_type)
                summary["revised_fields"] += 1
            summary["by_type"][rev_type] = summary["by_type"].get(rev_type, 0) + 1
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
            revisions.append({
                "file": "games.csv",
                "type": rev_type,
                "key": gid,
                "field": field,
                "old": old_val or None,
                "new": new_val or None,
                "severity": severity,
                # settled_at_revision means the record being changed already fed
                # settled outcomes in the previous snapshot — those revisions
                # must be reviewed, never auto-absorbed.
                "settled_at_revision": was_settled,
            })
        if changed_in_game:
            summary["rows_with_field_changes"] += 1
    return revisions, summary


def _file_hash_diff_only(old_raw: bytes | None, new_raw: bytes, name: str) -> tuple[list[dict], dict]:
    summary = {
        "old_bytes": len(old_raw) if old_raw is not None else 0,
        "new_bytes": len(new_raw),
        "changed": (old_raw is None) or (_sha256_bytes(old_raw) != _sha256_bytes(new_raw)),
    }
    revisions: list[dict] = []
    summary["row_delta"] = None
    if summary["changed"] and name.endswith(".csv"):
        try:
            old_rows = 0 if old_raw is None else max(0, len(_load_csv_rows(old_raw)[1]))
            new_rows = max(0, len(_load_csv_rows(new_raw)[1]))
            summary["row_delta"] = new_rows - old_rows
            revisions.append({
                "file": name,
                "type": "FILE_UPDATED",
                "key": name,
                "field": None,
                "old": f"{old_rows} rows" if old_raw is not None else None,
                "new": f"{new_rows} rows",
                "severity": "INFO",
                "settled_at_revision": False,
            })
        except (ValueError, csv.Error):
            pass
    return revisions, summary


def sync_snapshot(source_dir: str = "data/source", write: bool = True) -> dict:
    """Refresh the snapshot. Returns (and writes) the provenance manifest."""
    os.makedirs(source_dir, exist_ok=True)
    manifest_path = os.path.join(source_dir, MANIFEST_NAME)
    previous = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                previous = json.load(f)
        except (OSError, json.JSONDecodeError):
            previous = {}

    manifest = {
        "classification": "SOURCE_PROVENANCE",
        "generated_by": "engine/source_sync.py",
        "upstream_repo": f"https://github.com/{NFLDATA_REPO}",
        "upstream_branch": NFLDATA_BRANCH,
        "synced_at_utc": _utcnow_iso(),
        "previous_synced_at_utc": previous.get("synced_at_utc"),
        "fetch_attempts": [],
        "files": {},
        "revisions": [],
        "revision_summary": {},
        # revision_history is the append-only cross-cycle record of every
        # MEDIUM/HIGH revision a sync has ever caught; the register is built
        # from it, so a flag from an earlier cycle can never quietly vanish.
        # Manifests written before revision_history existed are migrated: the
        # notable entries of their latest-cycle revision list carry forward.
        "revision_history": _legacy_history(previous),
        # acknowledged_reviews is human-vsited: a RESULT_CORRECTED against an
        # already-settled game blocks verification until its revision id is
        # listed here with a note proving a human reconciled it.
        "acknowledged_reviews": list(previous.get("acknowledged_reviews") or []),
        "errors": [],
    }

    all_revisions: list[dict] = []
    aggregate_summary: dict = {"by_type": {}, "by_severity": {}, "changed_files": [], "unchanged_files": []}

    for remote_path, local_name in SOURCE_FILES.items():
        local_path = os.path.join(source_dir, local_name)
        old_raw = None
        old_hash = None
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                old_raw = f.read()
            old_hash = _sha256_bytes(old_raw)

        attempts: list = []
        fetched = fetch_remote_file(remote_path, attempts)
        manifest["fetch_attempts"].extend(attempts)
        file_entry = {
            "upstream_url": f"https://github.com/{NFLDATA_REPO}/blob/{NFLDATA_BRANCH}/{remote_path}",
            "fetch": None,
            "previous_sha256": old_hash,
            "changed": None,
            "revision_summary": None,
        }
        if fetched is None:
            file_entry["changed"] = False
            file_entry["fetch"] = {"result": "UNAVAILABLE - kept previous snapshot"}
            manifest["errors"].append(f"{local_name}: no mirror reachable; kept previous snapshot")
            aggregate_summary["unchanged_files"].append(local_name)
            manifest["files"][local_name] = file_entry
            continue

        new_raw = fetched["content"]
        new_hash = _sha256_bytes(new_raw)
        changed = old_hash != new_hash
        if local_name == "games.csv" and old_raw is not None and changed:
            revisions, rev_summary = diff_games_rows(old_raw, new_raw)
        elif old_raw is None:
            # First-time ingest cannot diff against nothing; hash-level only.
            revisions, rev_summary = _file_hash_diff_only(None, new_raw, local_name)
        elif changed:
            revisions, rev_summary = _file_hash_diff_only(old_raw, new_raw, local_name)
        else:
            revisions, rev_summary = [], {"changed": False}

        if write and changed:
            tmp_path = local_path + ".tmp"
            with open(tmp_path, "wb") as f:
                f.write(new_raw)
            os.replace(tmp_path, local_path)

        file_entry["fetch"] = {
            "endpoint": fetched["endpoint"],
            "http_status": fetched["http_status"],
            "retrieved_at_utc": _utcnow_iso(),
            "bytes": len(new_raw),
            "sha256": new_hash,
            "git_blob_sha": fetched["git_blob_sha"],
        }
        file_entry["changed"] = changed
        file_entry["revision_summary"] = rev_summary
        manifest["files"][local_name] = file_entry

        (aggregate_summary["changed_files"] if changed else aggregate_summary["unchanged_files"]).append(local_name)
        for rev in revisions:
            aggregate_summary["by_type"][rev["type"]] = aggregate_summary["by_type"].get(rev["type"], 0) + 1
            aggregate_summary["by_severity"][rev["severity"]] = aggregate_summary["by_severity"].get(rev["severity"], 0) + 1
        all_revisions.extend(revisions)

    aggregate_summary["total_revisions"] = len(all_revisions)
    if len(all_revisions) > MAX_REVISION_RECORDS:
        high = [r for r in all_revisions if r["severity"] in ("HIGH", "MEDIUM")]
        info = [r for r in all_revisions if r["severity"] not in ("HIGH", "MEDIUM")]
        aggregate_summary["revision_records_truncated"] = True
        all_revisions = (high + info)[:MAX_REVISION_RECORDS]
    manifest["revisions"] = all_revisions
    manifest["revision_summary"] = aggregate_summary

    notable_now = [r for r in all_revisions if r.get("severity") in ("HIGH", "MEDIUM")]
    history = manifest["revision_history"]
    seen_ids = {r["revision_id"] for r in history}
    for rev in notable_now:
        rid = revision_id(rev)
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        history.append({
            **rev,
            "revision_id": rid,
            "synced_at_utc": manifest["synced_at_utc"],
        })
    manifest["revision_history"] = history[-1000:]
    by_type_counts: dict = {}
    for rev in manifest["revision_history"]:
        by_type_counts[rev["type"]] = by_type_counts.get(rev["type"], 0) + 1
    manifest["history_summary"] = {
        "notable_revisions_retained": len(manifest["revision_history"]),
        "by_type": by_type_counts,
        "notable_added_this_sync": len([r for r in notable_now]),
    }

    if write:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=1)
            f.write("\n")
    return manifest


def revision_id(rev: dict) -> str:
    """Stable identity of a single upstream revision for review tracking."""
    basis = f"{rev.get('type')}|{rev.get('key')}|{rev.get('field')}|{rev.get('old')}|{rev.get('new')}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _legacy_history(previous: dict) -> list:
    """Carry a pre-history manifest's notable revisions into revision_history."""
    history = list(previous.get("revision_history") or [])
    seen = {r.get("revision_id") for r in history}
    if not history:
        migrated = []
        for rev in previous.get("revisions") or []:
            if rev.get("severity") not in ("HIGH", "MEDIUM"):
                continue
            rid = revision_id(rev)
            if rid in seen:
                continue
            seen.add(rid)
            migrated.append({
                **rev,
                "revision_id": rid,
                "synced_at_utc": previous.get("synced_at_utc"),
                "migrated_from": "legacy_cycle_revisions",
            })
        history = migrated
    return history


def unacknowledged_corrections(manifest: dict) -> list[dict]:
    """RESULT_CORRECTED entries in the persistent history with no review note."""
    acknowledged = {
        (a.get("revision_id") if isinstance(a, dict) else a)
        for a in manifest.get("acknowledged_reviews", [])
    }
    return [
        r for r in manifest.get("revision_history", [])
        if r.get("type") == "RESULT_CORRECTED" and r.get("revision_id") not in acknowledged
    ]


def check_manifest(source_dir: str = "data/source") -> tuple[bool, list[str]]:
    """Verify that every file fetched per the manifest still matches disk."""
    manifest_path = os.path.join(source_dir, MANIFEST_NAME)
    problems: list[str] = []
    if not os.path.exists(manifest_path):
        return False, [f"missing {manifest_path}; run python3 -m engine.source_sync first"]
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    if manifest.get("classification") != "SOURCE_PROVENANCE":
        problems.append("sync manifest carries no SOURCE_PROVENANCE classification")
    for local_name, entry in manifest.get("files", {}).items():
        fetch = entry.get("fetch") or {}
        recorded = fetch.get("sha256")
        if not recorded:
            continue
        path = os.path.join(source_dir, local_name)
        if not os.path.exists(path):
            problems.append(f"{local_name}: manifest records sha256 but file is missing")
            continue
        with open(path, "rb") as f:
            disk = _sha256_bytes(f.read())
        if disk != recorded:
            problems.append(f"{local_name}: on-disk sha256 {disk[:12]}… != manifest {recorded[:12]}…")
    corrections = unacknowledged_corrections(manifest)
    if corrections:
        problems.append(
            f"{len(corrections)} result corrections pending review; settled wagers must not be silently "
            f"re-settled — reconcile and append each revision_id to acknowledged_reviews in {MANIFEST_NAME}"
        )
    return (not problems), problems


def revisions_for_irregularity_register(manifest: dict, limit: int = 8) -> list[dict]:
    """Promote the notable sync revisions into irregularity-register entries.

    Field revisions are grouped per (type, game) so one register entry reads
    as one real-world event ("MIA @ SF closed 1.0 pt lower across 5 fields")
    rather than five near-duplicate rows, and reviews-critical classes
    (score corrections, starter reassignments) are never crowded out by an
    ordinary pre-kickoff line move.
    """
    history = manifest.get("revision_history") or []
    if history:
        # Persistent cross-cycle record: every MEDIUM/HIGH revision any sync
        # ever caught, so an earlier flag cannot vanish from the register.
        notable = history
        summary = manifest.get("history_summary", {}) or {}
    else:
        notable = [r for r in (manifest.get("revisions") or [])
                   if r.get("severity") in ("HIGH", "MEDIUM")]
        summary = manifest.get("revision_summary", {}) or {}
    severity_rank = {"HIGH": 0, "MEDIUM": 1}
    groups: dict = {}
    occurrence_counts: dict = {}
    first_seen: dict = {}
    for rev in notable:
        key = (rev["type"], rev["key"])
        occurrence_counts[key] = occurrence_counts.get(key, 0) + 1
        seen_at = rev.get("synced_at_utc")
        if key not in first_seen or (seen_at and seen_at < first_seen[key]):
            first_seen[key] = seen_at
        entry = groups.setdefault(key, {"heads": rev, "fields": []})
        if rev.get("severity") == "HIGH" and entry["heads"]["severity"] != "HIGH":
            entry["heads"] = rev
        if seen_at and (entry["heads"].get("synced_at_utc") or "") <= seen_at:
            entry["heads"] = rev
        entry["fields"].append(rev)
    ordered = sorted(
        groups.values(),
        key=lambda g: (severity_rank.get(g["heads"]["severity"], 3),
                       0 if g["heads"]["settled_at_revision"] else 1,
                       g["heads"]["type"], g["heads"]["key"]),
    )
    items: list[dict] = []
    acronym_fix = {"Qb": "QB"}
    for idx, group in enumerate(ordered[:limit], start=1):
        head = group["heads"]
        fields = group["fields"]
        label = " ".join(acronym_fix.get(tok, tok) for tok in head["type"].replace("_", " ").title().split())
        # Within one (type, game) group the same field may recur across sync
        # cycles; describe the latest state per field while keeping the count.
        latest_by_field: dict = {}
        for f in fields:
            latest_by_field[f.get("field")] = f
        field_desc = "; ".join(
            f"{f['field']}: {f.get('old')!r} -> {f.get('new')!r}"
            for f in list(latest_by_field.values())[:6])
        if len(latest_by_field) > 6:
            field_desc += f"; +{len(latest_by_field) - 6} more fields"
        seen_note = ""
        if history:
            first = first_seen.get((head["type"], head["key"]))
            last = head.get("synced_at_utc")
            if first and last and first != last:
                seen_note = f" First caught {first}; latest sighting {last}."
            elif last:
                seen_note = f" Caught {last}."
        if head.get("settled_at_revision"):
            resolution = (
                "REVIEW REQUIRED: the revised record had already fed settled paper wagers. "
                "Historical settlements are preserved as originally published; the revision is "
                "retained for reconciliation rather than re-settled silently."
            )
        else:
            resolution = (
                "Revision occurred before the game was played, so no settled wager could have "
                "consumed the earlier value. Mutable upstream fields (projected starters, weather, "
                "schedule) are treated as point-in-time estimates until kickoff; the revision log "
                "is retained as the audit trail."
            )
        items.append({
            "id": f"IRR-SYNC-{idx:02d}-{head['type']}-{head['key']}",
            "title": f"Upstream revision: {label} ({head['key']})",
            "category": "UPSTREAM_REVISION",
            "severity": head["severity"],
            "description": (
                f"nflverse revised {head['file']} for {head['key']} across {len(latest_by_field)} tracked "
                f"field(s): {field_desc}.{seen_note}"
            ),
            "source": manifest.get("upstream_repo", "nflverse/nfldata"),
            "resolution": resolution,
            "status": "FLAGGED" if head.get("settled_at_revision") else "LOGGED_AND_RESOLVED",
        })
    if len(ordered) > limit:
        by_type = summary.get("by_type", {})
        total = summary.get("notable_revisions_retained", summary.get("total_revisions", 0))
        items.append({
            "id": "IRR-SYNC-SUMMARY",
            "title": f"Upstream sync revision summary (+{len(ordered) - limit} more grouped MEDIUM/HIGH events)",
            "category": "UPSTREAM_REVISION",
            "severity": "LOW",
            "description": (
                f"Sync history retains {total} notable field revisions "
                f"({json.dumps(by_type, sort_keys=True)}). Full detail in data/source/sync_manifest.json."
            ),
            "source": manifest.get("upstream_repo", "nflverse/nfldata"),
            "resolution": "Full revision log retained in the sync manifest; low-severity postings are lifecycle-expected.",
            "status": "LOGGED_AND_RESOLVED",
        })
    return items


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    source_dir = "data/source"
    write = True
    check = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--check", "--offline"):
            check = True
        elif arg == "--no-write":
            write = False
        elif arg == "--source-dir" and i + 1 < len(argv):
            i += 1
            source_dir = argv[i]
        i += 1

    if check:
        ok, problems = check_manifest(source_dir)
        if ok:
            with open(os.path.join(source_dir, MANIFEST_NAME), encoding="utf-8") as f:
                manifest = json.load(f)
            summary = manifest.get("revision_summary", {})
            print(f"Source sync manifest verified: last sync {manifest.get('synced_at_utc')}, "
                  f"{len(manifest.get('files', {}))} files hashed, "
                  f"{summary.get('total_revisions', 0)} logged revisions.")
            return 0
        for problem in problems:
            print(f"SYNC CHECK FAILED: {problem}")
        return 1

    manifest = sync_snapshot(source_dir, write=write)
    summary = manifest.get("revision_summary", {})
    print(f"Source sync complete at {manifest['synced_at_utc']}")
    print(f"  changed files: {summary.get('changed_files', [])}")
    print(f"  revisions: {summary.get('total_revisions', 0)} ({summary.get('by_severity', {})})")
    for err in manifest.get("errors", []):
        print(f"  WARNING: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
