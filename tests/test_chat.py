import json

import pytest
from fastapi.testclient import TestClient

from app import chat, db

QUIZ = {
    "sport": "soccer", "age": 12, "skill": "beginner", "competitions": ["rec_league"],
    "availability": ["Tue-evening", "Sat-morning"], "budget_usd": 300, "max_distance_mi": 25, "transport": "parent",
    "home": {"label": "Cumming", "lat": 34.207, "lng": -84.14, "country": "United States"},
    "barriers": [], "goal_level": None, "goal_text": "",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_no_key_gives_a_clear_503(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r = client.post("/api/chat", json={"quiz": QUIZ, "messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["detail"]


def test_prompt_contains_plan_data_and_rules(client, monkeypatch):
    seen = {}

    def fake_post(payload, key):
        seen.update(payload)
        return "Your best fit is on Tuesdays."

    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(chat, "_post", fake_post)
    r = client.post("/api/chat", json={"quiz": QUIZ, "messages": [
        {"role": "assistant", "content": "earlier greeting"},  # dropped: chat must start with the user
        {"role": "user", "content": "Which program fits Tuesday?"},
    ]})
    assert r.json() == {"reply": "Your best fit is on Tuesdays."}
    system = seen["messages"][0]["content"]
    assert "Never name a program" in system and "PLAN DATA" in system
    facts = json.loads(system.split("PLAN DATA (from the app's database, JSON):\n", 1)[1])
    assert facts["best_matches"], "plan data should include her real matches"
    assert [m["role"] for m in seen["messages"][1:]] == ["user"]


def test_invented_price_is_not_shown(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(chat, "_post", lambda payload, key: "That club costs $9,999 a year.")
    r = client.post("/api/chat", json={"quiz": QUIZ, "messages": [{"role": "user", "content": "How much?"}]})
    assert "$9,999" not in r.json()["reply"]


def test_last_message_must_be_hers(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    r = client.post("/api/chat", json={"quiz": QUIZ, "messages": [{"role": "assistant", "content": "hello"}]})
    assert r.status_code == 422


def test_plan_facts_never_include_typed_text():
    plan = {"profile": {"raw_query": "private words", "sport": "soccer"}, "top_matches": [], "sessions": [],
            "pathway": [], "tips": [], "events": []}
    assert "private" not in json.dumps(chat.plan_facts(plan))
