"""Small normalized, provenance-preserving SQLite store for paper trading.

The checked-in JSON files are static read models for GitHub Pages.  This store
is the write-side boundary for future collectors: source observations and bets
are append-only, and corrections are represented as new audit events rather
than updates or deletes.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS source_observation (
  observation_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  available_at TEXT,
  payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  verification_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS game (
  game_id TEXT PRIMARY KEY,
  season INTEGER NOT NULL,
  week INTEGER NOT NULL,
  gameday TEXT NOT NULL,
  away_team TEXT NOT NULL,
  home_team TEXT NOT NULL,
  completed INTEGER NOT NULL,
  source_observation_id TEXT REFERENCES source_observation(observation_id)
);
CREATE TABLE IF NOT EXISTS strategy_version (
  strategy_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  parent_strategy_id TEXT,
  methodology_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiment (
  experiment_id TEXT PRIMARY KEY,
  strategy_id TEXT NOT NULL REFERENCES strategy_version(strategy_id),
  phase TEXT NOT NULL CHECK (phase IN ('BACKTEST','VALIDATION','OOS','FORWARD_TEST','PAPER_TRADE')),
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_bet (
  bet_id TEXT PRIMARY KEY,
  strategy_id TEXT NOT NULL REFERENCES strategy_version(strategy_id),
  game_id TEXT,
  phase TEXT NOT NULL CHECK (phase IN ('BACKTEST','FORWARD_TEST','PAPER_TRADE')),
  decision_at TEXT NOT NULL,
  price_json TEXT NOT NULL,
  execution_json TEXT NOT NULL,
  settlement_json TEXT,
  source_observation_id TEXT REFERENCES source_observation(observation_id),
  previous_hash TEXT NOT NULL,
  record_hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS audit_event (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS irregularity (
  irregularity_id TEXT PRIMARY KEY,
  severity TEXT NOT NULL,
  category TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def register_strategy(db: sqlite3.Connection, strategy: dict[str, Any]) -> None:
    """Register a version once; strategy rows are immutable after insertion."""
    required = {"id", "name", "version", "created_at"}
    missing = required - set(strategy)
    if missing:
        raise ValueError(f"strategy missing required fields: {sorted(missing)}")
    db.execute(
        """INSERT INTO strategy_version
        (strategy_id,name,version,parent_strategy_id,methodology_json,created_at)
        VALUES (?,?,?,?,?,?)""",
        (strategy["id"], strategy["name"], strategy["version"],
         strategy.get("parent_strategy_id"), _json(strategy.get("methodology", {})), strategy["created_at"]),
    )
    db.commit()


def append_bet(db: sqlite3.Connection, bet: dict[str, Any]) -> None:
    """Insert once. Existing bet IDs are rejected, never overwritten."""
    required = {"bet_id", "strategy_id", "phase", "decision_at", "record_hash"}
    missing = required - set(bet)
    if missing:
        raise ValueError(f"paper bet missing required fields: {sorted(missing)}")
    db.execute(
        """INSERT INTO paper_bet
        (bet_id,strategy_id,game_id,phase,decision_at,price_json,execution_json,
         settlement_json,source_observation_id,previous_hash,record_hash)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (bet["bet_id"], bet["strategy_id"], bet.get("game_id"), bet["phase"],
         bet["decision_at"], _json(bet.get("price", {})), _json(bet.get("execution", {})),
         _json(bet["settlement"]) if bet.get("settlement") is not None else None,
         bet.get("source_observation_id"), bet.get("previous_hash", ""), bet["record_hash"]),
    )
    db.commit()


def record_irregularity(db: sqlite3.Connection, item: dict[str, Any]) -> None:
    required = {"id", "severity", "category", "description", "status", "created_at"}
    missing = required - set(item)
    if missing:
        raise ValueError(f"irregularity missing required fields: {sorted(missing)}")
    db.execute(
        "INSERT INTO irregularity VALUES (?,?,?,?,?,?)",
        (item["id"], item["severity"], item["category"], item["description"], item["status"], item["created_at"]),
    )
    db.commit()
