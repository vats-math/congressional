"""Tests for app/fit.py: hard filters, schedule math, weights, and the /api/fit endpoint."""
import copy

import pytest

from app import db
from app.fit import (DEFAULT_WEIGHTS, availability_windows, combine, feasibility, fit_catalog, overlap_minutes,
                     schedule_score, score_program, session_fit)

HOME = {"lat": 34.20, "lng": -84.14, "country": "United States"}


def program(**over):
    base = {
        "id": "p1", "name": "Test Program", "organization": "Test Org", "website": "https://x.org",
        "type": "recreation", "sport": "soccer", "lat": 34.20, "lng": -84.14, "country": "United States",
        "min_age": 10, "max_age": 16, "skill_levels": ["beginner"], "is_travel": False, "cost_usd": 50,
        "cost_label": "$50", "stage": "rec_league", "environment": [], "status": "open", "status_note": "",
        "source_url": "", "last_verified": "2026-10-19",
        "sessions": [{"weekday": 1, "start_minute": 17 * 60 + 30, "end_minute": 18 * 60 + 30, "drop_in": False}],
    }
    base.update(over)
    return base


QUIZ = {"sport": "soccer", "age": 13, "skill": "beginner", "competitions": ["rec_league"],
        "availability": ["Tue-evening"], "budget_usd": 100, "max_distance_mi": 10, "transport": "parent", "home": HOME}


def codes(quiz, prog, **kw):
    return {r["code"] for r in feasibility(quiz, prog, **kw)[1]}


def test_overlap_minutes():
    assert overlap_minutes(0, 60, 30, 90) == 30
    assert overlap_minutes(0, 60, 60, 120) == 0  # touching is not overlapping
    assert overlap_minutes(0, 60, 100, 200) == 0


def test_availability_windows_ignores_garbage():
    assert availability_windows(["Tue-evening", "Funday-morning", "Sat-brunch", "nonsense"]) == {1: [(1020, 1260)]}


def test_session_fit_partial_and_full():
    windows = availability_windows(["Tue-evening"])  # 17:00-21:00
    assert session_fit({"weekday": 1, "start_minute": 1050, "end_minute": 1110}, windows) == 1.0
    assert session_fit({"weekday": 1, "start_minute": 960, "end_minute": 1080}, windows) == pytest.approx(0.5)  # 16-18h
    assert session_fit({"weekday": 2, "start_minute": 1050, "end_minute": 1110}, windows) == 0.0  # wrong day


def test_schedule_score_rewards_attending_every_session():
    windows = availability_windows(["Tue-evening", "Thu-evening"])
    tue = {"weekday": 1, "start_minute": 1050, "end_minute": 1110}
    thu = {"weekday": 3, "start_minute": 1050, "end_minute": 1110}
    mon = {"weekday": 0, "start_minute": 1050, "end_minute": 1110}
    both, _ = schedule_score([tue, thu], windows)
    half, _ = schedule_score([tue, mon], windows)
    assert both == pytest.approx(1.0) and half == pytest.approx(0.85)
    assert schedule_score([], windows) == (0.5, None)  # unknown schedule is neutral


def test_a_program_that_fits_is_feasible():
    assert feasibility(QUIZ, program()) == (True, [])


@pytest.mark.parametrize("over,code", [
    ({"sport": "tennis"}, "sport"),
    ({"min_age": 14, "max_age": 18}, "age"),
    ({"status": "closed", "status_note": "Closed."}, "closed"),
    ({"lat": 34.60}, "distance"),
    ({"sessions": [{"weekday": 4, "start_minute": 1050, "end_minute": 1110, "drop_in": False}]}, "schedule"),
])
def test_hard_filters(over, code):
    assert code in codes(QUIZ, program(**over))


def test_closed_programs_can_be_included_on_request():
    assert feasibility(QUIZ, program(status="closed"), include_closed=True)[0]


def test_transport_cap_and_ride_cutoff():
    far = program(lat=34.20 + 0.15)  # about 10 miles north
    assert "transport" in codes({**QUIZ, "transport": "bike_walk", "max_distance_mi": 20}, far)
    assert "ride_cutoff" in codes({**QUIZ, "ride_cutoff": "6:00 PM"}, program())  # ends 6:30 PM
    assert "ride_cutoff" not in codes({**QUIZ, "ride_cutoff": "7:00 PM"}, program())


def test_unknown_schedule_is_not_filtered_but_is_flagged():
    prog = program(sessions=[])
    assert feasibility(QUIZ, prog)[0]
    scored = score_program(QUIZ, prog)
    assert scored["schedule_known"] is False and scored["breakdown"]["schedule"] == 0.5


def test_every_failed_check_is_reported():
    assert {"sport", "age"} <= codes(QUIZ, program(sport="tennis", min_age=14, max_age=18))


def test_a_closer_program_never_scores_lower():
    near = score_program(QUIZ, program(lat=34.201))["fit"]
    mid = score_program(QUIZ, program(lat=34.24))["fit"]
    far = score_program(QUIZ, program(lat=34.28))["fit"]
    assert near >= mid >= far


def test_a_cheaper_program_never_scores_lower():
    assert score_program(QUIZ, program(cost_usd=10))["fit"] >= score_program(QUIZ, program(cost_usd=90))["fit"]


def test_weights_add_up_to_one_after_rescaling():
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)
    full = score_program(QUIZ, program())
    assert sum(full["weights_used"].values()) == pytest.approx(1.0, abs=0.01)
    sparse = score_program({"sport": "soccer", "age": 13}, program())  # she skipped most questions
    assert set(sparse["breakdown"]) == {"age"}
    assert sum(sparse["weights_used"].values()) == pytest.approx(1.0)


def test_combine_is_a_weighted_average():
    raw, used = combine({"schedule": 1.0, "age": 0.0}, {"schedule": 0.25, "age": 0.05})
    assert raw == pytest.approx(0.25 / 0.30) and sum(used.values()) == pytest.approx(1.0)


def test_custom_weights_change_the_score():
    quiz = {**QUIZ, "availability": ["Tue-evening"]}
    prog = program(cost_usd=95)
    base = score_program(quiz, prog)["fit"]
    only_schedule = score_program(quiz, prog, weights={"schedule": 1.0})["fit"]
    assert only_schedule == 100 and base != only_schedule


def test_fit_catalog_sorts_and_explains():
    good = program(id="good", name="Good")
    wrong_sport = program(id="bad", name="Bad", sport="tennis")
    better = program(id="better", name="Better", cost_usd=10)  # same place, cheaper
    out = fit_catalog(QUIZ, [good, wrong_sport, better])
    assert [m["id"] for m in out["matches"]] == ["better", "good"]
    assert out["filtered_out"][0]["id"] == "bad" and out["filtered_out"][0]["reasons"][0]["code"] == "sport"


def test_fit_catalog_does_not_mutate_its_input():
    progs = [program()]
    before = copy.deepcopy(progs)
    fit_catalog(QUIZ, progs)
    assert progs == before


def test_a_recreational_league_run_by_a_club_counts_as_recreation():
    club_run = score_program(QUIZ, program(type="club", stage="rec_league"))
    assert club_run["breakdown"]["competitive"] == pytest.approx(0.975)


def test_national_organizations_do_not_get_a_bogus_transport_penalty():
    from app.catalog import SCOPE_NATIONAL

    national = program(id=sorted(SCOPE_NATIONAL)[0], lat=40.7, lng=-74.0)  # headquarters far away
    assert score_program(QUIZ, national)["breakdown"]["transport"] == 0.5


def test_api_fit_endpoint(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    from app.main import app

    quiz = {**QUIZ, "home": {"lat": 34.185, "lng": -84.215, "country": "United States", "label": "Cumming"}}
    quiz.pop("sport")
    quiz["sport"] = "soccer"
    with TestClient(app) as client:
        r = client.post("/api/fit", json=quiz)
        assert r.status_code == 200
        body = r.json()
        assert set(body) == {"matches", "filtered_out", "weights"}
        assert all({"fit", "breakdown", "weights_used"} <= set(m) for m in body["matches"])
        fits = [m["fit"] for m in body["matches"]]
        assert fits == sorted(fits, reverse=True)
        assert all(f["reasons"] for f in body["filtered_out"])
        assert client.post("/api/fit", json={**quiz, "age": 1}).status_code == 422  # Quiz validation still applies
