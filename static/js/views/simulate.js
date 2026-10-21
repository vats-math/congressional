// What-if simulator (Phase 4): change availability, budget, distance or transport and compare plans.
import { api } from "../api.js";
import { TRANSPORT } from "../constants.js";
import { $, checkedValues, esc } from "../dom.js";
import { state } from "../state.js";
import { availabilityGrid, miniCard } from "../ui.js";

export function html() {
  if (!state.profile?.sport) {
    return `<section class="quiz"><p class="kicker">What-if simulator</p><h1>Build a plan first</h1>
      <p class="lede">Answer the quiz to explore how changes could affect your matches.</p>
      <a class="btn mt" href="#/quiz">Take the quiz</a></section>`;
  }
  const profile = state.profile;
  const transport = profile.transport || "car";
  return `<section class="simulator">
    <div class="dash-head">
      <div><p class="kicker">What-if simulator</p><h1>Try a different plan</h1>
        <p class="lede">Explore changes without saving them to your profile.</p></div>
      <div class="dash-actions"><a class="btn ghost small" href="#/dashboard">Back to dashboard</a></div>
    </div>
    <div class="simulator-grid">
      <form class="panel sim-controls" id="simulator-form">
        <h2>Change your situation</h2>
        <p class="hint">Results update shortly after you stop adjusting the controls.</p>
        <fieldset class="sim-fieldset"><legend>Free time</legend>${availabilityGrid(profile.availability || [])}</fieldset>
        <div class="sim-number-grid">
          <label class="stack" for="sim-budget">Budget per program (USD)
            <input id="sim-budget" type="number" min="0" step="25" value="${profile.budget_usd ?? ""}" placeholder="No limit" />
          </label>
          <label class="stack" for="sim-distance">Maximum travel distance (miles)
            <input id="sim-distance" type="number" min="0.1" step="5" value="${profile.max_distance_mi ?? ""}" placeholder="Use transport limit" />
          </label>
        </div>
        <label class="stack" for="sim-transport">How you get there
          <select id="sim-transport">${TRANSPORT.map(([value, label]) =>
            `<option value="${esc(value)}" ${transport === value ? "selected" : ""}>${esc(label)}</option>`).join("")}</select>
        </label>
      </form>
      <section class="panel sim-results" id="simulator-results" aria-live="polite" aria-busy="true">
        <p class="loading">Comparing plans…</p>
      </section>
    </div>
  </section>`;
}

export function after() {
  if (!state.profile?.sport) return;
  const form = $("#simulator-form");
  const results = $("#simulator-results");
  let timer;
  let requestVersion = 0;

  const readOverrides = () => {
    const base = state.profile;
    const overrides = {};
    const availability = checkedValues(form, "availability").sort();
    const originalAvailability = [...(base.availability || [])].sort();
    if (JSON.stringify(availability) !== JSON.stringify(originalAvailability)) overrides.availability = availability;

    const readNumber = (selector) => {
      const value = $(selector, form).value.trim();
      return value === "" ? null : Number(value);
    };
    const budget = readNumber("#sim-budget");
    if (budget !== base.budget_usd) overrides.budget_usd = budget;
    const distance = readNumber("#sim-distance");
    if (distance !== base.max_distance_mi) overrides.max_distance_mi = distance;
    const transport = $("#sim-transport", form).value;
    if (transport !== (base.transport || "car")) overrides.transport = transport;
    return overrides;
  };

  const renderResults = (data) => {
    const diff = data.diff;
    const scoreDelta = diff.score_improvement > 0 ? `+${diff.score_improvement}` : String(diff.score_improvement);
    const gained = diff.gained.length
      ? diff.gained.map((program) => miniCard(program)).join("")
      : `<p class="empty">No new weekly programs.</p>`;
    const lost = diff.lost.length
      ? diff.lost.map((program) => miniCard(program)).join("")
      : `<p class="empty">No weekly programs removed.</p>`;
    const suggestions = data.sensitivity.length
      ? `<ol class="sim-suggestions">${data.sensitivity.map((item) =>
        `<li><strong>${esc(item.label)}</strong><span>Best match: ${item.score_before} → ${item.score_after} (+${item.improvement})</span></li>`).join("")}</ol>`
      : `<p class="empty">No single change in the tested range raises your current best-match score.</p>`;
    const weeksBefore = diff.pathway_weeks_before == null ? "Not estimated" : `${diff.pathway_weeks_before} weeks`;
    const weeksAfter = diff.pathway_weeks_after == null ? "Not estimated" : `${diff.pathway_weeks_after} weeks`;
    results.innerHTML = `
      <p class="kicker">Plan comparison</p><h2>What changed</h2>
      <div class="sim-metrics">
        <div><span>Best match</span><strong>${diff.best_score_before} → ${diff.best_score_after}</strong><small>${scoreDelta} points</small></div>
        <div><span>Available plan slots</span><strong>${diff.sessions_before} → ${diff.sessions_after}</strong><small>Based on your free-time answers</small></div>
        <div><span>Pathway length</span><strong>${esc(weeksBefore)} → ${esc(weeksAfter)}</strong><small>Weeks between steps</small></div>
      </div>
      <div class="sim-program-diff">
        <section><h3>New in your weekly plan</h3>${gained}</section>
        <section><h3>No longer in your weekly plan</h3>${lost}</section>
      </div>
      <h3>Changes with the biggest score gains</h3>${suggestions}
      <p class="hint sim-note">${data.notes.map(esc).join(" ")}</p>`;
    results.setAttribute("aria-busy", "false");
  };

  // Debounce: wait 300 ms after the last change before asking the server.
  const scheduleUpdate = () => {
    const version = ++requestVersion;
    clearTimeout(timer);
    timer = setTimeout(async () => {
      results.setAttribute("aria-busy", "true");
      results.innerHTML = `<p class="loading">Comparing plans…</p>`;
      try {
        const data = await api("/api/simulate", {
          method: "POST",
          body: { quiz: state.profile, overrides: readOverrides() },
        });
        if (version === requestVersion) renderResults(data);
      } catch (err) {
        if (version === requestVersion) {
          results.innerHTML = `<p class="form-error" role="alert">${esc(err.message)}</p>`;
          results.setAttribute("aria-busy", "false");
        }
      }
    }, 300);
  };

  form.addEventListener("submit", (event) => event.preventDefault());
  form.addEventListener("input", scheduleUpdate);
  form.addEventListener("change", scheduleUpdate);
  scheduleUpdate();
}
