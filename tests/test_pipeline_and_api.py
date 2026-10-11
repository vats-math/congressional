from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import db
from app.analysis import affordability_index, analyze
from app.parser import parse_query
from app.pipeline import normalize, run
from app.ranking import next_deadline, rank_catalog, rank_opportunity


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_past_deadline_rolls_to_next_cycle():
    due, estimated = next_deadline("2026-06-01", today=date(2026, 10, 11))
    assert due == date(2027, 6, 1) and estimated
    due, estimated = next_deadline("2026-12-31", today=date(2026, 10, 11))
    assert due == date(2026, 12, 31) and not estimated
    assert next_deadline("rolling") == (None, False)


def test_pipeline_extracts_fields_from_free_text():
    row, problems = normalize({
        "name": "Girls Rec Volleyball",
        "organization": "Austin Parks and Recreation",
        "website": "https://example.org",
        "city": "Austin",
        "description": "Ages 9-14 recreational volleyball for girls, $60 per season",
    })
    assert row["sport"] == "volleyball"
    assert row["type"] == "recreation"
    assert (row["min_age"], row["max_age"]) == (9, 14)
    assert row["cost_usd"] == 60
    assert row["women_focused"] is True
    assert row["lat"] == pytest.approx(30.2672)
    assert "no deadline; marked rolling" in problems


def test_pipeline_rejects_and_dedupes():
    good = {"name": "A", "organization": "O", "website": "https://x", "city": "Dallas", "description": "soccer"}
    result = run([good, dict(good), {"name": "no org"}, {**good, "name": "B", "city": "Atlantis"}])
    assert len(result["rows"]) == 1
    assert result["duplicates_dropped"] == 1
    assert len(result["rejected"]) == 2


def test_state_high_school_league_is_not_eligible_far_away():
    dallas = parse_query("I'm 15 and play soccer near Dallas")
    from app.catalog import CATALOG

    georgia = next(c for c in CATALOG if c["id"] == "georgia-hs-soccer")
    result = rank_opportunity(dallas, georgia)
    assert not result["residency_ok"] and not result["eligible"]
    assert result["compatibility"] <= 40


def test_national_pathway_requires_same_country():
    from app.catalog import CATALOG

    usys = next(c for c in CATALOG if c["id"] == "usys-odp")
    us = rank_opportunity(parse_query("14 soccer near Seattle"), usys)
    uk = rank_opportunity(parse_query("14 soccer near London"), usys)
    assert us["eligible"] and not uk["eligible"]


def test_unknown_place_is_flagged_for_geocoding():
    profile = parse_query("I'm 15 and play lacrosse near Fresno")
    assert profile["place_query"] == "fresno"
    assert "lat" not in profile


def test_budget_does_not_read_miles():
    profile = parse_query("soccer under 50 miles away")
    assert "budget_usd" not in profile


def test_analysis_and_affordability():
    from app.catalog import CATALOG

    ranked = rank_catalog(parse_query("soccer"), [dict(c) for c in CATALOG])
    stats = analyze(ranked)
    assert stats["count"] == len(CATALOG)
    assert sum(stats["affordability_bands"].values()) == len(CATALOG)
    assert affordability_index(0) == 1.0 and affordability_index(None) == 0.5


def test_match_endpoint_uses_database(client):
    res = client.post("/api/match", json={
        "query": "I'm 14, play recreational soccer and want to find travel opportunities near Dallas",
        "eligible_only": True,
    })
    data = res.json()
    assert res.status_code == 200
    assert data["count"] > 0 and data["count"] <= data["catalog_size"]
    ids = {r["id"] for r in client.get("/api/opportunities").json()["opportunities"]}
    assert all(r["id"] in ids for r in data["recommendations"])  # nothing invented
    assert all(r["eligible"] for r in data["recommendations"])
    top = data["recommendations"][0]
    assert top["sport"] == "soccer" and top["is_travel"]


def test_match_requests_geocode_for_unknown_city(client):
    data = client.post("/api/match", json={"query": "volleyball", "city": "Boise, Idaho"}).json()
    assert data["needs_geocode"] == "Boise, Idaho"
    data = client.post("/api/match", json={
        "query": "volleyball", "city": "Boise", "lat": 43.6, "lng": -116.2, "country": "United States",
    }).json()
    assert data["needs_geocode"] is None
    assert data["recommendations"][0]["distance_km"] is not None


def test_similar_endpoint(client):
    data = client.get("/api/similar/dallas-cup").json()
    assert len(data["similar"]) == 5
    assert client.get("/api/similar/nope").status_code == 404
