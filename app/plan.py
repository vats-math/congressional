"""Turn the onboarding quiz into a ranking profile, a weekly plan, and a skill pathway."""
from __future__ import annotations

from typing import Any

from app.ranking import rank_catalog
from app.stages import STAGES, STAGE_LABELS

LEVELS = ["beginner", "recreational", "competitive", "elite", "college"]
LEVEL_LABELS = {
    "beginner": "Beginner",
    "recreational": "Recreational",
    "competitive": "Competitive / club",
    "elite": "Elite / academy",
    "college": "College",
}
SKILL_START_STAGE = {
    "beginner": "intro_clinic",
    "recreational": "rec_league",
    "competitive": "intermediate_group",
    "elite": "club_league",
    "college": "club_league",
}
STAGE_INDEX = {stage: index for index, stage in enumerate(STAGES)}

# Weeks are typical time spent at a stage before moving on, not a promise about
# any individual athlete. Readiness notes describe the transition to the next stage.
PATHWAY_GRAPH = {
    "intro_clinic": (
        {"to": "open_play", "weeks": 4, "ready_when": "Attend 4+ sessions and feel comfortable with the basic skills."},
        {"to": "camp", "weeks": 2, "ready_when": "Complete a multi-day camp and practice the core skills."},
    ),
    "open_play": (
        {"to": "camp", "weeks": 2, "ready_when": "Build consistency across 6+ drop-in sessions."},
        {"to": "rec_league", "weeks": 6, "ready_when": "Feel ready to attend weekly and play with a team."},
    ),
    "camp": (
        {"to": "rec_league", "weeks": 6, "ready_when": "Complete camp and demonstrate the rules and basic skills."},
        {"to": "intermediate_group", "weeks": 8, "ready_when": "Use sport-specific skills confidently in controlled play."},
    ),
    "rec_league": (
        {"to": "intermediate_group", "weeks": 8, "ready_when": "Attend 6+ games and feel ready for more structured practice."},
        {"to": "school_team", "weeks": 10, "ready_when": "Practice consistently and prepare for school-team tryouts."},
    ),
    "intermediate_group": (
        {"to": "school_team", "weeks": 8, "ready_when": "Meet the skills and fitness expectations for school-team tryouts."},
        {"to": "club_league", "weeks": 12, "ready_when": "Be ready for regular practices, competitive play, and possible tryouts."},
    ),
    "school_team": (
        {"to": "club_league", "weeks": 12, "ready_when": "Build experience and check local club-league tryout requirements."},
    ),
    "club_league": (),
}
_GOAL_TEXT_STAGES = (
    (("school team", "school-team", "make varsity", "make the team"), "school_team"),
    (("college", "recruit", "scholarship"), "club_league"),
    (("club", "travel team", "tournament", "showcase", "elite"), "club_league"),
    (("recreational", "rec league", "for fun"), "rec_league"),
)
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


def starting_stage(skill: str | None, years_since_played: int | None = None) -> str:
    """Map the athlete's experience to a program stage, stepping back after a long break."""
    stage = SKILL_START_STAGE.get(skill or "beginner", "intro_clinic")
    if years_since_played is not None and years_since_played > 2:
        stage = STAGES[max(0, STAGE_INDEX[stage] - 1)]
    return stage


def goal_stage(
    goal: str | None,
    competitions: list[str] | None = None,
    goal_text: str | None = None,
    current_stage: str | None = None,
) -> str:
    """Resolve the athlete's stated goal and competition preferences to a catalog stage."""
    text = (goal_text or "").casefold()
    target = None
    for phrases, stage in _GOAL_TEXT_STAGES:
        if any(phrase in text for phrase in phrases):
            target = stage
            break

    preferences = set(competitions or [])
    if target is None:
        if goal == "recreational":
            target = "rec_league"
        elif goal == "beginner":
            target = "intro_clinic"
        elif goal == "competitive":
            if "school_team" in preferences:
                target = "school_team"
            elif preferences & {"club_travel", "tournaments", "college_recruiting"}:
                target = "club_league"
            else:
                target = "intermediate_group"
        elif goal in {"elite", "college"}:
            target = "club_league"
        elif "college_recruiting" in preferences or preferences & {"club_travel", "tournaments"}:
            target = "club_league"
        elif "school_team" in preferences:
            target = "school_team"
        elif "rec_league" in preferences:
            target = "rec_league"
        elif "community" in preferences:
            target = "open_play"
        else:
            target = current_stage or "intro_clinic"

    # A pathway moves forward only. If the selected goal is below her current
    # experience, keep the current stage as the nearest attainable goal.
    if current_stage in STAGE_INDEX and STAGE_INDEX[target] < STAGE_INDEX[current_stage]:
        return current_stage
    return target


def enumerate_routes(start: str, goal: str) -> list[list[str]]:
    """Enumerate every forward route between two stages in the small pathway graph."""
    if start not in PATHWAY_GRAPH or goal not in PATHWAY_GRAPH:
        return []
    if STAGE_INDEX[goal] < STAGE_INDEX[start]:
        goal = start

    routes: list[list[str]] = []

    def walk(stage: str, route: list[str]) -> None:
        if stage == goal:
            routes.append(route)
            return
        for edge in PATHWAY_GRAPH[stage]:
            next_stage = edge["to"]
            if STAGE_INDEX[next_stage] <= STAGE_INDEX[goal]:
                walk(next_stage, [*route, next_stage])

    walk(start, [start])
    return routes


def _route_score(route: list[str], best_by_stage: dict[str, dict[str, Any]], shortest: int) -> float:
    fits = [float(best_by_stage[stage].get("fit", 0)) for stage in route if stage in best_by_stage]
    average_fit = sum(fits) / len(fits) if fits else 0.0
    gaps = len(route) - len(fits)
    return average_fit - 18 * gaps - 2 * max(0, len(route) - shortest)


def pathway(quiz: dict[str, Any], programs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the best feasible, program-backed route from the athlete's current stage to her goal."""
    start = starting_stage(quiz.get("skill"), quiz.get("years_since_played"))
    goal = goal_stage(quiz.get("goal_level"), quiz.get("competitions"), quiz.get("goal_text"), start)
    routes = enumerate_routes(start, goal)
    if not routes:
        return []

    # Import lazily: fit.py reuses constants from this module.
    from app.fit import fit_catalog

    matches = fit_catalog(quiz, programs)["matches"]
    best_by_stage: dict[str, dict[str, Any]] = {}
    for match in matches:
        stage = match.get("stage")
        if stage in PATHWAY_GRAPH and stage not in best_by_stage:
            best_by_stage[stage] = match

    shortest = min(map(len, routes))
    route = min(
        routes,
        key=lambda candidate: (
            -_route_score(candidate, best_by_stage, shortest),
            len(candidate) - sum(stage in best_by_stage for stage in candidate),
            len(candidate),
            tuple(candidate),
        ),
    )

    steps = []
    for index, stage in enumerate(route):
        next_stage = route[index + 1] if index + 1 < len(route) else None
        transition = next(
            (edge for edge in PATHWAY_GRAPH[stage] if edge["to"] == next_stage),
            None,
        )
        match = best_by_stage.get(stage)
        program = None if match is None else {
            "id": match["id"],
            "name": match["name"],
            "fit": match.get("fit"),
            "distance_mi": match.get("distance_mi"),
            "cost_label": match.get("cost_label", ""),
            "website": match.get("website", ""),
        }
        label = STAGE_LABELS[stage]
        steps.append({
            "stage": stage,
            "label": label,
            "status": "current" if index == 0 else "upcoming",
            "is_goal": stage == goal,
            "program": program,
            # Retain the former compact property for clients that only need a link and name.
            "example": {"id": program["id"], "name": program["name"]} if program else None,
            "gap": None if program else f"No eligible {label.lower()} program matches your answers yet.",
            "weeks": transition["weeks"] if transition else None,
            "ready_when": (
                transition["ready_when"] if transition
                else "This is your selected goal stage; confirm entry requirements with the program."
            ),
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
        "pathway": pathway(quiz, rows),
        "top_matches": [_card_summary(r) for r in ranked if r["eligible"]][:8],
        "tips": tips,
    }
