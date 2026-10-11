"""The GitHub Pages build re-implements the engine in JS (docs/engine.js). Check it matches Python."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.catalog import CATALOG
from app.parser import parse_query
from app.plan import build_plan
from app.pipeline import run
from app.ranking import rank_catalog

ROOT = Path(__file__).resolve().parent.parent
QUERIES = [
    "I'm 14, play recreational soccer and want to find travel opportunities near Dallas",
    "15, competitive soccer player in London, under $500",
    "16 year old basketball player in Phoenix within 50 miles",
    "im 12 and want to try volleyball near Lagos",
    "",
]
QUIZ = {
    "sport": "soccer", "age": 14, "skill": "recreational", "competitions": ["rec_league", "club_travel"],
    "availability": ["Tue-evening", "Thu-evening", "Sat-morning"], "budget_usd": 1000, "max_distance_mi": 50,
    "transport": "parent", "home": {"label": "Dallas", "lat": 32.7767, "lng": -96.797, "country": "United States"},
    "barriers": ["cost"], "goal_level": "college", "goal_text": "speed and footwork",
}

JS = """
global.window = {};
eval(require('fs').readFileSync('docs/data.js', 'utf8'));
eval(require('fs').readFileSync('docs/engine.js', 'utf8'));
const E = window.PlayPathEngine;
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = { ranks: input.queries.map((q) => Object.fromEntries(E.rankCatalog(E.parseQuery(q)).map((r) => [r.id, r.compatibility]))),
  plan: E.buildPlan(input.quiz) };
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_engine_matches_python():
    rows = run([{**c, "source": "catalog"} for c in CATALOG])["rows"]
    proc = subprocess.run(["node", "-e", JS], cwd=ROOT, input=json.dumps({"queries": QUERIES, "quiz": QUIZ}),
                          capture_output=True, text=True, check=True)
    js = json.loads(proc.stdout)
    for q, js_scores in zip(QUERIES, js["ranks"]):
        py = {r["id"]: r["compatibility"] for r in rank_catalog(parse_query(q), rows)}
        diffs = {k: (py[k], js_scores[k]) for k in py if abs(py[k] - js_scores[k]) > 1}  # allow rounding ties
        assert not diffs, f"{q!r}: {diffs}"
    py_plan = build_plan(QUIZ, rows)
    assert [s["id"] for s in js["plan"]["sessions"]] == [s["id"] for s in py_plan["sessions"]]
    assert [p["status"] for p in js["plan"]["pathway"]] == [p["status"] for p in py_plan["pathway"]]


def test_docs_data_is_current():
    from scripts.export_static import data_js

    assert (ROOT / "docs" / "data.js").read_text(encoding="utf-8") == data_js(), "run: python scripts/export_static.py"


def test_docs_app_js_is_current():
    assert (ROOT / "docs" / "app.js").read_text() == (ROOT / "static" / "app.js").read_text(), "run: python scripts/export_static.py"
