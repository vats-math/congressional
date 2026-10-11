from app.parser import parse_query
from app.ranking import rank_opportunity


def test_soccer_travel_query_extracts_fields():
    profile = parse_query(
        "I'm 14, play recreational soccer and want to find travel opportunities near Dallas"
    )
    assert profile["age"] == 14
    assert profile["sport"] == "soccer"
    assert profile["skill"] == "recreational"
    assert profile["wants_travel"] is True
    assert profile["lat"] == 32.7767


def test_travel_club_outranks_local_rec_for_travel_intent():
    profile = {
        "age": 14,
        "sport": "soccer",
        "skill": "recreational",
        "wants_travel": True,
        "lat": 32.7767,
        "lng": -96.7970,
    }
    travel = {
        "id": "t1",
        "name": "Travel club",
        "organization": "X",
        "type": "club",
        "sport": "soccer",
        "city": "Dallas",
        "region": "TX",
        "country": "United States",
        "lat": 32.7767,
        "lng": -96.7970,
        "min_age": 13,
        "max_age": 18,
        "skill_levels": ["competitive", "elite"],
        "cost_usd": 3000,
        "cost_label": "$",
        "deadline": "2026-06-01",
        "eligibility": "girls",
        "is_travel": True,
        "women_focused": True,
        "website": "https://example.com",
        "description": "d",
        "season": "s",
    }
    rec = {**travel, "id": "r1", "name": "Local rec", "type": "recreation", "is_travel": False, "cost_usd": 80}
    assert rank_opportunity(profile, travel)["compatibility"] > rank_opportunity(profile, rec)["compatibility"]
