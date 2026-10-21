"""OpenPlay fit score: hard filters first, then a weighted score for whatever is left.

    feasibility(quiz, program)      -> (True, [])  or  (False, [{"code": ..., "detail": ...}, ...])
    score_program(quiz, program)    -> fit 0-100 plus a per-factor breakdown (each factor 0-1)
    fit_catalog(quiz, programs)     -> {"matches": [...best first], "filtered_out": [...with reasons]}

Why two stages: a "92% match" for a program she cannot attend would be a lie, so anything she
cannot do (wrong sport, too young, no session fits her week, too far, registration closed) is removed
and *explained*, never ranked. The what-if simulator later reuses those reasons.

Weights are an argument, not a constant buried in the code, so the simulator can change them.
Questions she did not answer drop out and the remaining weights are rescaled to add up to 1.
The score is a "fit", not a probability.
"""
from __future__ import annotations

from typing import Any

from app.advisor import add_environment_weight, environment_score
from app.catalog import ADAPTIVE_ONLY, scope_for
from app.local_data import parse_clock
from app.plan import COMPETITION_TYPES, KM_PER_MI, TRANSPORT_WEEKLY_MI, TRAVEL_COMPETITIONS
from app.ranking import (_affordability_score, _age_score, _clamp, _proximity_score, _skill_score,
                         _travel_score, _type_intent_score, haversine_km)
from app.stages import WEEKDAY_NAMES, WEEKDAYS

BASE_WEIGHTS: dict[str, float] = {
    "schedule": 0.25,
    "distance": 0.20,
    "budget": 0.15,
    "experience": 0.15,
    "transport": 0.10,
    "competitive": 0.10,
    "age": 0.05,
}
# Phase 5: "environment" (do the program's tags suit the barriers she confirmed?) takes 8%, and every
# other weight shrinks by 8% so the total is still 1. With no confirmed barriers the environment factor
# is simply absent and combine() rescales the rest, so scores are unchanged for her.
DEFAULT_WEIGHTS: dict[str, float] = add_environment_weight(BASE_WEIGHTS, share=0.08)
assert abs(sum(DEFAULT_WEIGHTS.values()) - 1) < 1e-9

FACTOR_LABELS = {
    "schedule": "fits your week", "distance": "close to you", "budget": "fits your budget",
    "experience": "right level", "transport": "easy to get to", "competitive": "right intensity",
    "age": "right age group", "environment": "suits what makes playing hard for you",
}

# What each availability choice in the quiz means, in minutes after midnight. The three windows touch,
# so no hour of the afternoon is lost between them.
SLOT_WINDOWS = {"morning": (7 * 60, 12 * 60), "afternoon": (12 * 60, 17 * 60), "evening": (17 * 60, 21 * 60)}

UNKNOWN = 0.5  # neutral score when the program has not published the fact (schedule, cost)

# A club can run a purely recreational league. For "what intensity does she want", the stage wins over the
# organization type.
STAGE_INTENSITY_TYPE = {"intro_clinic": "recreation", "open_play": "recreation", "camp": "recreation",
                        "rec_league": "recreation", "school_team": "school", "club_league": "club"}


# ------------------------------------------------------------------ schedule helpers

def overlap_minutes(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    """Minutes two time ranges share (0 when they do not touch)."""
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def availability_windows(availability: list[str]) -> dict[int, list[tuple[int, int]]]:
    """['Tue-evening', 'Sat-morning'] -> {1: [(1020, 1260)], 5: [(420, 720)]}. Unreadable slots are ignored."""
    windows: dict[int, list[tuple[int, int]]] = {}
    for slot in availability or []:
        day, _, part = slot.partition("-")
        if day[:3].lower() in WEEKDAYS and part in SLOT_WINDOWS:
            windows.setdefault(WEEKDAYS[day[:3].lower()], []).append(SLOT_WINDOWS[part])
    return windows


def session_fit(session: dict[str, Any], windows: dict[int, list[tuple[int, int]]]) -> float:
    """Share of one session (0-1) that falls inside the times she is free on that weekday."""
    length = session["end_minute"] - session["start_minute"]
    covered = sum(overlap_minutes(session["start_minute"], session["end_minute"], lo, hi)
                  for lo, hi in windows.get(session["weekday"], []))
    return min(1.0, covered / length) if length > 0 else 0.0


def schedule_score(sessions: list[dict[str, Any]], windows: dict[int, list[tuple[int, int]]],
                   ) -> tuple[float, dict[str, Any] | None]:
    """70% how well her best session fits + 30% how many of the weekly sessions she could attend fully.

    The second part matters because teams usually expect every practice, not just one.
    Returns (score, best_session). A program with no published sessions scores neutral.
    """
    if not sessions:
        return UNKNOWN, None
    fits = [session_fit(s, windows) for s in sessions]
    best = max(fits)
    attend_share = sum(1 for f in fits if f >= 0.99) / len(fits)
    return 0.7 * best + 0.3 * attend_share, sessions[fits.index(best)]


def fmt_minute(minute: int) -> str:
    hour, mins = divmod(minute, 60)
    return f"{(hour % 12) or 12}:{mins:02d} {'AM' if hour < 12 else 'PM'}"


def describe_session(s: dict[str, Any]) -> str:
    return f"{WEEKDAY_NAMES[s['weekday']]} {fmt_minute(s['start_minute'])}-{fmt_minute(s['end_minute'])}"


def _cutoff_minutes(quiz: dict[str, Any]) -> int | None:
    """'Latest time I can get a ride' (quiz field ride_cutoff, e.g. '8:00 PM'). Unreadable -> ignored."""
    raw = quiz.get("ride_cutoff")
    if not raw:
        return None
    try:
        return parse_clock(raw)
    except ValueError:
        return None


# ------------------------------------------------------------------ distance

def _home(quiz: dict[str, Any]) -> tuple[float, float] | None:
    home = quiz.get("home") or {}
    if home.get("lat") is not None and home.get("lng") is not None:
        return float(home["lat"]), float(home["lng"])
    return None


def _distance_km(quiz: dict[str, Any], program: dict[str, Any]) -> float | None:
    home = _home(quiz)
    if home is None:
        return None
    return haversine_km(home[0], home[1], program["lat"], program["lng"])


# ------------------------------------------------------------------ stage 1: hard filters

def feasibility(quiz: dict[str, Any], program: dict[str, Any], include_closed: bool = False,
                ) -> tuple[bool, list[dict[str, str]]]:
    """Can she realistically do this program? Returns (ok, reasons it is not). Every failed check is listed."""
    why: list[dict[str, str]] = []

    def no(code: str, detail: str) -> None:
        why.append({"code": code, "detail": detail})

    scope, scope_km = scope_for(program["id"])
    if scope == "resource":
        no("resource", "This is an information resource, not a program you can join.")
    if program["id"] in ADAPTIVE_ONLY and "disability" not in (quiz.get("barriers") or []):
        no("adaptive_only", "This program is for athletes with disabilities.")

    sport = quiz.get("sport")
    if sport and sport != "multi" and program["sport"] not in (sport, "multi"):
        no("sport", f"This is {program['sport']}, not {sport}.")

    age = quiz.get("age")
    if age is not None and not program["min_age"] <= age <= program["max_age"]:
        no("age", f"Ages {program['min_age']}-{program['max_age']} only.")

    if program.get("status") == "closed" and not include_closed:
        no("closed", program.get("status_note") or "Registration is closed right now.")

    km = _distance_km(quiz, program)
    max_km = float(quiz["max_distance_mi"]) * KM_PER_MI if quiz.get("max_distance_mi") else None
    if scope == "national":
        home_country = (quiz.get("home") or {}).get("country")
        if home_country and home_country != program["country"]:
            no("distance", "This organization does not serve your country.")
    elif scope == "regional" and km is not None and km > (scope_km or 0):
        no("distance", "Outside the area this program serves.")
    elif km is not None:
        miles = km / KM_PER_MI
        if max_km and km > max_km:
            no("distance", f"{miles:.1f} mi away, farther than your {float(quiz['max_distance_mi']):g} mi limit.")
        cap = TRANSPORT_WEEKLY_MI.get(quiz.get("transport") or "")
        if cap and miles > cap:
            no("transport", f"{miles:.1f} mi is too far for a weekly trip without a car ({cap} mi).")

    sessions = program.get("sessions") or []
    windows = availability_windows(quiz.get("availability") or [])
    if windows and sessions and all(session_fit(s, windows) == 0 for s in sessions):
        times = ", ".join(describe_session(s) for s in sessions[:3])
        no("schedule", f"It meets {times}, and none of that overlaps the times you are free.")

    cutoff = _cutoff_minutes(quiz)
    if cutoff is not None and sessions and all(s["end_minute"] > cutoff for s in sessions):
        no("ride_cutoff", f"Every session ends after {fmt_minute(cutoff)}, when your ride is gone.")

    return (not why), why


# ------------------------------------------------------------------ stage 2: the score

def _transport_factor(quiz: dict[str, Any], program: dict[str, Any], km: float | None) -> float:
    """How easy the trip is for the way she travels. 1.0 up to half her mode's range, falling to 0 at the range."""
    if scope_for(program["id"])[0] == "national":
        return UNKNOWN  # you join a local chapter; the headquarters pin says nothing about your trip
    score = 1.0
    cap = TRANSPORT_WEEKLY_MI.get(quiz.get("transport") or "")
    if cap and km is not None:
        miles = km / KM_PER_MI
        score = 1.0 if miles <= cap / 2 else _clamp(1.0 - (miles - cap / 2) / (cap / 2))
    cutoff = _cutoff_minutes(quiz)
    if cutoff is not None and not (program.get("sessions") or []):
        score = min(score, 0.6)  # she has a ride deadline but we do not know when sessions end
    return score


def _factors(quiz: dict[str, Any], program: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
    """Every factor she gave enough information for, each 0-1, plus details for the UI."""
    factors: dict[str, float] = {}
    info: dict[str, Any] = {"best_session": None}
    km = _distance_km(quiz, program)
    scope, _ = scope_for(program["id"])

    windows = availability_windows(quiz.get("availability") or [])
    if windows:
        factors["schedule"], info["best_session"] = schedule_score(program.get("sessions") or [], windows)

    if km is not None:
        score, _, _ = _proximity_score(_home(quiz), program["lat"], program["lng"],
                                       float(quiz["max_distance_mi"]) * KM_PER_MI if quiz.get("max_distance_mi") else None)
        factors["distance"] = max(score, 0.85) if scope == "national" else score

    if quiz.get("budget_usd") is not None:
        cost = program.get("cost_usd")
        factors["budget"] = UNKNOWN if cost is None else _affordability_score(quiz["budget_usd"], cost)

    if quiz.get("skill"):
        comps = set(quiz.get("competitions") or [])
        factors["experience"] = _skill_score(quiz["skill"], program["skill_levels"],
                                             bool(TRAVEL_COMPETITIONS & comps) if comps else None)

    if quiz.get("transport") or quiz.get("ride_cutoff"):
        factors["transport"] = _transport_factor(quiz, program, km)

    comps = quiz.get("competitions") or []
    if comps:
        intents = [COMPETITION_TYPES[c] for c in comps if c in COMPETITION_TYPES] or None
        wants_travel = bool(TRAVEL_COMPETITIONS & set(comps))
        kind = STAGE_INTENSITY_TYPE.get(program.get("stage") or "", program["type"])
        factors["competitive"] = (_travel_score(wants_travel, program["is_travel"], kind)
                                  + _type_intent_score(intents, kind)) / 2

    if quiz.get("age") is not None:
        factors["age"] = _age_score(quiz["age"], program["min_age"], program["max_age"])[0]

    env = environment_score(program.get("environment") or [], quiz.get("barriers") or [])
    if env is not None:
        factors["environment"] = env
    return factors, info


def combine(factors: dict[str, float], weights: dict[str, float]) -> tuple[float, dict[str, float]]:
    """Weighted average over the factors present. Returns (0-1 score, the rescaled weights that add up to 1)."""
    used = {k: weights.get(k, 0.0) for k in factors if weights.get(k, 0.0) > 0}
    total = sum(used.values())
    if total == 0:
        return 0.5, {}
    rescaled = {k: w / total for k, w in used.items()}
    return sum(factors[k] * w for k, w in rescaled.items()), rescaled


def score_program(quiz: dict[str, Any], program: dict[str, Any],
                  weights: dict[str, float] | None = None) -> dict[str, Any]:
    """Fit score (0-100) with a per-factor breakdown. Call feasibility() first; this never filters."""
    factors, info = _factors(quiz, program)
    raw, rescaled = combine(factors, weights or DEFAULT_WEIGHTS)
    km = _distance_km(quiz, program)
    sessions = program.get("sessions") or []
    windows = availability_windows(quiz.get("availability") or [])
    return {
        "id": program["id"], "name": program["name"], "organization": program["organization"],
        "website": program["website"], "type": program["type"], "sport": program["sport"],
        "stage": program.get("stage"), "environment": program.get("environment", []),
        "status": program.get("status", "unknown"), "status_note": program.get("status_note", ""),
        "source_url": program.get("source_url", ""), "last_verified": program.get("last_verified", ""),
        "cost_usd": program.get("cost_usd"), "cost_label": program.get("cost_label", ""),
        "distance_mi": None if km is None else round(km / KM_PER_MI, 1),
        "fit": round(100 * raw),
        "breakdown": {k: round(v, 3) for k, v in factors.items()},
        "weights_used": {k: round(w, 3) for k, w in rescaled.items()},
        "why": [FACTOR_LABELS[k] for k, v in factors.items() if v >= 0.85],
        "weak": [FACTOR_LABELS[k] for k, v in factors.items() if v < 0.4],
        "schedule_known": bool(sessions),
        "cost_known": program.get("cost_usd") is not None,
        "best_session": None if info["best_session"] is None else {**info["best_session"],
                                                                   "label": describe_session(info["best_session"])},
        "sessions": [{**s, "label": describe_session(s), "fits": round(session_fit(s, windows), 2) if windows else None}
                     for s in sessions],
    }


def fit_catalog(quiz: dict[str, Any], programs: list[dict[str, Any]],
                weights: dict[str, float] | None = None, include_closed: bool = False) -> dict[str, Any]:
    """Filter, then score and sort. 'filtered_out' says exactly why each removed program was removed."""
    matches, removed = [], []
    for program in programs:
        ok, reasons = feasibility(quiz, program, include_closed)
        if ok:
            matches.append(score_program(quiz, program, weights))
        else:
            removed.append({"id": program["id"], "name": program["name"], "reasons": reasons})
    matches.sort(key=lambda m: (-m["fit"], m["distance_mi"] is None, m["distance_mi"] or 0, m["name"]))
    return {"matches": matches, "filtered_out": removed, "weights": weights or DEFAULT_WEIGHTS}
