"""Data pipeline: extract -> normalize -> validate -> dedupe -> load.

Turns raw source records (CSV / JSON rows scraped or exported from schools,
colleges, rec departments, nonprofits, clubs) into clean `opportunities` rows.
Free-text fields are mined with rule-based extractors (no LLM), so every value
in the database is traceable to the source text.

CLI:
    python -m app.pipeline data/sources/my_export.csv          # dry run report
    python -m app.pipeline data/sources/my_export.csv --load   # upsert into SQLite
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from app.catalog import CITIES, OPPORTUNITY_TYPES
from app.parser import SPORT_ALIASES

REQUIRED = ("name", "organization", "website")
SKILLS = ("beginner", "recreational", "competitive", "elite", "college")

TYPE_HINTS = [
    ("college", r"\b(college|university|ncaa|naia|njcaa|id camp|varsity)\b"),
    ("school", r"\b(high school|middle school|school district|athletic association|hsaa|uil)\b"),
    ("national", r"\b(national team|federation|odp|olympic|pathway|national championship|world)\b"),
    ("nonprofit", r"\b(nonprofit|non-profit|foundation|charity|501\(c\)|scholarship fund)\b"),
    ("recreation", r"\b(parks?|recreation|rec league|ymca|ayso|community center)\b"),
    ("club", r"\b(club|academy|fc\b|sc\b|ecnl|travel team|select)\b"),
]

SKILL_HINTS = [
    ("college", r"\b(college|ncaa|recruit|scholarship|id camp)\b"),
    ("elite", r"\b(elite|odp|national team|academy|high[-\s]?performance)\b"),
    ("competitive", r"\b(competitive|club|travel|select|tryouts?)\b"),
    ("recreational", r"\b(recreational|rec\b|everyone plays|for fun|community)\b"),
    ("beginner", r"\b(beginner|intro|learn to|first[-\s]time|no experience)\b"),
]


def _text(record: dict[str, Any]) -> str:
    keys = ("name", "organization", "description", "eligibility", "cost_label", "notes")
    return " ".join(str(record.get(k) or "") for k in keys).lower()


def extract_sport(text: str) -> str:
    for sport, aliases in SPORT_ALIASES.items():
        if sport == "multi":
            continue
        for alias in sorted(aliases, key=len, reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", text):
                return sport
    return "multi"


def extract_type(text: str) -> str:
    for kind, pattern in TYPE_HINTS:
        if re.search(pattern, text):
            return kind
    return "club"


def extract_ages(text: str) -> tuple[int, int] | None:
    m = re.search(r"\bages?\s*(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\b", text)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
        return lo, hi
    m = re.search(r"\bu-?(\d{1,2})\s*(?:-|–|to)\s*u-?(\d{1,2})\b", text)
    if m:  # U-ages: U14 = under 14, so players are roughly 13
        lo, hi = sorted((int(m.group(1)) - 1, int(m.group(2)) - 1))
        return lo, hi
    if re.search(r"\b(grades?\s*9\s*(?:-|–|to)\s*12|high school)\b", text):
        return 14, 18
    if re.search(r"\b(college|ncaa|university)\b", text):
        return 15, 22
    return None


def extract_cost(text: str) -> int | None:
    if re.search(r"\b(free|no cost|no fee|fully funded)\b", text):
        return 0
    m = re.search(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)", text)
    if m:
        return int(m.group(1).replace(",", ""))
    return None


def extract_skills(text: str) -> list[str]:
    found = [s for s, pattern in SKILL_HINTS if re.search(pattern, text)]
    return sorted(set(found), key=SKILLS.index) or ["recreational"]


def extract_travel(text: str) -> bool:
    return bool(re.search(r"\b(travel|showcase|tournament|national|regional|odp|away games)\b", text))


def geocode(city: str | None) -> tuple[float, float] | None:
    """Offline gazetteer lookup. Returns None when the city is unknown."""
    if not city:
        return None
    key = city.strip().lower()
    for entry in CITIES:
        if entry["name"] == key:
            return entry["lat"], entry["lng"]
    return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    f = _to_float(value)
    return None if f is None else int(f)


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def slugify(*parts: str) -> str:
    joined = "-".join(p for p in parts if p)
    return re.sub(r"[^a-z0-9]+", "-", joined.lower()).strip("-")[:80]


def normalize(record: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (clean_row, problems). clean_row is None when the record is unusable."""
    problems: list[str] = []
    for key in REQUIRED:
        if not str(record.get(key) or "").strip():
            problems.append(f"missing {key}")
    if problems:
        return None, problems

    text = _text(record)
    sport = (record.get("sport") or "").strip().lower() or extract_sport(text)
    opp_type = (record.get("type") or "").strip().lower() or extract_type(text)
    if opp_type not in OPPORTUNITY_TYPES:
        problems.append(f"unknown type '{opp_type}'")
        return None, problems

    lat, lng = _to_float(record.get("lat")), _to_float(record.get("lng"))
    if lat is None or lng is None:
        coords = geocode(record.get("city"))
        if coords is None:
            problems.append(f"could not geocode city '{record.get('city')}'")
            return None, problems
        lat, lng = coords
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        problems.append("coordinates out of range")
        return None, problems

    min_age, max_age = _to_int(record.get("min_age")), _to_int(record.get("max_age"))
    if min_age is None or max_age is None:
        ages = extract_ages(text)
        if ages is None:
            problems.append("age range not stated; defaulted to 5-99")
            ages = (5, 99)
        min_age, max_age = ages

    skills = record.get("skill_levels")
    if isinstance(skills, str):
        skills = [s.strip() for s in re.split(r"[;,|]", skills) if s.strip()]
    skills = [s for s in (skills or []) if s in SKILLS] or extract_skills(text)

    cost = record.get("cost_usd")
    cost = _to_int(cost) if cost not in (None, "") else extract_cost(text)

    deadline = str(record.get("deadline") or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline):
        problems.append("no deadline; marked rolling")
        deadline = "rolling"

    row = {
        "id": record.get("id") or slugify(record["organization"], record["name"]),
        "name": record["name"].strip(),
        "organization": record["organization"].strip(),
        "type": opp_type,
        "sport": sport,
        "city": (record.get("city") or "").strip(),
        "region": (record.get("region") or "").strip(),
        "country": (record.get("country") or "").strip(),
        "lat": lat,
        "lng": lng,
        "min_age": min_age,
        "max_age": max_age,
        "skill_levels": skills,
        "cost_usd": cost,
        "cost_label": (record.get("cost_label") or ("Free" if cost == 0 else f"~${cost:,}" if cost else "See website")).strip(),
        "deadline": deadline,
        "eligibility": (record.get("eligibility") or "See website").strip(),
        "is_travel": _to_bool(record.get("is_travel"), extract_travel(text)),
        "women_focused": _to_bool(record.get("women_focused"), bool(re.search(r"\b(girls?|women'?s?)\b", text))),
        "website": record["website"].strip(),
        "description": (record.get("description") or "").strip(),
        "season": (record.get("season") or "").strip(),
        "source": (record.get("source") or "import").strip(),
        "last_checked": (record.get("last_checked") or "").strip(),
    }
    return row, problems


def dedupe(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicates by id and by (organization, name, sport, city)."""
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, ...]] = set()
    out = []
    for row in rows:
        key = tuple(str(row[k]).lower() for k in ("organization", "name", "sport", "city"))
        if row["id"] in seen_ids or key in seen_keys:
            continue
        seen_ids.add(row["id"])
        seen_keys.add(key)
        out.append(row)
    return out


def run(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    clean, rejected, warnings = [], [], []
    for i, record in enumerate(records):
        row, problems = normalize(record)
        label = record.get("name") or f"row {i}"
        if row is None:
            rejected.append({"record": label, "problems": problems})
        else:
            clean.append(row)
            if problems:
                warnings.append({"record": label, "problems": problems})
    before = len(clean)
    clean = dedupe(clean)
    return {
        "rows": clean,
        "rejected": rejected,
        "warnings": warnings,
        "duplicates_dropped": before - len(clean),
        "run_date": date.today().isoformat(),
    }


def read_source(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("opportunities", [])
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(r, source=r.get("source") or path.name) for r in csv.DictReader(fh)]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    path, load = Path(argv[0]), "--load" in argv
    result = run(read_source(path))
    print(f"clean={len(result['rows'])} rejected={len(result['rejected'])} "
          f"warnings={len(result['warnings'])} duplicates={result['duplicates_dropped']}")
    for item in result["rejected"] + result["warnings"]:
        print(f"  - {item['record']}: {'; '.join(item['problems'])}")
    if load:
        from app.db import upsert

        upsert(result["rows"])
        print("loaded into SQLite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
