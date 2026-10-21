from app.plan import enumerate_routes, goal_stage, pathway, starting_stage


def test_start_stage_uses_experience_and_long_break():
    assert starting_stage("beginner") == "intro_clinic"
    assert starting_stage("recreational", 2) == "rec_league"
    assert starting_stage("recreational", 3) == "camp"
    assert starting_stage("beginner", 8) == "intro_clinic"


def test_goal_stage_uses_goal_and_competition_preference():
    assert goal_stage("recreational") == "rec_league"
    assert goal_stage("competitive", ["school_team"]) == "school_team"
    assert goal_stage("competitive", ["club_travel"]) == "club_league"
    assert goal_stage(None, ["college_recruiting"]) == "club_league"
    assert goal_stage(None, [], "I want to make the school team") == "school_team"


def test_route_enumeration_is_forward_and_includes_alternatives():
    routes = enumerate_routes("intro_clinic", "rec_league")
    assert {tuple(route) for route in routes} == {
        ("intro_clinic", "open_play", "rec_league"),
        ("intro_clinic", "open_play", "camp", "rec_league"),
        ("intro_clinic", "camp", "rec_league"),
    }
    assert enumerate_routes("club_league", "rec_league") == [["club_league"]]


def test_pathway_picks_the_route_with_better_feasible_programs(monkeypatch):
    import app.fit

    matches = [
        {"id": "rec", "name": "Rec", "stage": "rec_league", "fit": 80},
        {"id": "intermediate", "name": "Intermediate", "stage": "intermediate_group", "fit": 95},
        {"id": "school", "name": "School", "stage": "school_team", "fit": 10},
        {"id": "club", "name": "Club", "stage": "club_league", "fit": 90},
    ]
    monkeypatch.setattr(app.fit, "fit_catalog", lambda quiz, programs: {"matches": matches})

    steps = pathway(
        {"skill": "recreational", "goal_level": "college", "competitions": ["club_travel"]},
        [],
    )

    assert [step["stage"] for step in steps] == ["rec_league", "intermediate_group", "club_league"]
    assert steps[0]["program"]["id"] == "rec"
    assert steps[0]["weeks"] == 8
    assert steps[0]["ready_when"]
    assert steps[-1]["is_goal"] and steps[-1]["weeks"] is None


def test_pathway_marks_missing_stage_program_as_a_gap(monkeypatch):
    import app.fit

    monkeypatch.setattr(app.fit, "fit_catalog", lambda quiz, programs: {"matches": []})
    steps = pathway(
        {"skill": "recreational", "goal_level": "competitive", "competitions": ["school_team"]},
        [],
    )

    assert [step["stage"] for step in steps] == ["rec_league", "school_team"]
    assert steps[-1]["program"] is None
    assert steps[-1]["gap"] == "No eligible school team program matches your answers yet."
