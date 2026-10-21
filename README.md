# PlayPath

Congressional App Challenge submission by Sharanya Vats, Vanshika Pundru, Shruthi Chava, and Sahanaa Rao.

PlayPath helps girls and women find sports programs they can actually join: school teams,
rec leagues, clubs, camps, nonprofits, and college pathways. An athlete answers a short quiz
(sport, age, level, free time, budget, how she gets around, what makes playing hard). The app
filters out what she can't do, scores the rest, builds a weekly plan around her free time, maps
a pathway toward her goal, and lets her ask "what if?"

> **TEAM: write this part yourselves.** In 3–5 sentences, explain why *you* built this: a real
> moment, a teammate who quit, a sport you couldn't find. Judges read this first.

## Screens

| Address | Screen |
|---|---|
| `#/` | Landing page |
| `#/login`, `#/signup` | Sign in, create an account, or continue as a guest |
| `#/quiz` | 9-question onboarding |
| `#/dashboard` | This week's sessions, next step, pathway, best matches, upcoming events |
| `#/simulate` | What-if simulator: change free time, budget, distance or transport and compare plans |
| `#/opportunity/<id>` | One program: facts, map with route from home, why it matches, similar programs |
| `#/explore` | World map + ranked list, with color modes, clustering and a density heatmap |
| `#/settings` | Account, plus every quiz answer, editable |

## How it works

```
quiz answers ─► fit.py (hard filters, then weighted fit) ─► plan.py (weekly plan + pathway) ─► API ─► screens
                     ▲                                                ▲
      data/local/*.csv (programs + weekly sessions)        main.py /api/simulate (what-if + sensitivity)
      catalog.py (wider catalog) ─► pipeline.py ─► SQLite ─► ranking.py, recommender.py, analysis.py
                                                    advisor.py (optional AI barrier detection, keyword fallback)
```

| File | What it does |
|---|---|
| `app/fit.py` | Two stages. First, **hard filters** remove anything she can't do (wrong sport, age, no session fits her week, too far, past her ride cutoff) and record *why*. Then a **weighted fit score** ranks what's left: schedule 25%, distance 20%, budget 15%, experience 15%, transport 10%, intensity 10%, age 5%. |
| `app/plan.py` | Weekly plan in her free slots, the "try the next group" step, and the pathway through the seven stages with estimated weeks. |
| `app/main.py` | The API. `/api/simulate` copies the quiz, applies one change, re-plans, diffs the two plans, and tests single changes to find the top 3 that raise her best score. |
| `app/local_data.py` | Loads the verified Forsyth County programs and their weekly sessions. |
| `app/ranking.py`, `app/recommender.py`, `app/analysis.py` | The wider catalog: 9-factor ranking, TF-IDF "similar programs", and pandas statistics for the map. |
| `app/advisor.py` | Optional: reads what she types and tags barriers (cost, confidence, transport…). Uses an LLM through Groq if `GROQ_API_KEY` is set, otherwise keyword rules. It must quote her exact words as evidence. |
| `static/js/` | The front end, split into modules (see below). |

### Front-end structure

```
static/js/
  main.js        entry point: loads who is signed in, starts the router
  router.js      maps #/address -> view
  api.js         the only file that calls the server
  state.js       signed-in user, quiz answers, quiz in progress
  constants.js   sports, levels, days, brand colors
  dom.js, geo.js, map.js, ui.js, nav.js   shared helpers and components
  views/         one file per screen: landing, auth, quiz, dashboard, simulate,
                 opportunity, explore, settings
```

It uses plain ES modules (`<script type="module">`), with no build step and no framework, so anyone
on the team can open a file and read it top to bottom.

## Design choices

- **Type: Barlow Condensed + Barlow.** The condensed face for headings and numbers looks like a
  scoreboard or a jersey, which suits sports. Regular Barlow comes from the same family, so the
  two always match.
- **Color: three brand colors plus neutrals.** Plum `#462255` (primary, strong matches), berry
  `#AA4465` (accents, good matches), seafoam `#93E1D8` (highlights, "free"). Text and backgrounds
  are neutrals. Scores use only three steps (plum 80+, berry 60–79, gray under 60) so the color
  means something at a glance. Program *types* on the map keep six separate colors, because six
  categories can't be told apart with three.
- **Spacing: one 4px scale** (`--space-1` … `--space-8` = 4, 8, 12, 16, 24, 32, 48, 64px) and two
  corner sizes (4px, 8px). Everything snaps to it, so the layout looks consistent.
- **No emoji, no gradients, no drop shadows.** Flat surfaces and plain labels.
- **Honesty over polish.** A "92% match" for a program she can't attend would be a lie, so
  infeasible programs are filtered out and explained, never ranked. Deadlines that have passed are
  labeled "est." Gaps in our data are shown as gaps.

## Tradeoffs

- **Rules first, AI optional.** Matching, scoring and planning are deterministic rules we can
  explain and test. The LLM only tags barriers, and the app works without it. Cost: the keyword
  fallback misses unusual phrasing.
- **Small but verified data vs. big but rough data.** The Forsyth County programs have real weekly
  session times that we checked. The wider 99-program catalog covers more places but has no
  practice times and approximate costs. Because the weekly plan and the simulator still use the
  wider catalog, **adding a free day can't raise a score yet**. Moving them onto the Forsyth
  sessions (`fit_catalog`) is the next step.
- **No build step.** Plain JS modules are easy to read and need no install, but we don't get
  type checking or bundling.
- **Accounts in SQLite on one server.** Simple and private, but not built for many users at once.
- **Free map tiles and geocoding** (OpenStreetMap, Esri, OpenStreetMap Nominatim). No API keys, but they
  are rate-limited.

## Barriers (Phase 5)

1. In the quiz she can describe, in her own words, what makes playing hard.
2. `app/advisor.py` suggests barriers (AI through Groq if a key is set, keyword rules otherwise). Each suggestion
   must quote her exact words.
3. She confirms each one with **Yes / No**. Only confirmed barriers are used, and her message is not saved.
4. Confirmed barriers add an **environment** factor (8% of the fit; every other weight shrinks by 8% so the total
   stays 1). `BARRIER_TAGS` maps each barrier to program tags to boost and to avoid. For example, *confidence*
   boosts `beginner_friendly`, `no_tryouts`, `girls_only`, `drop_in` and avoids `tryout_required`.
5. The dashboard shows a 3-sentence **AI summary** written only from the finished plan's data. The server rejects
   it if it isn't exactly 3 sentences or uses a number that isn't in the plan.

### Advisor evaluation

`data/eval/barrier_messages.csv` has 30 sample messages with the labels a person would expect.
Run `python scripts/eval_advisor.py --show`.

| Mode | Exact-match accuracy | Label precision | Label recall | F1 | Years-since-played |
|---|---|---|---|---|---|
| Keyword fallback | 83% | 97% | 85% | 0.91 | 100% |
| AI (Groq) | *run with `GROQ_API_KEY` set and fill in* | | | | |

**Caveat:** these 30 messages were written by the developers, who had seen the keyword list, so the keyword score
is likely higher than it would be on messages from real users. Messages collected during user testing are the
honest test. Add them to the CSV and re-run.

## User testing

We tested with real athletes. Their quotes, and what we changed because of them, are in
[`USER_TESTING.md`](USER_TESTING.md).

## Run it

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Run the tests with `pytest`.
On Replit: click **Run**. For the optional AI advisor, add `GROQ_API_KEY` under **Tools → Secrets**
(never put the key in code).

## Known limitations

- Verified session data covers one county. The wider catalog is mostly U.S. soccer.
- Costs and deadlines are typical published ranges, so users must confirm on the official site.
- Umbrella organizations (AYSO, YMCA, national governing bodies) are pinned to their headquarters
  on the map.
- No live scraping. New programs are added by hand through the CSV loaders.
