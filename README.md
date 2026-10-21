# PlayPath

Congressional App Challenge submission by Sharanya Vats, Vanshika Pundru, Shruthi Chava, and Sahanaa Rao.

PlayPath matches women and girls with sports opportunities from schools, colleges,
recreation departments, nonprofits, clubs, and national pathways. You describe
yourself in plain English, for example *"I'm 14, play recreational soccer and want
to find travel opportunities near Dallas"*. The app extracts a profile, scores
every program in its SQLite database with a multi-factor ranking algorithm, and
plots the results on an interactive world map.

**No LLM is used.** Every recommendation is a real row in the database. Nothing
is generated.

## Screens

| Route | Screen |
|---|---|
| `#/` | Landing page: logo, navigation, purpose, why we built it, calls to action, how it works |
| `#/login`, `#/signup` | Welcome back / create account, or continue as a guest |
| `#/quiz` | 9-question onboarding: sport, age, level, competitions, weekly availability, cost, home and distance, transport, challenges and goal |
| `#/dashboard` | Weekly session cards (day, program, time slot, distance, cost), "try the next group" step-up, tips, pathway, best matches, upcoming events |
| `#/opportunity/<id>` | When, where, cost, level, map with route from home, why it matches, pathway with "You are here" and "Change my goal", similar programs |
| `#/explore` | World map plus ranked list with color modes, clustering, and heatmap |
| `#/settings` | Account (name, sign out, delete) and every quiz answer, editable |

Accounts use email and password (PBKDF2-hashed, HttpOnly session cookie, stored in SQLite).
Guests keep their answers in the browser only.

**Session times:** the database does not hold real practice schedules. The weekly
plan places programs into the time slots *you* said you're free, and tells you to
confirm the real practice times on the program's site.

## How it works

```
prompt + form ─► parser.py ─► profile ─┐
                (regex/keyword NLP)    │
                                       ▼
source CSV/JSON ─► pipeline.py ─► SQLite ─► ranking.py ─► analysis.py ─► API ─► list + map
                  extract/normalize/        9 weighted     pandas stats
                  geocode/validate/dedupe   factors + TF-IDF
```

| Module | What it does |
|---|---|
| `app/parser.py` | Rule-based extraction of age, sport, skill, travel intent, budget, distance, home city, and program type from the prompt. Unknown places are flagged and geocoded worldwide in the browser (OpenStreetMap Nominatim). |
| `app/pipeline.py` | Ingestion pipeline for new sources: extracts sport, type, ages, cost, skill, and travel from free text, geocodes, validates, dedupes, and loads into SQLite. |
| `app/recommender.py` | Content-based recommender: TF-IDF and cosine similarity. Scores prompt relevance and powers "Similar programs". |
| `app/ranking.py` | Multi-factor score (0–100) built from sport, age, skill, travel, proximity, affordability, deadline, program type, and keyword relevance. Enforces eligibility rules: age range, max distance, residency for state and city programs, and same-country for national pathways. Ineligible results are capped. |
| `app/plan.py` | Turns quiz answers into a ranking profile and weekly plan, then chooses a program-backed route through the seven pathway stages. Routes include estimated weeks and readiness notes, use feasible program fit scores, and show honest gaps when no program matches. A break longer than two years starts one stage lower. |
| `app/auth.py` | Sign up, log in, sessions, saved profiles. |
| `app/analysis.py` | Pandas analysis: score distribution, average score by type, cost bands, affordability index, country mix, and a density grid. |
| `static/app.js` | Leaflet world map with street/satellite tiles, clustering, a density heatmap, a home radius, and color modes (type / score / affordability / eligibility). |

### Scoring weights

sport 22% · proximity 18% · age 16% · skill 11% · travel 11% · cost 10% ·
keyword relevance 5% · deadline 4% · program type 3%.

Ineligible results are capped at 62. Programs that fail a residency rule are capped at 40.

## Run the full Python app

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Run the tests with `pytest`.

## Adding real opportunities

1. Fill in a CSV using `data/sources/TEMPLATE.csv`. Only `name`, `organization`,
   `website`, and either `city` or `lat`/`lng` are required. Anything left blank
   is extracted from the description where possible.
2. Dry run: `python -m app.pipeline data/sources/your_file.csv`
3. Load: `python -m app.pipeline data/sources/your_file.csv --load`

## Known limitations

- **The catalog is small and skewed.** It has 99 programs: 75 in the US and 63 for
  soccer. Many sports and most countries have very few or zero entries, so
  someone in Lagos who wants volleyball gets nothing nearby. Growing the data is
  the most important next step.
- **Costs and deadlines are approximate.** They are typical published ranges
  entered by hand, not live data. A date that has passed is rolled to next
  year's cycle and labeled "est." Users must confirm on the official site.
- **Umbrella organizations are pinned to their HQ.** AYSO, YMCA, NFHS, and national
  governing bodies run local chapters. They are treated as available anywhere in
  their country, but their map pin is the headquarters.
- **There is no live scraping.** The pipeline normalizes data you export or
  collect; it does not crawl websites.
- **Geocoding of arbitrary places uses the public Nominatim service** from the
  browser, which is rate-limited (about 1 request per second). For production,
  self-host a geocoder or use a keyed service.
