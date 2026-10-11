from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from app.catalog import CATALOG

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "playpath.db"

COLUMNS = (
    "id", "name", "organization", "type", "sport", "city", "region", "country",
    "lat", "lng", "min_age", "max_age", "skill_levels", "cost_usd", "cost_label",
    "deadline", "eligibility", "is_travel", "women_focused", "website",
    "description", "season", "source", "last_checked",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    organization TEXT NOT NULL,
    type TEXT NOT NULL,
    sport TEXT NOT NULL,
    city TEXT NOT NULL,
    region TEXT NOT NULL,
    country TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    min_age INTEGER NOT NULL,
    max_age INTEGER NOT NULL,
    skill_levels TEXT NOT NULL,
    cost_usd INTEGER,
    cost_label TEXT NOT NULL,
    deadline TEXT NOT NULL,
    eligibility TEXT NOT NULL,
    is_travel INTEGER NOT NULL,
    women_focused INTEGER NOT NULL,
    website TEXT NOT NULL,
    description TEXT NOT NULL,
    season TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'catalog',
    last_checked TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_opp_sport ON opportunities(sport);
CREATE INDEX IF NOT EXISTS idx_opp_type ON opportunities(type);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _catalog_hash() -> str:
    return hashlib.sha256(json.dumps(CATALOG, sort_keys=True).encode()).hexdigest()[:16]


def init_db() -> None:
    """Create schema and (re)load the curated catalog through the pipeline when it changes."""
    from app.pipeline import run

    conn = connect()
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(opportunities)")}
        if cols and not {"source", "last_checked"} <= cols:
            conn.execute("DROP TABLE opportunities")  # pre-pipeline schema
        conn.executescript(SCHEMA)
        row = conn.execute("SELECT value FROM meta WHERE key='catalog_hash'").fetchone()
        current = _catalog_hash()
        if row is None or row[0] != current:
            conn.execute("DELETE FROM opportunities WHERE source='catalog'")
            _upsert(conn, run([{**c, "source": "catalog"} for c in CATALOG])["rows"])
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('catalog_hash', ?)", (current,))
        conn.commit()
    finally:
        conn.close()


def _upsert(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]]) -> None:
    def encode(item: dict[str, Any]) -> tuple:
        values = dict(item)
        values["skill_levels"] = json.dumps(values["skill_levels"])
        values["is_travel"] = int(values["is_travel"])
        values["women_focused"] = int(values["women_focused"])
        values.setdefault("source", "catalog")
        values.setdefault("last_checked", "")
        return tuple(values[c] for c in COLUMNS)

    conn.executemany(
        f"INSERT OR REPLACE INTO opportunities ({','.join(COLUMNS)}) "
        f"VALUES ({','.join('?' * len(COLUMNS))})",
        [encode(r) for r in rows],
    )


def upsert(rows: Iterable[dict[str, Any]]) -> None:
    init_db()
    conn = connect()
    try:
        _upsert(conn, rows)
        conn.commit()
    finally:
        conn.close()


def fetch_all() -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM opportunities").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["skill_levels"] = json.loads(data["skill_levels"])
    data["is_travel"] = bool(data["is_travel"])
    data["women_focused"] = bool(data["women_focused"])
    return data
