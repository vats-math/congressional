// Personalized plan: this week's sessions, next step, pathway, best matches, events.
import { api } from "../api.js";
import { $, esc } from "../dom.js";
import { state } from "../state.js";
import { deadlineText, miniCard, pathwayHtml, scoreColor, wirePathway } from "../ui.js";

export function html() {
  return `<section id="dash"><p class="loading">Building your plan…</p></section>`;
}

export async function after() {
  if (!state.profile?.sport) { location.hash = "#/quiz"; return; }
  const plan = await api("/api/plan", { method: "POST", body: state.profile });
  const p = state.profile;
  const name = state.user?.name || "there";
  const sessions = plan.sessions.length
    ? plan.sessions.map((s) => `<a class="session" href="#/opportunity/${encodeURIComponent(s.id)}">
        <div class="session-day"><b>${s.day}</b><small>${esc(s.time)}</small></div>
        <div class="session-body"><strong>${esc(s.name)}</strong>
          <span class="meta">Distance: ${esc(s.distance)} · Cost: ${esc(s.cost)}</span>
          <span class="meta muted">Your free slot. Confirm the practice time on the program's site.</span></div>
        <span class="score sm" style="background:${scoreColor(s.compatibility)}">${s.compatibility}</span></a>`).join("")
    : `<p class="empty">${plan.no_slots ? "Add your free times in Settings to get a weekly plan." : "No eligible weekly programs within your travel range yet. Try a bigger distance in Settings, or check the map."}</p>`;
  const up = plan.step_up;
  $("#dash").innerHTML = `
    <div class="dash-head">
      <div><p class="kicker">Your plan · ${esc(p.sport)} · age ${esc(p.age)}</p><h1>Hi ${esc(name)}</h1>
      <p class="lede">Built from your quiz answers and ranked against every program in our database.</p></div>
      <div class="dash-actions"><a class="btn ghost small" href="#/settings">Edit answers</a><a class="btn small" href="#/simulate">Try a what-if</a><a class="btn small" href="#/explore">Open map</a></div>
    </div>
    <div class="dash-grid">
      <div class="panel span3 ai-summary" id="ai-summary" hidden>
        <p class="ai-label">AI summary</p>
        <p id="ai-summary-text" class="loading">Writing a short summary of your plan…</p>
        <p class="hint">Written by an AI model from your plan's data only (not anything you typed). It can still make mistakes, so check the details below.</p>
      </div>
      <div class="panel span2"><h2>This week</h2><div class="sessions">${sessions}</div></div>
      <div class="panel">
        <h2>Next step</h2>
        ${up ? `<div class="stepup"><p class="kicker">${esc(up.after)}</p><h3>Try the ${esc(up.label.toLowerCase())} group</h3>
          ${up.program ? miniCard(up.program) : `<p class="empty">No ${esc(up.label.toLowerCase())} program in range yet.</p>`}</div>`
          : `<p>You're at the top of the pathway. Keep an eye on the college and national events.</p>`}
        ${plan.tips.length ? `<h3 class="mt">Tips for you</h3><ul class="tips">${plan.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}
      </div>
      <div class="panel span3"><h2>Your pathway</h2>${pathwayHtml(plan.pathway)}</div>
      <div class="panel span2"><h2>Best matches for you</h2><div class="minis">${plan.top_matches.map((m) => miniCard(m)).join("") || '<p class="empty">No eligible matches yet.</p>'}</div></div>
      <div class="panel"><h2>Upcoming events</h2>${plan.events.length ? `<div class="minis">${plan.events.map((m) => miniCard(m, `<span class="meta">Deadline ${esc(deadlineText(m))}</span>`)).join("")}</div>` : `<p class="empty">Choose “Tournaments” or “College recruiting” in your answers to see events.</p>`}</div>
    </div>`;
  wirePathway();
  loadSummary();
}

// Phase 5: 3-sentence summary from the model. The server sends it only the finished plan's facts.
// If there's no API key or the answer fails the server's checks, the panel stays hidden.
async function loadSummary() {
  const box = $("#ai-summary");
  if (!box) return;
  box.hidden = false;
  try {
    const { summary } = await api("/api/plan/summary", { method: "POST", body: state.profile });
    if (!summary) { box.hidden = true; return; }
    const text = $("#ai-summary-text");
    text.classList.remove("loading");
    text.textContent = summary;
  } catch {
    box.hidden = true;
  }
}
