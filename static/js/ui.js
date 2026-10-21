// Pieces of HTML reused across screens: logo, score badges, form controls, program cards, the pathway.
import { COLORS, DAYS, LEVELS, TIMES, TYPE_COLORS } from "./constants.js";
import { $, esc } from "./dom.js";
import { currentPosition, geocode, reverseGeocode } from "./geo.js";
import { saveProfile, state } from "./state.js";

// Three steps of the brand palette so the colors stay meaningful: plum = strong, berry = good, neutral = weak.
export const SCORE_BANDS = [
  [80, COLORS.plum, "80–100"],
  [60, COLORS.berry, "60–79"],
  [0, COLORS.neutral, "under 60"],
];
export function scoreColor(s) {
  return SCORE_BANDS.find(([min]) => s >= min)[1];
}

export const LOGO = `<svg class="logo" viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="8" fill="${COLORS.plum}"/>
  <path d="M9 29 C15 29 14 14 21 14 S27 23 31 12" fill="none" stroke="${COLORS.seafoam}" stroke-width="3.2" stroke-linecap="round"/>
  <circle cx="31" cy="12" r="3.4" fill="${COLORS.berry}"/></svg>`;

export function chip(name, value, label, checked, type = "checkbox") {
  return `<label class="chip"><input type="${type}" name="${name}" value="${esc(value)}" ${checked ? "checked" : ""}/><span>${label}</span></label>`;
}

export function availabilityGrid(selected = []) {
  return `<div class="avail" role="group" aria-label="Availability">
    <span></span>${DAYS.map((d) => `<b>${d}</b>`).join("")}
    ${TIMES.map(([t, label]) => `<span class="avail-label">${label}</span>${DAYS.map((d) => {
      const v = `${d}-${t}`;
      return `<label class="cell" title="${d} ${label}"><input type="checkbox" name="availability" value="${v}" ${selected.includes(v) ? "checked" : ""}/><i></i></label>`;
    }).join("")}`).join("")}
  </div>`;
}

export function homeField(home = {}) {
  return `<div class="home-row">
      <input id="home-input" placeholder="City, e.g. Dallas, TX" value="${esc(home.label || "")}" autocomplete="off"/>
      <button type="button" class="ghost small" id="home-locate">Use my location</button>
    </div><p class="hint" id="home-status">${home.lat != null ? `Saved: ${esc(home.label)}${home.country ? `, ${esc(home.country)}` : ""}` : "Type your city and press Enter. We only use it to measure distance."}</p>`;
}

export function wireHomeField(root, onSet) {
  const status = $("#home-status", root);
  const input = $("#home-input", root);
  $("#home-locate", root).addEventListener("click", async () => {
    status.textContent = "Locating…";
    try {
      const c = await currentPosition();
      const rev = await reverseGeocode(c.latitude, c.longitude);
      const home = { lat: c.latitude, lng: c.longitude, ...rev };
      input.value = home.label;
      status.textContent = `Using ${home.label}${home.country ? `, ${home.country}` : ""}`;
      onSet(home);
    } catch (err) { status.textContent = err.message; }
  });
  const lookup = async () => {
    const q = input.value.trim();
    if (!q) return onSet({});
    status.textContent = "Looking up…";
    try {
      const hit = await geocode(q);
      if (!hit) { status.textContent = `Couldn't find "${q}". Try adding the state or country.`; return; }
      status.textContent = `Found ${hit.label}${hit.country ? `, ${hit.country}` : ""}`;
      onSet({ lat: hit.lat, lng: hit.lng, label: hit.label, country: hit.country });
    } catch (err) { status.textContent = err.message; }
  };
  input.addEventListener("change", lookup);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); input.blur(); } });
}

export function deadlineText(item) {
  if (!item.next_deadline) return "Rolling / see site";
  return item.deadline_estimated ? `${item.next_deadline} (est.)` : item.next_deadline;
}

export function miniCard(item, extra = "") {
  return `<a class="mini" href="#/opportunity/${encodeURIComponent(item.id)}">
    <span class="score sm" style="background:${scoreColor(item.compatibility)}">${item.compatibility}</span>
    <span class="mini-body"><strong>${esc(item.name)}</strong>
    <span class="meta"><span class="dot" style="background:${TYPE_COLORS[item.type]}"></span>${esc(item.type)} · ${esc(item.distance)} · ${esc(item.cost)}</span>${extra}</span></a>`;
}

export function pathwayHtml(steps) {
  return `<div class="pathway">${steps.map((s, i) => `
    <div class="pstep ${s.status}${s.is_goal ? " goal" : ""}">
      ${s.status === "current" ? `<span class="here">Current stage</span>` : ""}
      ${s.is_goal ? `<span class="flag">Goal</span>` : ""}
      <span class="pdot${s.status === "past" ? " done" : ""}">${s.status === "past" ? "Done" : i + 1}</span>
      <b>${esc(s.label)}</b>
      ${s.program ? `<a href="#/opportunity/${encodeURIComponent(s.program.id)}">${esc(s.program.name)}</a>
        <small class="program-fit">Best feasible match${s.program.fit == null ? "" : ` · ${esc(s.program.fit)}% fit`}</small>`
        : `<small class="gap-note">${esc(s.gap || "No eligible program matches your answers yet.")}</small>`}
      ${s.weeks == null ? `<small class="duration">Goal stage</small>` : `<small class="duration">About ${esc(s.weeks)} weeks to next step</small>`}
      <small class="ready-note">${esc(s.ready_when)}</small>
    </div>${i < steps.length - 1 ? `<span class="arrow" aria-hidden="true">→</span>` : ""}`).join("")}</div>
    <div class="goal-row"><button type="button" class="ghost small" id="change-goal">Change my goal</button>
      <span id="goal-editor" hidden><select id="goal-select"><option value="">Just have fun</option>${LEVELS.map(([v, l]) => `<option value="${v}" ${state.profile?.goal_level === v ? "selected" : ""}>${l}</option>`).join("")}</select>
      <button type="button" class="btn small" id="goal-save">Save goal</button></span></div>`;
}

export function wirePathway() {
  $("#change-goal")?.addEventListener("click", () => { $("#goal-editor").hidden = false; $("#goal-select").focus(); });
  $("#goal-save")?.addEventListener("click", async () => {
    await saveProfile({ ...state.profile, goal_level: $("#goal-select").value || null });
    state.rerender();
  });
}
