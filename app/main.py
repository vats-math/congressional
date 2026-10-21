from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import auth
from app.fit import fit_catalog
from app.local_data import fetch_programs, load_local
from app.analysis import affordability_index, analyze
from app.catalog import TYPE_COLORS
from app.db import fetch_all, init_db
from app.parser import parse_query, resolve_home
from app.pipeline import run as run_pipeline
from app.plan import DAYS, TIMES, TRANSPORT_WEEKLY_MI, build_plan, pathway, to_ranking_profile
from app.ranking import rank_catalog
from app.recommender import TfidfIndex

ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    load_local()
    auth.init_auth()
    yield


app = FastAPI(title="PlayPath", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))


class MatchRequest(BaseModel):
    query: str = Field(default="", max_length=1000)
    age: Optional[int] = Field(default=None, ge=3, le=80)
    sport: Optional[str] = None
    skill: Optional[str] = None
    budget_usd: Optional[int] = Field(default=None, ge=0)
    city: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    max_distance_km: Optional[float] = Field(default=None, gt=0)
    wants_travel: Optional[bool] = None
    types: list[str] = Field(default_factory=list)
    eligible_only: bool = False


def _enrich(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, "affordability": affordability_index(row.get("cost_usd"))}


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> Any:
    return templates.TemplateResponse(request, "index.html", {"type_colors": TYPE_COLORS})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/opportunities")
def list_opportunities() -> dict[str, Any]:
    rows = fetch_all()
    return {"count": len(rows), "opportunities": rows}


@app.post("/api/match")
def match(body: MatchRequest) -> dict[str, Any]:
    # Structured form fields win over whatever the prompt parser extracts.
    form = {
        "age": body.age,
        "sport": body.sport,
        "skill": body.skill,
        "budget_usd": body.budget_usd,
        "max_distance_km": body.max_distance_km,
        "wants_travel": body.wants_travel,
        **resolve_home(body.city, body.lat, body.lng, body.country),
    }
    form = {k: v for k, v in form.items() if v is not None}
    profile = parse_query(body.query, {})
    if "lat" in form:
        profile.pop("place_query", None)
    profile.update(form)
    if body.types:
        profile["intent_types"] = body.types

    rows = fetch_all()
    ranked = [_enrich(r) for r in rank_catalog(profile, rows)]
    total = len(ranked)
    if body.eligible_only:
        ranked = [r for r in ranked if r["eligible"]]
    return {
        "profile": profile,
        "count": len(ranked),
        "catalog_size": total,
        "needs_geocode": profile.get("place_query") if "lat" not in profile else None,
        "recommendations": ranked,
        "analysis": analyze(ranked),
        "source": "sqlite:data/playpath.db",
    }


@app.get("/api/similar/{opp_id}")
def similar(opp_id: str, k: int = 5) -> dict[str, Any]:
    rows = fetch_all()
    by_id = {r["id"]: r for r in rows}
    if opp_id not in by_id:
        raise HTTPException(404, "unknown opportunity")
    pairs = TfidfIndex(rows).similar(opp_id, k=max(1, min(k, 20)))
    return {
        "id": opp_id,
        "similar": [
            {"id": i, "name": by_id[i]["name"], "city": by_id[i]["city"], "type": by_id[i]["type"],
             "sport": by_id[i]["sport"], "similarity": round(s, 3)}
            for i, s in pairs
        ],
    }


@app.post("/api/pipeline/preview")
def pipeline_preview(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Dry-run the extraction pipeline on raw source records. Nothing is written."""
    if len(records) > 500:
        raise HTTPException(413, "max 500 records per preview")
    return run_pipeline(records)


# ---------- accounts, quiz profile, plan ----------


class Credentials(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)
    name: str = Field(default="", max_length=80)


class Quiz(BaseModel):
    """Everything the onboarding quiz collects. Editable later in Settings."""

    sport: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=3, le=80)
    skill: Optional[str] = None
    years_since_played: Optional[int] = Field(default=None, ge=0, le=50)
    competitions: list[str] = Field(default_factory=list)
    availability: list[str] = Field(default_factory=list)  # e.g. "Tue-evening"
    budget_usd: Optional[int] = Field(default=None, ge=0)
    max_distance_mi: Optional[float] = Field(default=None, gt=0)
    transport: Optional[str] = None
    home: dict[str, Any] = Field(default_factory=dict)  # {label, lat, lng, country}
    barriers: list[str] = Field(default_factory=list)
    goal_level: Optional[str] = None
    goal_text: str = Field(default="", max_length=500)
    ride_cutoff: Optional[str] = Field(default=None, max_length=8)  # latest time she can get a ride, e.g. "8:00 PM"


class SimulatorOverrides(BaseModel):
    """Only the quiz fields that the what-if simulator can change."""

    model_config = ConfigDict(extra="forbid")

    availability: list[str] = Field(default_factory=list)
    budget_usd: Optional[int] = Field(default=None, ge=0)
    max_distance_mi: Optional[float] = Field(default=None, gt=0)
    transport: Optional[Literal["car", "parent", "carpool", "transit", "bike_walk"]] = None

    @field_validator("availability")
    @classmethod
    def validate_availability(cls, values: list[str]) -> list[str]:
        valid = {f"{day}-{time}" for day in DAYS for time in TIMES}
        if any(value not in valid for value in values):
            raise ValueError("availability must contain valid day-time quiz slots")
        return list(dict.fromkeys(values))


class SimulateRequest(BaseModel):
    quiz: Quiz
    overrides: SimulatorOverrides = Field(default_factory=SimulatorOverrides)


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)


def _set_session(response: Response, token: str) -> None:
    response.set_cookie(
        auth.SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30
    )


def _require_user(token: Optional[str]) -> dict[str, Any]:
    user = auth.user_for(token)
    if user is None:
        raise HTTPException(401, "Sign in required")
    return user


@app.post("/api/auth/signup")
def signup(body: Credentials, response: Response) -> dict[str, Any]:
    try:
        user, token = auth.signup(body.email, body.password, body.name)
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    _set_session(response, token)
    return {"user": user, "profile": None}


@app.post("/api/auth/login")
def login(body: Credentials, response: Response) -> dict[str, Any]:
    try:
        user, token = auth.login(body.email, body.password)
    except auth.AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    _set_session(response, token)
    return {"user": user, "profile": auth.get_profile(user["id"])}


@app.post("/api/auth/logout")
def logout(response: Response, playpath_session: Optional[str] = Cookie(default=None)) -> dict[str, bool]:
    auth.logout(playpath_session)
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(playpath_session: Optional[str] = Cookie(default=None)) -> dict[str, Any]:
    user = auth.user_for(playpath_session)
    if user is None:
        return {"user": None, "profile": None}
    return {"user": user, "profile": auth.get_profile(user["id"])}


@app.put("/api/me")
def update_me(body: AccountUpdate, playpath_session: Optional[str] = Cookie(default=None)) -> dict[str, Any]:
    user = _require_user(playpath_session)
    auth.update_account(user["id"], body.name)
    return {"user": auth.user_for(playpath_session)}


@app.delete("/api/me")
def delete_me(response: Response, playpath_session: Optional[str] = Cookie(default=None)) -> dict[str, bool]:
    user = _require_user(playpath_session)
    auth.delete_account(user["id"])
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"ok": True}


@app.put("/api/profile")
def put_profile(body: Quiz, playpath_session: Optional[str] = Cookie(default=None)) -> dict[str, Any]:
    user = _require_user(playpath_session)
    auth.save_profile(user["id"], body.model_dump())
    return {"profile": body.model_dump()}


@app.post("/api/plan")
def plan(body: Quiz) -> dict[str, Any]:
    """Works for guests (profile kept in the browser) and signed-in users alike."""
    return build_plan(body.model_dump(), fetch_programs())


def _pathway_total_weeks(plan_data: dict[str, Any]) -> Optional[int]:
    """Sum the weeks of the pathway steps that have a duration (the goal step itself has none).

    None when no step has a duration, so the UI can say "unknown" instead of showing 0.
    """
    steps = plan_data.get("pathway") or []
    durations = [step["weeks"] for step in steps if isinstance(step.get("weeks"), (int, float))]
    return int(sum(durations)) if durations else None


def _best_plan_score(plan_data: dict[str, Any]) -> int:
    matches = plan_data.get("top_matches") or []
    return int(matches[0]["compatibility"]) if matches else 0


def _programs_by_id(plan_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(program["id"]): program
        for program in plan_data.get("weekly_programs", [])
        if program.get("id") is not None
    }


def _sensitivity_suggestions(
    quiz: dict[str, Any], rows: list[dict[str, Any]], baseline_score: int
) -> list[dict[str, Any]]:
    """Try one quiz change at a time and keep the largest positive score gains."""
    candidates: list[tuple[str, dict[str, Any]]] = []
    availability = list(quiz.get("availability") or [])
    available_days = {slot.partition("-")[0] for slot in availability}

    # The quiz records day/time windows rather than whole days, so test a newly
    # available day with all three windows.
    for day in DAYS:
        if day not in available_days:
            candidates.append((
                f"Add {day} availability",
                {"availability": availability + [f"{day}-{time}" for time in TIMES]},
            ))

    budget = quiz.get("budget_usd")
    costs = [row.get("cost_usd") for row in rows if isinstance(row.get("cost_usd"), (int, float))]
    if budget is not None and costs:
        max_budget = ((int(max(costs)) + 24) // 25) * 25
        next_budget = ((int(budget) // 25) + 1) * 25
        for amount in range(next_budget, max_budget + 1, 25):
            candidates.append((f"Raise budget to ${amount}", {"budget_usd": amount}))

    transport = quiz.get("transport") or "car"
    current_distance = quiz.get("max_distance_mi")
    if current_distance is None:
        current_distance = TRANSPORT_WEEKLY_MI.get(transport, 40)
    candidates.append((
        "Increase travel range by 5 miles",
        {"max_distance_mi": float(current_distance) + 5},
    ))

    if transport != "car":
        candidates.append(("Switch transport to a car", {"transport": "car"}))

    improvements = []
    for label, override in candidates:
        candidate_quiz = {**quiz, **override}
        candidate_score = _best_plan_score(build_plan(candidate_quiz, rows))
        improvement = candidate_score - baseline_score
        if improvement > 0:
            improvements.append({
                "label": label,
                "score_before": baseline_score,
                "score_after": candidate_score,
                "improvement": improvement,
                "overrides": override,
            })
    return sorted(improvements, key=lambda item: (-item["improvement"], item["label"]))[:3]


@app.post("/api/simulate")
def simulate(body: SimulateRequest) -> dict[str, Any]:
    """Compare a quiz with temporary overrides; no profile or database rows are changed."""
    quiz = body.quiz.model_dump()
    overrides = body.overrides.model_dump(exclude_unset=True)
    simulated_quiz = {**quiz, **overrides}
    rows = fetch_all()
    baseline_plan = build_plan(quiz, rows)
    simulated_plan = build_plan(simulated_quiz, rows)
    baseline_programs = _programs_by_id(baseline_plan)
    simulated_programs = _programs_by_id(simulated_plan)
    baseline_score = _best_plan_score(baseline_plan)
    simulated_score = _best_plan_score(simulated_plan)

    return {
        "diff": {
            "gained": [simulated_programs[key] for key in sorted(simulated_programs.keys() - baseline_programs.keys())],
            "lost": [baseline_programs[key] for key in sorted(baseline_programs.keys() - simulated_programs.keys())],
            "best_score_before": baseline_score,
            "best_score_after": simulated_score,
            "score_improvement": simulated_score - baseline_score,
            "sessions_before": len(baseline_plan["sessions"]),
            "sessions_after": len(simulated_plan["sessions"]),
            "pathway_weeks_before": _pathway_total_weeks(baseline_plan),
            "pathway_weeks_after": _pathway_total_weeks(simulated_plan),
        },
        "sensitivity": _sensitivity_suggestions(quiz, rows, baseline_score),
        "notes": [
            "Program listings do not include real practice times, so availability changes cannot yet affect match scores.",
        ],
    }


@app.post("/api/fit")
def fit(body: Quiz) -> dict[str, Any]:
    """OpenPlay scoring: hard filters, then a weighted fit score with a per-factor breakdown."""
    return fit_catalog(body.model_dump(), fetch_programs())

@app.post("/api/opportunity/{opp_id}")
def opportunity(opp_id: str, body: Quiz) -> dict[str, Any]:
    rows = fetch_programs()
    if opp_id not in {r["id"] for r in rows}:
        raise HTTPException(404, "unknown opportunity")
    quiz = body.model_dump()
    ranked = rank_catalog(to_ranking_profile(quiz), rows)
    item = _enrich(next(r for r in ranked if r["id"] == opp_id))
    by_id = {r["id"]: r for r in ranked}
    sims = TfidfIndex(rows).similar(opp_id, k=4)
    return {
        "opportunity": item,
        "pathway": pathway(quiz, rows),
        "similar": [
            {"id": i, "name": by_id[i]["name"], "compatibility": by_id[i]["compatibility"], "type": by_id[i]["type"]}
            for i, _ in sims
        ],
    }


@app.get("/api/geocode")
def geocode_offline(q: str) -> dict[str, Any]:
    """Offline gazetteer lookup. The browser falls back to OpenStreetMap for anything else."""
    home = resolve_home(q[:100], None, None)
    if "lat" not in home:
        return {"found": False}
    return {"found": True, "lat": home["lat"], "lng": home["lng"], "label": home["home_label"],
            "country": home["home_country"]}
