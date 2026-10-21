// The 9-question onboarding quiz. Answers are kept in state.quiz.draft until the last step saves them.
import { BARRIERS, COMPETITIONS, LEVELS, SPORTS, TRANSPORT } from "../constants.js";
import { $, $$, checkedValues, esc, radioValue } from "../dom.js";
import { blankProfile, saveProfile, state } from "../state.js";
import { availabilityGrid, chip, homeField, wireHomeField } from "../ui.js";

const STEPS = [
  { title: "What sport do you play, or want to play?",
    render: (p) => `<div class="chips grid4">${SPORTS.map((s) => chip("sport", s, s === "multi" ? "Not sure yet" : s, p.sport === s, "radio")).join("")}</div>`,
    read: (r, p) => { p.sport = radioValue(r, "sport"); return p.sport ? null : "Pick a sport (or “Not sure yet”)."; } },
  { title: "How old are you?",
    render: (p) => `<input class="big-input" name="age" type="number" min="5" max="80" inputmode="numeric" value="${p.age ?? ""}" placeholder="14"/>
      <p class="hint">Programs have age limits. We only recommend ones you can join.</p>`,
    read: (r, p) => { const v = Number($("[name=age]", r).value); if (!v || v < 5 || v > 80) return "Enter an age between 5 and 80."; p.age = v; return null; } },
  { title: "What's your experience level?",
    render: (p) => `<div class="options">${LEVELS.map(([v, l, d]) => `<label class="option"><input type="radio" name="skill" value="${v}" ${p.skill === v ? "checked" : ""}/><span><b>${l}</b><small>${d}</small></span></label>`).join("")}</div>
      <label class="stack">If you've taken a break, how long since you last played?
        <select name="years_since_played">
          <option value="" ${p.years_since_played == null ? "selected" : ""}>No long break</option>
          <option value="1" ${p.years_since_played === 1 ? "selected" : ""}>About 1 year</option>
          <option value="2" ${p.years_since_played === 2 ? "selected" : ""}>About 2 years</option>
          <option value="3" ${p.years_since_played >= 3 ? "selected" : ""}>3 or more years</option>
        </select>
      </label>
      <label class="stack">Skills you want to work on (optional)<input name="goal_text" maxlength="300" value="${esc(p.goal_text)}" placeholder="e.g. footwork, speed, getting noticed by college coaches"/></label>`,
    read: (r, p) => {
      p.skill = radioValue(r, "skill");
      const years = $("[name=years_since_played]", r).value;
      p.years_since_played = years === "" ? null : Number(years);
      p.goal_text = $("[name=goal_text]", r).value.trim();
      return p.skill ? null : "Choose the level closest to you.";
    } },
  { title: "What kinds of competition interest you?", sub: "Pick as many as you like.",
    render: (p) => `<div class="options two">${COMPETITIONS.map(([v, l, d]) => `<label class="option"><input type="checkbox" name="competitions" value="${v}" ${p.competitions.includes(v) ? "checked" : ""}/><span><b>${l}</b><small>${d}</small></span></label>`).join("")}</div>`,
    read: (r, p) => { p.competitions = checkedValues(r, "competitions"); return null; } },
  { title: "When are you free to play?", sub: "Tap every time slot that works in a normal week.",
    render: (p) => availabilityGrid(p.availability),
    read: (r, p) => { p.availability = checkedValues(r, "availability"); return p.availability.length ? null : "Pick at least one time slot."; } },
  { title: "What can you spend per season?",
    render: (p) => `<div class="range-wrap"><input type="range" name="budget" min="0" max="5000" step="50" value="${p.budget_usd ?? 500}"/>
      <output id="budget-out">${p.budget_usd == null ? "Not sure" : "$" + p.budget_usd.toLocaleString()}</output></div>
      <div class="chips">${chip("budget_preset", "0", "Free only", p.budget_usd === 0, "radio")}${chip("budget_preset", "200", "Under $200", p.budget_usd === 200, "radio")}${chip("budget_preset", "1000", "Under $1,000", p.budget_usd === 1000, "radio")}${chip("budget_preset", "", "Not sure", p.budget_usd == null, "radio")}</div>`,
    after: (r) => {
      const range = $("[name=budget]", r), out = $("#budget-out", r);
      range.addEventListener("input", () => { out.textContent = `$${Number(range.value).toLocaleString()}`; $$("[name=budget_preset]", r).forEach((i) => (i.checked = false)); });
      $$("[name=budget_preset]", r).forEach((i) => i.addEventListener("change", () => {
        if (i.value !== "") { range.value = i.value; out.textContent = `$${Number(i.value).toLocaleString()}`; } else out.textContent = "Not sure"; }));
    },
    read: (r, p) => { const preset = radioValue(r, "budget_preset"); p.budget_usd = preset === "" ? null : Number(preset ?? $("[name=budget]", r).value); return null; } },
  { title: "Where do you live, and how far will you go?",
    render: (p) => `${homeField(p.home)}
      <label class="stack">Max travel distance<div class="range-wrap"><input type="range" name="distance" min="5" max="500" step="5" value="${p.max_distance_mi ?? 25}"/><output id="dist-out">${p.max_distance_mi ?? 25} mi</output></div></label>`,
    after: (r, p) => {
      wireHomeField(r, (home) => (p.home = home));
      const range = $("[name=distance]", r);
      range.addEventListener("input", () => ($("#dist-out", r).textContent = `${range.value} mi`));
    },
    read: (r, p) => { p.max_distance_mi = Number($("[name=distance]", r).value); return p.home?.lat != null ? null : "Add your city (press Enter after typing) or use your location."; } },
  { title: "How will you get there?",
    render: (p) => `<div class="options three">${TRANSPORT.map(([v, label]) => `<label class="option center"><input type="radio" name="transport" value="${v}" ${p.transport === v ? "checked" : ""}/><span><b>${label}</b></span></label>`).join("")}</div>`,
    read: (r, p) => { p.transport = radioValue(r, "transport"); return p.transport ? null : "Choose how you'll usually travel."; } },
  { title: "Anything that makes playing harder? And what's your goal?", sub: "Optional. This helps us suggest the right programs.",
    render: (p) => `<div class="chips">${BARRIERS.map(([v, l]) => chip("barriers", v, l, p.barriers.includes(v))).join("")}</div>
      <label class="stack">My goal is to reach…<select name="goal_level"><option value="">Just have fun / not sure</option>${LEVELS.map(([v, l]) => `<option value="${v}" ${p.goal_level === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>`,
    read: (r, p) => { p.barriers = checkedValues(r, "barriers"); p.goal_level = $("[name=goal_level]", r).value || null; return null; } },
];

export function html() {
  const q = state.quiz;
  if (!q.draft) { q.draft = structuredClone({ ...blankProfile(), ...(state.profile || {}) }); q.step = 0; }
  const step = STEPS[q.step];
  return `<section class="quiz">
    <div class="progress"><i style="width:${(100 * (q.step + 1)) / STEPS.length}%"></i></div>
    <p class="kicker">Question ${q.step + 1} of ${STEPS.length}</p>
    <h1>${step.title}</h1>${step.sub ? `<p class="lede">${step.sub}</p>` : ""}
    <form id="quiz-form" novalidate>${step.render(q.draft)}
      <p class="form-error" id="quiz-error" role="alert"></p>
      <div class="quiz-nav">
        ${q.step ? `<button type="button" class="ghost" id="quiz-back">Back</button>` : "<span></span>"}
        <button type="submit" class="btn">${q.step === STEPS.length - 1 ? "Build my plan" : "Next"}</button>
      </div>
    </form></section>`;
}

export function after() {
  const q = state.quiz;
  const form = $("#quiz-form");
  const step = STEPS[q.step];
  step.after?.(form, q.draft);
  $("#quiz-back")?.addEventListener("click", () => { step.read(form, q.draft); q.step--; state.rerender(); });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = step.read(form, q.draft);
    if (err) { $("#quiz-error").textContent = err; return; }
    if (q.step < STEPS.length - 1) { q.step++; state.rerender(); return; }
    await saveProfile(q.draft);
    q.draft = null;
    location.hash = "#/dashboard";
  });
}
