import pytest
from fastapi.testclient import TestClient

from app import db

QUIZ = {
    "sport": "soccer", "age": 14, "skill": "recreational",
    "competitions": ["rec_league", "club_travel"],
    "availability": ["Tue-evening", "Thu-evening", "Sat-morning"],
    "budget_usd": 1000, "max_distance_mi": 50, "transport": "parent",
    "home": {"label": "Dallas", "lat": 32.7767, "lng": -96.797, "country": "United States"},
    "barriers": ["cost"], "goal_level": "college", "goal_text": "",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_signup_login_profile_roundtrip(client):
    r = client.post("/api/auth/signup", json={"email": "Ana@Example.com", "password": "longenough", "name": "Ana"})
    assert r.status_code == 200
    assert client.put("/api/profile", json=QUIZ).status_code == 200
    me = client.get("/api/me").json()
    assert me["user"]["email"] == "ana@example.com" and me["profile"]["sport"] == "soccer"

    client.post("/api/auth/logout")
    assert client.get("/api/me").json()["user"] is None
    assert client.put("/api/profile", json=QUIZ).status_code == 401

    assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "wrong-pass"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "longenough"})
    assert r.json()["profile"]["age"] == 14


def test_signup_validation(client):
    assert client.post("/api/auth/signup", json={"email": "bad", "password": "longenough"}).status_code == 400
    assert client.post("/api/auth/signup", json={"email": "a@b.co", "password": "short"}).status_code == 400
    client.post("/api/auth/signup", json={"email": "a@b.co", "password": "longenough"})
    assert client.post("/api/auth/signup", json={"email": "a@b.co", "password": "longenough"}).status_code == 400


def test_plan_uses_availability_and_real_programs(client):
    plan = client.post("/api/plan", json=QUIZ).json()
    ids = {o["id"] for o in client.get("/api/opportunities").json()["opportunities"]}
    assert [s["day"] for s in plan["sessions"]] == ["Tue", "Thu", "Sat"]
    assert all(s["id"] in ids for s in plan["sessions"])
    assert plan["step_up"]["level"] == "competitive"
    assert plan["pathway"][0]["stage"] == "rec_league"
    assert plan["pathway"][-1]["stage"] == "club_league"
    assert plan["pathway"][0]["status"] == "current"
    assert plan["pathway"][-1]["is_goal"]
    assert any("Cost" in t for t in plan["tips"])


def test_pathway_steps_back_after_three_year_break(client):
    plan = client.post("/api/plan", json={**QUIZ, "years_since_played": 3}).json()
    assert plan["pathway"][0]["stage"] == "camp"


def test_bike_walk_limits_weekly_distance(client):
    quiz = {**QUIZ, "transport": "bike_walk"}
    plan = client.post("/api/plan", json=quiz).json()
    for s in plan["weekly_programs"]:
        assert s["distance"] == "Find your local chapter" or float(s["distance"].split()[0].replace(",", "")) <= 5


def test_opportunity_detail(client):
    data = client.post("/api/opportunity/dallas-cup", json=QUIZ).json()
    assert data["opportunity"]["id"] == "dallas-cup"
    assert data["pathway"][0]["stage"] == "rec_league"
    assert data["pathway"][-1]["stage"] == "club_league" and data["similar"]
    assert client.post("/api/opportunity/nope", json=QUIZ).status_code == 404
