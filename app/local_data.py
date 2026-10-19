"""Real, hand-verified local programs: loader and reader.

The existing `opportunities` table is left alone. Three things live beside it:

    program_extras  one row per program: pathway stage, environment tags, last_verified
    sessions        one row per weekly meeting time (weekday + start/end minutes)

Source of truth is three CSVs you edit in a spreadsheet:

    data/local/locations.csv   one row per place (park, school, office) with its coordinates
    data/local/programs.csv    one row per program, pointing at a location_id
    data/local/sessions.csv    one row per weekly meeting time

Load (idempotent - safe to run as often as you like):

    python -m app.local_data            # validate and load
    python -m app.local_data --check    # validate only, change nothing
"""
from __future__ import annotations

import csv
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Any

from app import db
from app.pipeline import run as run_pipeline
from app.stages import ENVIRONMENT_TAGS, STAGES, WEEKDAYS

LOCAL_DIR = Path(__file__).resolve().parent.parent / "data" / "local"
LOCATIONS_CSV = LOCAL_DIR / "locations.csv"
PROGRAMS_CSV = LOCAL_DIR / "programs.csv"
SESSIONS_CSV = LOCAL_DIR / "sessions.csv"
LOCAL_SOURCE = "local"

# Fields the generic pipeline would guess at. For hand-collected data we refuse to guess.
# cost_usd is NOT required: a blank cost means "not published / not verified" and is stored as NULL.
MUST_HAVE = ("id", "stage", "location_id", "min_age", "max_age", "last_verified", "source_url")
STATUSES = ("open", "closed", "upcoming", "unknown")  # is she able to sign up right now?

SCHEMA = """
CREATE TABLE IF NOT EXISTS program_extras (
    opportunity_id TEXT PRIMARY KEY,
    stage TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT '',
    last_verified TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unknown',
    status_note TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sessions (
    opportunity_id TEXT NOT NULL,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_minute INTEGER NOT NULL CHECK (start_minute BETWEEN 0 AND 1439),
    end_minute INTEGER NOT NULL CHECK (end_minute BETWEEN 1 AND 1440),
    drop_in INTEGER NOT NULL DEFAULT 0,
    CHECK (end_minute > start_minute)
);
CREATE INDEX IF NOT EXISTS idx_sessions_opp ON sessions(opportunity_id);
"""


# ---------------------------------------------------------------- parsing helpers

def parse_clock(text: str) -> int:
    """'16:30', '4:30 PM' or '4:30pm' -> minutes since midnight (990). Raises ValueError."""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*([ap]m)?\s*", str(text).lower())
    if not m:
        raise ValueError(f"unreadable time {text!r}")
    hour, minute, meridiem = int(m.group(1)), int(m.group(2)), m.group(3)
    if meridiem:
        if not 1 <= hour <= 12:
            raise ValueError(f"bad hour in {text!r}")
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    if hour > 23 or minute > 59:
        raise ValueError(f"time out of range {text!r}")
    return hour * 60 + minute


def parse_weekday(text: str) -> int:
    """'Tue' / 'tuesday' -> 1. Raises ValueError."""
    key = str(text).strip().lower()[:3]
    if key not in WEEKDAYS:
        raise ValueError(f"unknown day {text!r}")
    return WEEKDAYS[key]


def parse_environment(text: str) -> tuple[list[str], list[str]]:
    """'drop_in; girls_only' -> (valid_tags, unknown_tags)."""
    tags = [t.strip().lower() for t in re.split(r"[;,|]", text or "") if t.strip()]
    good = [t for t in tags if t in ENVIRONMENT_TAGS]
    bad = [t for t in tags if t not in ENVIRONMENT_TAGS]
    return sorted(set(good)), bad


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:  # utf-8-sig: Excel adds a BOM
        rows = []
        for r in csv.DictReader(fh):
            r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
            if any(r.values()):  # skip blank spreadsheet rows
                rows.append(r)
        return rows


# ---------------------------------------------------------------- validation

def validate_locations(raw: list[dict[str, str]]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return ({location_id: row}, problems). A location without usable coordinates is dropped."""
    out: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for line, r in enumerate(raw, start=2):
        lid = r.get("location_id", "")
        if not lid:
            problems.append(f"locations.csv line {line}: missing location_id")
            continue
        try:
            lat, lng = float(r.get("lat", "")), float(r.get("lng", ""))
        except ValueError:
            problems.append(f"locations.csv line {line} ({lid}): lat/lng not filled in yet - programs here are skipped")
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            problems.append(f"locations.csv line {line} ({lid}): coordinates out of range")
            continue
        out[lid] = {**r, "lat": lat, "lng": lng}
    return out, problems


def validate_programs(raw: list[dict[str, str]], locations: dict[str, dict[str, Any]],
                      ) -> tuple[list[dict[str, Any]], dict[str, dict], list[str]]:
    """Return (records_for_pipeline, extras_by_id, problems). Rows starting 'example-' are skipped."""
    records, extras, problems = [], {}, []
    waiting: dict[str, int] = {}  # location_id -> programs skipped because it has no coordinates
    for line, r in enumerate(raw, start=2):  # line 1 is the header
        pid = r.get("id", "")
        if pid.lower().startswith("example-"):
            continue
        where = f"programs.csv line {line} ({pid or r.get('name') or '?'})"
        missing = [k for k in MUST_HAVE if not r.get(k)]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}")
            continue
        if r["stage"] not in STAGES:
            problems.append(f"{where}: stage {r['stage']!r} not in {STAGES}")
            continue
        status = r.get("status") or "unknown"
        if status not in STATUSES:
            problems.append(f"{where}: status {status!r} not in {STATUSES}")
            continue
        try:
            date.fromisoformat(r["last_verified"])
        except ValueError:
            problems.append(f"{where}: last_verified must be YYYY-MM-DD")
            continue
        loc = locations.get(r["location_id"])
        if loc is None:
            waiting[r["location_id"]] = waiting.get(r["location_id"], 0) + 1
            continue
        tags, unknown = parse_environment(r.get("environment", ""))
        if unknown:
            problems.append(f"{where}: ignored unknown environment tags {unknown}")
        extras[pid] = {
            "stage": r["stage"], "environment": tags, "last_verified": r["last_verified"],
            "status": status, "status_note": r.get("status_note", ""), "source_url": r["source_url"],
            "cost_blank": r.get("cost_usd", "") == "",
        }
        # Location supplies place fields; anything typed on the program row wins.
        merged = {k: loc.get(k, "") for k in ("city", "region", "country", "lat", "lng")}
        merged.update({k: v for k, v in r.items() if v != ""})
        records.append({**merged, "source": LOCAL_SOURCE, "last_checked": r["last_verified"]})
    for lid, count in waiting.items():
        problems.append(f"{count} program(s) skipped: location {lid!r} is missing or has no coordinates")
    return records, extras, problems


def validate_sessions(raw: list[dict[str, str]], known_ids: set[str],
                      skipped_ids: set[str] = frozenset()) -> tuple[list[dict[str, Any]], list[str]]:
    """Sessions of programs in skipped_ids are ignored quietly (their own problem is already reported)."""
    sessions, problems = [], []
    for line, r in enumerate(raw, start=2):
        pid = r.get("program_id", "")
        if pid.lower().startswith("example-"):
            continue
        if pid in skipped_ids:
            continue
        if pid not in known_ids:
            problems.append(f"sessions.csv line {line}: program_id {pid!r} matches no program in programs.csv")
            continue
        try:
            start, end = parse_clock(r.get("start", "")), parse_clock(r.get("end", ""))
            if end <= start:
                raise ValueError("end must be after start")
            sessions.append({
                "opportunity_id": pid,
                "weekday": parse_weekday(r.get("day", "")),
                "start_minute": start,
                "end_minute": end,
                "drop_in": 1 if r.get("drop_in", "").lower() in {"1", "true", "yes", "y"} else 0,
            })
        except ValueError as err:
            problems.append(f"sessions.csv line {line} ({pid}): {err}")
    return sessions, problems


# ---------------------------------------------------------------- loading

def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the tables, and add columns to an older program_extras (CREATE IF NOT EXISTS won't)."""
    conn.executescript(SCHEMA)
    have = {r[1] for r in conn.execute("PRAGMA table_info(program_extras)")}
    for col in ("status", "status_note", "source_url"):
        if col not in have:
            default = "'unknown'" if col == "status" else "''"
            conn.execute(f"ALTER TABLE program_extras ADD COLUMN {col} TEXT NOT NULL DEFAULT {default}")


def load_local(programs_path: Path = PROGRAMS_CSV, sessions_path: Path = SESSIONS_CSV,
               locations_path: Path = LOCATIONS_CSV, dry_run: bool = False) -> dict[str, Any]:
    """Validate the CSVs and (unless dry_run) replace all local data in SQLite. Never raises on bad rows."""
    locations, problems = validate_locations(_read_csv(locations_path))
    program_rows = _read_csv(programs_path)
    records, extras, prob = validate_programs(program_rows, locations)
    problems += prob
    result = run_pipeline(records)
    for item in result["rejected"]:
        problems.append(f"{item['record']}: rejected by pipeline - {'; '.join(item['problems'])}")
    rows = result["rows"]
    for row in rows:
        if extras[row["id"]]["cost_blank"]:  # the pipeline guesses a cost from free text; we don't allow that
            row["cost_usd"] = None
            if row["cost_label"] in ("Free", "See website") or row["cost_label"].startswith("~$"):
                row["cost_label"] = "See website"
    kept = {r["id"] for r in rows}
    skipped = {r.get("id", "") for r in program_rows} - kept
    sessions, session_problems = validate_sessions(_read_csv(sessions_path), kept, skipped)
    problems += session_problems

    report = {"programs": len(rows), "sessions": len(sessions), "problems": problems, "loaded": False}
    if dry_run:
        return report

    db.init_db()
    conn = db.connect()
    try:
        _ensure_schema(conn)
        # The CSVs are the source of truth, so wipe previous local data first.
        old = [r[0] for r in conn.execute("SELECT id FROM opportunities WHERE source = ?", (LOCAL_SOURCE,))]
        conn.executemany("DELETE FROM program_extras WHERE opportunity_id = ?", [(i,) for i in old])
        conn.executemany("DELETE FROM sessions WHERE opportunity_id = ?", [(i,) for i in old])
        conn.execute("DELETE FROM opportunities WHERE source = ?", (LOCAL_SOURCE,))
        conn.commit()
    finally:
        conn.close()

    db.upsert(rows)  # opportunities rows (source='local')

    conn = db.connect()
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO program_extras "
            "(opportunity_id, stage, environment, last_verified, status, status_note, source_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(i, e["stage"], ",".join(e["environment"]), e["last_verified"], e["status"], e["status_note"],
              e["source_url"]) for i, e in extras.items() if i in kept],
        )
        conn.executemany(
            "INSERT INTO sessions VALUES (:opportunity_id, :weekday, :start_minute, :end_minute, :drop_in)",
            sessions,
        )
        conn.commit()
    finally:
        conn.close()
    report["loaded"] = True
    return report


# ---------------------------------------------------------------- reading

def fetch_programs() -> list[dict[str, Any]]:
    """Every opportunity (same dicts as db.fetch_all) plus stage, environment, last_verified, status,
    status_note, source_url and sessions.

    Catalog programs that have no local data get stage=None, status='unknown', empty lists.
    """
    base = db.fetch_all()
    conn = db.connect()
    try:
        _ensure_schema(conn)
        extras = {r["opportunity_id"]: r for r in conn.execute("SELECT * FROM program_extras")}
        by_program: dict[str, list[dict[str, Any]]] = {}
        for s in conn.execute("SELECT * FROM sessions ORDER BY weekday, start_minute"):
            by_program.setdefault(s["opportunity_id"], []).append({
                "weekday": s["weekday"],
                "start_minute": s["start_minute"],
                "end_minute": s["end_minute"],
                "drop_in": bool(s["drop_in"]),
            })
    finally:
        conn.close()

    for program in base:
        ex = extras.get(program["id"])
        program["stage"] = ex["stage"] if ex else None
        program["environment"] = [t for t in ex["environment"].split(",") if t] if ex else []
        program["last_verified"] = ex["last_verified"] if ex else ""
        program["status"] = ex["status"] if ex else "unknown"
        program["status_note"] = ex["status_note"] if ex else ""
        program["source_url"] = ex["source_url"] if ex else ""
        program["sessions"] = by_program.get(program["id"], [])
    return base


def main(argv: list[str]) -> int:
    report = load_local(dry_run="--check" in argv)
    print(f"programs={report['programs']} sessions={report['sessions']} loaded={report['loaded']}")
    for p in report["problems"]:
        print("  -", p)
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
