from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any

from app.advisor import add_environment_weight, environment_score
from app.catalog import ADAPTIVE_ONLY, TYPE_COLORS, scope_for
from app.recommender import TfidfIndex


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _sport_score(user_sport: str | None, opp_sport: str) -> float:
    if not user_sport:
        return 0.55
    if user_sport == "multi" or opp_sport == "multi":
        return 0.72
    if user_sport == opp_sport:
        return 1.0
    related = {
        "soccer": {"track"},
        "track": {"soccer"},
        "softball": {"baseball"},
    }
    if opp_sport in related.get(user_sport, set()):
        return 0.35
    return 0.08


def _age_score(age: int | None, min_age: int, max_age: int) -> tuple[float, bool]:
    if age is None:
        return 0.6, True
    if min_age <= age <= max_age:
        span = max(max_age - min_age, 1)
        center = (min_age + max_age) / 2
        return 1.0 - 0.15 * abs(age - center) / span, True
    if age < min_age:
        gap = min_age - age
        return _clamp(0.35 - 0.08 * gap), False
    gap = age - max_age
    return _clamp(0.35 - 0.08 * gap), False


SKILL_RANK = {
    "beginner": 0,
    "recreational": 1,
    "competitive": 2,
    "elite": 3,
    "college": 4,
}


def _skill_score(
    user_skill: str | None, opp_skills: list[str], wants_travel: bool | None
) -> float:
    if not user_skill:
        return 0.55
    ranks = [SKILL_RANK.get(s, 1) for s in opp_skills]
    target = SKILL_RANK.get(user_skill, 1)
    best = min(abs(target - r) for r in ranks)
    base = {0: 1.0, 1: 0.78, 2: 0.45, 3: 0.22, 4: 0.1}[min(best, 4)]
    if wants_travel and "elite" in opp_skills:
        base = min(1.0, base + 0.08)
    return base


def _travel_score(wants_travel: bool | None, is_travel: bool, opp_type: str) -> float:
    if wants_travel is None:
        return 0.5
    if wants_travel:
        if is_travel:
            return 1.0 if opp_type in {"club", "national", "college"} else 0.85
        return 0.18
    return 0.95 if not is_travel else 0.4


def _proximity_score(
    home: tuple[float, float] | None,
    lat: float,
    lng: float,
    max_km: float | None,
) -> tuple[float, float | None, bool]:
    if home is None:
        return 0.5, None, True
    dist = haversine_km(home[0], home[1], lat, lng)
    cap = max_km if max_km else 4000.0
    if dist > cap:
        return _clamp(0.15 * cap / dist), dist, False
    # Smooth decay: full credit nearby, still useful for travel events farther out
    score = math.exp(-dist / (cap * 0.55))
    return _clamp(score), dist, True


def _affordability_score(budget: int | None, cost: int | None) -> float:
    if cost is None or cost == 0:
        return 1.0
    if budget is None:
        # Prefer lower cost slightly when unspecified
        return _clamp(1.0 - cost / 8000.0)
    if cost <= budget:
        return 1.0 - 0.15 * (cost / max(budget, 1))
    over = (cost - budget) / max(budget, 1)
    return _clamp(0.55 - 0.35 * over)


def next_deadline(deadline: str, today: date | None = None) -> tuple[date | None, bool]:
    """Return (next deadline on/after today, rolled_forward).

    Catalog dates are typical annual windows. A past date is rolled to the same
    month/day of the next cycle and flagged so the UI can say "estimated".
    """
    today = today or date.today()
    try:
        due = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        return None, False
    if due >= today:
        return due, False
    for year in (today.year, today.year + 1):
        try:
            candidate = due.replace(year=year)
        except ValueError:  # Feb 29
            candidate = due.replace(year=year, day=28)
        if candidate >= today:
            return candidate, True
    return None, False


def _deadline_score(due: date | None) -> float:
    if due is None:
        return 0.6  # rolling / unknown
    days = (due - date.today()).days
    if days < 14:
        return 0.7
    if days < 60:
        return 0.95
    if days < 180:
        return 1.0
    return 0.8


def _type_intent_score(intent_types: list[str] | None, opp_type: str) -> float:
    if not intent_types:
        return 0.55
    return 1.0 if opp_type in intent_types else 0.28


# Used when the student has no confirmed barriers, so scores stay exactly as before.
BASE_WEIGHTS = {
    "sport": 0.22,
    "age": 0.16,
    "skill": 0.11,
    "travel": 0.11,
    "proximity": 0.18,
    "affordability": 0.10,
    "deadline": 0.04,
    "type": 0.03,
    "relevance": 0.05,
}

# Used when she has confirmed barriers: the old weights shrink by 8% and
# "environment" takes that 8%, so the total is still 1.
WEIGHTS = add_environment_weight(BASE_WEIGHTS, share=0.08)
assert abs(sum(WEIGHTS.values()) - 1) < 1e-9

FACTOR_LABELS = {
    "sport": "sport",
    "age": "age range",
    "skill": "skill level",
    "travel": "travel preference",
    "proximity": "distance",
    "affordability": "cost",
    "deadline": "deadline timing",
    "type": "program type",
    "relevance": "prompt keywords",
    "environment": "fit for your barriers",
}


def _reasons(
    factors: dict[str, float], profile: dict[str, Any]
) -> dict[str, list[str]]:
    asked = {
        "sport": profile.get("sport"),
        "age": profile.get("age"),
        "skill": profile.get("skill"),
        "travel": profile.get("wants_travel"),
        "proximity": profile.get("lat"),
        "affordability": profile.get("budget_usd"),
        "type": profile.get("intent_types"),
        "relevance": profile.get("raw_query"),
        "deadline": True,
        "environment": profile.get("barriers") or None,
    }
    strong = [
        FACTOR_LABELS[k]
        for k, v in factors.items()
        if v >= 0.85 and asked[k] is not None
    ]
    weak = [
        FACTOR_LABELS[k] for k, v in factors.items() if v < 0.4 and asked[k] is not None
    ]
    return {"strong": strong, "weak": weak}


def rank_opportunity(
    profile: dict[str, Any], opp: dict[str, Any], relevance: float | None = None
) -> dict[str, Any]:
    home = None
    if profile.get("lat") is not None and profile.get("lng") is not None:
        home = (float(profile["lat"]), float(profile["lng"]))

    sport = _sport_score(profile.get("sport"), opp["sport"])
    age, eligible_age = _age_score(profile.get("age"), opp["min_age"], opp["max_age"])
    skill = _skill_score(
        profile.get("skill"), opp["skill_levels"], profile.get("wants_travel")
    )
    travel = _travel_score(profile.get("wants_travel"), opp["is_travel"], opp["type"])
    proximity, distance_km, within_radius = _proximity_score(
        home, opp["lat"], opp["lng"], profile.get("max_distance_km")
    )
    scope, scope_km = scope_for(opp["id"])
    home_country = profile.get("home_country")
    residency_ok = True
    if scope == "national":
        # Joined through local chapters/state associations: the HQ pin is not where you play.
        if home_country:
            residency_ok = home_country == opp["country"]
            if residency_ok:
                proximity, within_radius = max(proximity, 0.85), True
    elif scope == "regional" and distance_km is not None:
        residency_ok = distance_km <= (scope_km or 0)
    if opp["id"] in ADAPTIVE_ONLY and not profile.get("adaptive"):
        residency_ok = False
    afford = _affordability_score(profile.get("budget_usd"), opp.get("cost_usd"))
    due, estimated = next_deadline(opp["deadline"])
    deadline = _deadline_score(due)
    type_fit = _type_intent_score(profile.get("intent_types"), opp["type"])

    factors = {
        "sport": sport,
        "age": age,
        "skill": skill,
        "travel": travel,
        "proximity": proximity,
        "affordability": afford,
        "deadline": deadline,
        "type": type_fit,
        "relevance": 0.5 if relevance is None else _clamp(relevance),
    }

    barriers = profile.get("barriers") or []
    if barriers:
        factors["environment"] = environment_score(opp.get("tags") or [], barriers)
        weights = WEIGHTS
    else:
        weights = BASE_WEIGHTS
    raw = sum(factors[k] * weights[k] for k in weights)
    score = round(100 * raw)
    eligible = eligible_age and within_radius and residency_ok and scope != "resource"
    if not eligible:
        score = min(score, 62)
    if not residency_ok:
        score = min(score, 40)

    return {
        **opp,
        "compatibility": score,
        "distance_km": None if distance_km is None else round(distance_km, 1),
        "distance_mi": None
        if distance_km is None
        else round(distance_km * 0.621371, 1),
        "eligible": eligible,
        "eligible_age": eligible_age,
        "within_radius": within_radius,
        "residency_ok": residency_ok,
        "scope": scope,
        "next_deadline": due.isoformat() if due else None,
        "deadline_estimated": estimated,
        "color": TYPE_COLORS.get(opp["type"], "#888888"),
        "factors": {k: round(v, 3) for k, v in factors.items()},
        "reasons": _reasons(factors, profile),
    }


def rank_catalog(
    profile: dict[str, Any],
    rows: list[dict[str, Any]],
    index: TfidfIndex | None = None,
) -> list[dict[str, Any]]:
    """Score every row. TF-IDF similarity to the prompt is scaled to 0-1 by the best match."""
    relevance: dict[str, float] = {}
    query = profile.get("raw_query")
    if query:
        index = index or TfidfIndex(rows)
        raw = index.query_scores(query)
        top = max(raw.values(), default=0.0)
        if top > 0:
            relevance = {k: v / top for k, v in raw.items()}
    ranked = [
        rank_opportunity(profile, row, relevance.get(row["id"]) if relevance else None)
        for row in rows
    ]
    ranked.sort(
        key=lambda r: (
            -r["compatibility"],
            r["distance_km"] is None,
            r["distance_km"] or 0,
        )
    )
    return ranked
