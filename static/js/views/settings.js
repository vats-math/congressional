// Account settings and every quiz answer, editable.
import { api } from "../api.js";
import { BARRIERS, COMPETITIONS, LEVELS, SPORTS, TRANSPORT } from "../constants.js";
import { $, checkedValues, esc, radioValue } from "../dom.js";
import { renderNav } from "../nav.js";
import { blankProfile, saveProfile, state } from "../state.js";
import { availabilityGrid, chip, homeField, wireHomeField } from "../ui.js";

export function html() {
  state.profile = { ...blankProfile(), ...(state.profile || {}) };
  const p = state.profile;
  const u = state.user;
  return `<section class="settings">
    <h1>Settings</h1>
    <p class="lede">Everything you answered in the quiz is saved here. Change anything and your plan updates.</p>
    <form id="settings-form" novalidate>
      <div class="panel"><h2>Account</h2>
        ${u ? `<label class="stack">Name<input name="name" value="${esc(u.name)}" maxlength="80"/></label>
          <label class="stack">Email<input value="${esc(u.email)}" disabled/></label>
          <div class="row-actions"><button type="button" class="ghost small" data-action="signout">Sign out</button>
          <button type="button" class="danger small" id="delete-account">Delete account</button></div>`
        : `<p>You're a guest, so your answers live only in this browser. <a href="#/signup">Create an account</a> to save them.</p>`}
      </div>
      <div class="panel"><h2>Sport profile</h2>
        <div class="two-col">
          <label class="stack">Sport<select name="sport">${SPORTS.map((s) => `<option value="${s}" ${p.sport === s ? "selected" : ""}>${s === "multi" ? "Not sure / multi" : s}</option>`).join("")}</select></label>
          <label class="stack">Age<input name="age" type="number" min="5" max="80" value="${p.age ?? ""}"/></label>
          <label class="stack">Level<select name="skill">${LEVELS.map(([v, l]) => `<option value="${v}" ${p.skill === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
          <label class="stack">Years since you last played<select name="years_since_played">
            <option value="" ${p.years_since_played == null ? "selected" : ""}>No long break</option>
            <option value="1" ${p.years_since_played === 1 ? "selected" : ""}>About 1 year</option>
            <option value="2" ${p.years_since_played === 2 ? "selected" : ""}>About 2 years</option>
            <option value="3" ${p.years_since_played >= 3 ? "selected" : ""}>3 or more years</option>
          </select></label>
          <label class="stack">Goal<select name="goal_level"><option value="">Just have fun</option>${LEVELS.map(([v, l]) => `<option value="${v}" ${p.goal_level === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>
        </div>
        <label class="stack">Skills I want to work on<input name="goal_text" maxlength="300" value="${esc(p.goal_text)}"/></label>
        <h3>Competitions</h3><div class="chips">${COMPETITIONS.map(([v, l]) => chip("competitions", v, l, p.competitions.includes(v))).join("")}</div>
      </div>
      <div class="panel"><h2>Cost & availability</h2>
        <label class="stack">Max cost per season (USD, blank = not sure)<input name="budget_usd" type="number" min="0" value="${p.budget_usd ?? ""}"/></label>
        <h3>When I'm free</h3>${availabilityGrid(p.availability)}
      </div>
      <div class="panel"><h2>Location & travel</h2>
        <h3>Home</h3>${homeField(p.home)}
        <label class="stack">Max travel distance (miles)<input name="max_distance_mi" type="number" min="1" value="${p.max_distance_mi ?? ""}"/></label>
        <h3>How I get there</h3><div class="chips">${TRANSPORT.map(([v, label]) => chip("transport", v, label, p.transport === v, "radio")).join("")}</div>
      </div>
      <div class="panel"><h2>Challenges</h2><div class="chips">${BARRIERS.map(([v, l]) => chip("barriers", v, l, p.barriers.includes(v))).join("")}</div></div>
      <div class="save-bar"><span id="save-status" role="status"></span><a class="ghost btn" href="#/quiz" id="retake">Retake quiz</a><button class="btn" type="submit">Save changes</button></div>
    </form></section>`;
}

export function after() {
  const form = $("#settings-form");
  let home = state.profile.home || {};
  wireHomeField(form, (h) => (home = h));
  $("#retake").addEventListener("click", () => { state.quiz.draft = null; });
  $("#delete-account")?.addEventListener("click", async () => {
    if (!confirm("Delete your account and saved answers? This can't be undone.")) return;
    await api("/api/me", { method: "DELETE" });
    state.user = null; state.profile = null; location.hash = "#/";
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(form);
    const num = (k) => (f.get(k) === "" || f.get(k) == null ? null : Number(f.get(k)));
    const next = {
      ...state.profile,
      sport: f.get("sport"), age: num("age"), skill: f.get("skill"), goal_level: f.get("goal_level") || null,
      years_since_played: num("years_since_played"),
      goal_text: (f.get("goal_text") || "").trim(), competitions: checkedValues(form, "competitions"),
      budget_usd: num("budget_usd"), availability: checkedValues(form, "availability"), home,
      max_distance_mi: num("max_distance_mi"), transport: radioValue(form, "transport"), barriers: checkedValues(form, "barriers"),
    };
    try {
      if (state.user && f.get("name") != null) state.user = (await api("/api/me", { method: "PUT", body: { name: f.get("name") } })).user;
      await saveProfile(next);
      $("#save-status").textContent = "Saved. Your plan is updated.";
      renderNav("settings");
    } catch (err) { $("#save-status").textContent = err.message; }
  });
}
