"""Turn the onboarding quiz into a ranking profile, a weekly plan, and a skill pathway."""
from __future__ import annotations

from typing import Any

from app.ranking import SKILL_RANK, rank_catalog

LEVELS = ["beginner", "recreational", "competitive", "elite", "college"]
LEVEL_LABELS = {
    "beginner": "Beginner",
    "recreational": "Recreational",
    "competitive": "Competitive / club",
    "elite": "Elite / academy",
    "college": "College",
}
COMPETITION_TYPES = {
    "rec_league": "recreation",
    "school_team": "school",
    "club_travel": "club",
    "tournaments": "national",
    "college_recruiting": "college",
    "community": "nonprofit",
}
TRAVEL_COMPETITIONS = {"club_travel", "tournaments", "college_recruiting"}
# How far a weekly practice can realistically be, by how the athlete gets there (miles).
TRANSPORT_WEEKLY_MI = {"bike_walk": 5, "transit": 15, "carpool": 30, "parent": 40, "car": 40}
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TIMES = {"morning": "Morning (7 am–12 pm)", "afternoon": "Afternoon (12–5 pm)", "evening": "Evening (5–9 pm)"}  # keep in sync with SLOT_WINDOWS in fit.py
KM_PER_MI = 1.60934


def to_ranking_profile(quiz: dict[str, Any]) -> dict[str, Any]:
    comps = quiz.get("competitions") or []
    barriers = set(quiz.get("barriers") or [])
    home = quiz.get("home") or {}
    profile: dict[str, Any] = {
        "sport": quiz.get("sport") or None,
        "age": quiz.get("age"),
        "skill": quiz.get("skill") or None,
        "budget_usd": quiz.get("budget_usd"),
        "intent_types": [COMPETITION_TYPES[c] for c in comps if c in COMPETITION_TYPES] or None,
        "adaptive": "disability" in barriers or None,
    }
    if quiz.get("max_distance_mi"):
        profile["max_distance_km"] = float(quiz["max_distance_mi"]) * KM_PER_MI
    if comps:
        profile["wants_travel"] = bool(TRAVEL_COMPETITIONS & set(comps))
    if "cost" in barriers and profile["budget_usd"] is None:
        profile["budget_usd"] = 200
    if home.get("lat") is not None and home.get("lng") is not None:
        profile.update(
            lat=float(home["lat"]), lng=float(home["lng"]),
            home_label=home.get("label") or "Home", home_country=home.get("country"),
        )
    if quiz.get("goal_text"):
        profile["raw_query"] = quiz["goal_text"]
    return {k: v for k, v in profile.items() if v is not None}


def _slots(quiz: dict[str, Any]) -> list[tuple[str, str]]:
    out = []
    for slot in quiz.get("availability") or []:
        day, _, time = slot.partition("-")
        if day in DAYS and time in TIMES:
            out.append((day, time))
    return sorted(out, key=lambda s: (DAYS.index(s[0]), list(TIMES).index(s[1])))


def _weekly_ok(item: dict[str, Any], cap_km: float) -> bool:
    if not item["eligible"] or item["scope"] == "resource":
        return False
    if item["type"] not in {"club", "recreation", "school", "nonprofit"}:
        return False
    if item["scope"] == "national":
        return True  # local chapters
    return item["distance_km"] is None or item["distance_km"] <= cap_km


def _card_summary(item: dict[str, Any]) -> dict[str, Any]:
    local = item["scope"] == "national" and item.get("residency_ok")
    return {
        "id": item["id"],
        "name": item["name"],
        "type": item["type"],
        "compatibility": item["compatibility"],
        "distance": "Find your local chapter" if local
        else ("under 1 mi" if (item.get("distance_mi") or 0) < 1 and item.get("distance_mi") is not None
              else f"{item['distance_mi']:,} mi" if item.get("distance_mi") is not None else "—"),
        "cost": item["cost_label"],
        "levels": item["skill_levels"],
        "next_deadline": item["next_deadline"],
        "deadline_estimated": item["deadline_estimated"],
        "why": item["reasons"]["strong"],
    }


def next_level(skill: str | None) -> str | None:
    if not skill or skill not in LEVELS:
        return "recreational"
    i = LEVELS.index(skill)
    return LEVELS[i + 1] if i + 1 < len(LEVELS) else None


def pathway(skill: str | None, goal: str | None, ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = SKILL_RANK.get(skill or "beginner", 0)
    target = SKILL_RANK.get(goal, None) if goal else None
    steps = []
    for level in LEVELS:
        rank = SKILL_RANK[level]
        status = "past" if rank < current else "current" if rank == current else "upcoming"
        if target is not None and rank > target:
            status = "beyond"
        example = next(
            (r for r in ranked if r["eligible"] and level in r["skill_levels"] and r["scope"] != "resource"), None
        )
        steps.append({
            "level": level,
            "label": LEVEL_LABELS[level],
            "status": status,
            "is_goal": level == goal,
            "example": {"id": example["id"], "name": example["name"]} if example else None,
        })
    return steps


def build_plan(quiz: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    profile = to_ranking_profile(quiz)
    ranked = rank_catalog(profile, rows)
    transport = quiz.get("transport") or "car"
    cap_mi = TRANSPORT_WEEKLY_MI.get(transport, 40)
    if quiz.get("max_distance_mi"):
        cap_mi = min(cap_mi, float(quiz["max_distance_mi"]))
    reachable = [r for r in ranked if _weekly_ok(r, cap_mi * KM_PER_MI)]
    # Weekly sessions should be at the athlete's current level and inside the budget;
    # harder or pricier programs belong in "next step", not in this week's plan.
    skill_now = quiz.get("skill")
    budget = profile.get("budget_usd")

    def fits(r: dict[str, Any]) -> bool:
        level_ok = not skill_now or skill_now in r["skill_levels"]
        cost_ok = budget is None or r["cost_usd"] is None or r["cost_usd"] <= budget
        return level_ok and cost_ok

    weekly = ([r for r in reachable if fits(r)] or reachable)[:3]

    sessions = []
    slots = _slots(quiz)[:4]
    # Main program gets the first two slots (teams usually practice 2x/week), others fill the rest.
    order = [0, 0, 1, 2] if len(weekly) >= 3 else [0, 0, 1, 1] if len(weekly) == 2 else [0, 0, 0, 0]
    for (day, time), idx in zip(slots, order):
        if not weekly:
            break
        item = weekly[idx]
        sessions.append({
            "day": day,
            "time": TIMES[time],
            **_card_summary(item),
            "schedule_note": "Your available slot. The program's real practice times aren't in our database, so confirm them on its site.",
        })

    skill = profile.get("skill")
    nxt = next_level(skill)
    step_up = None
    if nxt and skill:
        cand = next(
            (r for r in ranked if r["eligible"] and nxt in r["skill_levels"] and r["scope"] != "resource"
             and r["id"] not in {w["id"] for w in weekly[:1]}),
            None,
        )
        step_up = {
            "after": "After 4–6 weeks of consistent sessions",
            "level": nxt,
            "label": LEVEL_LABELS[nxt],
            "program": _card_summary(cand) if cand else None,
        }

    events = [
        _card_summary(r) for r in ranked
        if r["eligible"] and r["is_travel"] and r["type"] in {"national", "college"}
    ][:3] if profile.get("wants_travel") else []

    tips = []
    barriers = set(quiz.get("barriers") or [])
    if "cost" in barriers:
        tips.append("Cost: the free and low-cost programs are ranked higher. Ask clubs about financial aid. Many offer it but don't advertise it.")
    if "transport" in barriers or transport in {"bike_walk", "transit"}:
        tips.append(f"Getting there: weekly picks stay within {int(cap_mi)} mi because of how you travel.")
    if "time" in barriers:
        tips.append("Time: the plan uses only the slots you marked as available.")
    if "disability" in barriers:
        tips.append("Adaptive sport: programs with adaptive or unified divisions are included.")
    if "new_to_sport" in barriers or "confidence" in barriers:
        tips.append("New or nervous? Start with a recreational group. They focus on learning, not tryouts.")

    return {
        "profile": profile,
        "sessions": sessions,
        "no_slots": not slots,
        "weekly_programs": [_card_summary(w) for w in weekly],
        "step_up": step_up,
        "events": events,
        "pathway": pathway(skill, quiz.get("goal_level"), ranked),
        "top_matches": [_card_summary(r) for r in ranked if r["eligible"]][:8],
        "tips": tips,
    }
