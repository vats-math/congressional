from __future__ import annotations

import re
from typing import Any

from app.catalog import CITIES

SPORT_ALIASES = {
    "soccer": {"soccer", "football", "futbol", "fútbol", "footy", "goalkeeper"},
    "basketball": {"basketball", "hoops", "bball", "wnba"},
    "volleyball": {"volleyball", "vb"},
    "softball": {"softball", "fastpitch"},
    "tennis": {"tennis"},
    "swimming": {"swimming", "swim", "swimmer", "aquatic"},
    "track": {"track", "running", "runner", "sprinter", "cross country", "xc", "5k"},
    "lacrosse": {"lacrosse", "lax"},
    "field hockey": {"field hockey"},
    "hockey": {"hockey", "ice hockey"},
    "golf": {"golf", "golfer"},
    "gymnastics": {"gymnastics", "gymnast"},
    "wrestling": {"wrestling", "wrestle", "wrestler"},
    "rugby": {"rugby"},
    "netball": {"netball"},
    "multi": {"sport", "sports", "athlete", "multi"},
}

SKILL_PATTERNS = [
    ("elite", r"\b(elite|odp|national team|academy|high[-\s]?performance)\b"),
    ("competitive", r"\b(competitive|club|travel team|select|showcase)\b"),
    ("college", r"\b(college[-\s]level|ncaa|d1|division\s?i)\b"),
    ("recreational", r"\b(recreational|rec\b|casual|fun|beginner-friendly)\b"),
    ("beginner", r"\b(beginner|new to|never played|just starting)\b"),
]


def _find_sport(text: str) -> str | None:
    for sport, aliases in SPORT_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", text):
                return sport
    return None


def _find_age(text: str) -> int | None:
    match = re.search(r"\b(?:i(?:['’]?m| am)?|age)\s*(\d{1,2})\b", text)
    if match:
        age = int(match.group(1))
        return age if 3 <= age <= 80 else None
    match = re.search(r"\b(\d{1,2})\s*(?:years?\s*old|yo)\b", text)
    if match:
        age = int(match.group(1))
        return age if 3 <= age <= 80 else None
    return None


def _find_skill(text: str) -> str | None:
    for skill, pattern in SKILL_PATTERNS:
        if re.search(pattern, text, re.I):
            return skill
    return None


def _find_travel(text: str) -> bool | None:
    if re.search(r"\b(travel|showcase|tournament|odp|national|away|id camp)\b", text, re.I):
        return True
    if re.search(r"\b(local only|stay local|no travel|recreational only)\b", text, re.I):
        return False
    return None


def _find_budget(text: str) -> int | None:
    match = re.search(r"\$\s?(\d{2,5})", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(?:under|below|less than|max)\s+(\d{2,5})(?!\s*(?:miles?|mi|km|kilomet))\b", text)
    if match:
        return int(match.group(1))
    if re.search(r"\b(free|no cost|low[-\s]?cost|affordable)\b", text, re.I):
        return 200
    return None


def _find_distance_km(text: str) -> float | None:
    miles = re.search(r"within\s+(\d{1,4})\s*(?:miles?|mi)\b", text, re.I)
    if miles:
        return float(miles.group(1)) * 1.60934
    km = re.search(r"within\s+(\d{1,4})\s*km\b", text, re.I)
    if km:
        return float(km.group(1))
    return None


def _find_city(text: str) -> dict | None:
    for city in sorted(CITIES, key=lambda c: len(c["name"]), reverse=True):
        if re.search(rf"\b{re.escape(city['name'])}\b", text):
            return city
    return None


PLACE_STOP = r"(?:\s+(?:and|but|for|to|with|who|that|within|under|looking|want|wants|play|playing|i|im)\b|[,.;!?]|$)"


def _find_place_phrase(text: str) -> str | None:
    """Unknown place after 'near/in/around/from' -> handed to the geocoder."""
    m = re.search(rf"\b(?:near|around|in|from|close to)\s+([a-z][a-z .'-]{{2,40}}?){PLACE_STOP}", text)
    if not m:
        return None
    place = m.group(1).strip()
    if place in {"the area", "my area", "town", "high school", "college", "school"}:
        return None
    return place


def _intent_types(text: str) -> list[str]:
    mapping = [
        ("college", r"\b(college|ncaa|university|scholarship)\b"),
        ("school", r"\b(high school|school team|hs\b)\b"),
        ("recreation", r"\b(rec|parks?|ymca|ayso)\b"),
        ("nonprofit", r"\b(nonprofit|free program|community)\b"),
        ("club", r"\b(club team|academy|travel team)\b"),
        ("national", r"\b(national|odp|federation|tournament)\b"),
    ]
    found = [key for key, pat in mapping if re.search(pat, text, re.I)]
    return found


def parse_query(query: str, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rule-based extraction pipeline (not an LLM). Overlay extracted fields on a profile."""
    profile = dict(base or {})
    text = (query or "").strip().lower()
    if not text:
        return profile

    sport = _find_sport(text)
    if sport:
        profile["sport"] = sport
    age = _find_age(text)
    if age is not None:
        profile["age"] = age
    skill = _find_skill(text)
    if skill:
        profile["skill"] = skill
    travel = _find_travel(text)
    if travel is not None:
        profile["wants_travel"] = travel
    budget = _find_budget(text)
    if budget is not None:
        profile["budget_usd"] = budget
    dist = _find_distance_km(text)
    if dist is not None:
        profile["max_distance_km"] = dist
    city = _find_city(text)
    if city and profile.get("lat") is None:
        profile["lat"] = city["lat"]
        profile["lng"] = city["lng"]
        profile["home_label"] = city["name"].title()
        profile["home_country"] = city["country"]
    elif not city and profile.get("lat") is None:
        place = _find_place_phrase(text)
        if place:
            profile["place_query"] = place
    if re.search(r"\b(disabilit\w*|adaptive|special olympics|para[-\s]?athlete|intellectual)\b", text):
        profile["adaptive"] = True
    types = _intent_types(text)
    if types:
        profile["intent_types"] = types
    profile["raw_query"] = query
    return profile


def resolve_home(
    city_query: str | None,
    lat: float | None,
    lng: float | None,
    country: str | None = None,
) -> dict[str, Any]:
    if lat is not None and lng is not None:
        return {
            "lat": lat,
            "lng": lng,
            "home_label": city_query or "Your location",
            "home_country": country,
        }
    if city_query:
        city = _find_city(city_query.lower())
        if city:
            return {
                "lat": city["lat"],
                "lng": city["lng"],
                "home_label": city["name"].title(),
                "home_country": city["country"],
            }
        return {"place_query": city_query.strip()}
    return {}
