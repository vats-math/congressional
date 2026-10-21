"""Phase 5: barrier-aware scoring, the eval set, and that the summary never sees raw text."""
from app import advisor
from app.advisor import BARRIER_TAGS, environment_score
from app.fit import BASE_WEIGHTS, DEFAULT_WEIGHTS, score_program
from app.stages import ENVIRONMENT_TAGS
from scripts.eval_advisor import evaluate, load


def test_barrier_rules_only_use_tags_that_exist_in_the_data():
    for barrier, rule in BARRIER_TAGS.items():
        assert set(rule["boost"]) | set(rule["avoid"]) <= set(ENVIRONMENT_TAGS), barrier


def test_confidence_rule_matches_the_spec():
    assert BARRIER_TAGS["confidence"] == {
        "boost": ["beginner_friendly", "no_tryouts", "girls_only", "drop_in"],
        "avoid": ["tryout_required"],
    }


def test_environment_score():
    assert environment_score(["beginner_friendly", "no_tryouts"], ["confidence"]) == 1.0
    assert environment_score(["tryout_required"], ["confidence"]) == 0.0
    assert environment_score([], ["confidence"]) == 0.5  # untagged program: neutral
    assert environment_score(["girls_only"], []) is None  # no barriers: factor left out
    assert environment_score(["girls_only"], ["transport"]) is None  # no tag rule for transport
    assert environment_score(["beginner_friendly"], ["new_to_sport"]) == environment_score(["beginner_friendly"], ["experience"])


def test_weights_still_add_to_one_with_environment():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1) < 1e-9
    assert DEFAULT_WEIGHTS["environment"] == 0.08
    for k, w in BASE_WEIGHTS.items():
        assert abs(DEFAULT_WEIGHTS[k] - w * 0.92) < 1e-9


def _program(tags):
    return {"id": "p", "name": "P", "organization": "O", "website": "w", "type": "recreation", "sport": "soccer",
            "lat": 34.2, "lng": -84.1, "min_age": 10, "max_age": 14, "skill_levels": ["beginner"], "cost_usd": 50,
            "is_travel": False, "environment": tags, "sessions": []}


def test_confirmed_confidence_barrier_ranks_friendly_program_higher():
    quiz = {"sport": "soccer", "age": 12, "skill": "beginner", "budget_usd": 100, "barriers": ["confidence"]}
    friendly = score_program(quiz, _program(["beginner_friendly", "no_tryouts"]))["fit"]
    tryouts = score_program(quiz, _program(["tryout_required"]))["fit"]
    assert friendly > tryouts
    no_barrier = {**quiz, "barriers": []}
    assert score_program(no_barrier, _program(["beginner_friendly"]))["fit"] == score_program(no_barrier, _program(["tryout_required"]))["fit"]


def test_summary_is_built_from_plan_facts_only():
    plan = {"top_matches": [{"name": "A", "compatibility": 80}], "sessions": [], "pathway": [], "tips": [],
            "profile": {"raw_query": "my secret message"}}
    assert "secret" not in str(advisor._plan_facts(plan))


def test_eval_set_loads_and_keyword_mode_runs():
    rows = load()
    assert len(rows) >= 30
    res = evaluate(rows, "keywords")
    assert res["n"] == len(rows) and 0 <= res["exact_accuracy"] <= 1
