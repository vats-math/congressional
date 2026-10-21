// One program in detail: facts, map with route from home, why it matches, pathway, similar programs.
import { api } from "../api.js";
import { COLORS, TYPE_COLORS } from "../constants.js";
import { $, esc, pct } from "../dom.js";
import { makeMap } from "../map.js";
import { blankProfile, state } from "../state.js";
import { deadlineText, pathwayHtml, scoreColor, wirePathway } from "../ui.js";

export function html() {
  return `<section id="opp"><p class="loading">Loading…</p></section>`;
}

export async function after(id) {
  let data;
  try {
    data = await api(`/api/opportunity/${encodeURIComponent(id)}`, { method: "POST", body: state.profile || blankProfile() });
  } catch (err) { $("#opp").innerHTML = `<p class="empty">${esc(err.message)}</p>`; return; }
  const o = data.opportunity;
  const personal = !!state.profile?.sport;
  const localChapters = o.scope === "national" && o.residency_ok;
  const flags = [];
  if (personal && !o.eligible_age) flags.push("Outside your age range");
  if (personal && !o.within_radius) flags.push("Farther than your max distance");
  if (!o.residency_ok) flags.push(o.scope === "national" ? "Only for residents of that country" : "Has a residency / eligibility rule you may not meet");
  if (o.scope === "resource") flags.push("Federation resource. You join through a local club or association.");
  const where = localChapters ? `Local chapters nationwide (HQ: ${o.city})` : `${o.city}, ${o.region ? o.region + ", " : ""}${o.country}`;
  $("#opp").innerHTML = `
    <a class="back" href="#/dashboard" onclick="history.length > 1 && (event.preventDefault(), history.back())">← Back</a>
    <div class="opp-head">
      <span class="score lg" style="background:${scoreColor(o.compatibility)}" title="Compatibility score">${o.compatibility}</span>
      <div class="opp-title"><span class="pill" style="background:${TYPE_COLORS[o.type]}">${esc(o.type)}</span><span class="pill outline">${esc(o.sport)}</span>${o.is_travel ? '<span class="pill outline">travel</span>' : ""}
        <h1>${esc(o.name)}</h1><p class="lede">${esc(o.organization)}</p></div>
      <a class="btn" href="${esc(o.website)}" target="_blank" rel="noopener noreferrer">Official site ↗</a>
    </div>
    <div class="opp-grid">
      <div class="panel">
        <dl class="facts-grid">
          <dt>When</dt><dd>${esc(o.season)}<br><small>Deadline: ${esc(deadlineText(o))}</small></dd>
          <dt>Where</dt><dd>${esc(where)}${o.distance_mi != null && !localChapters ? `<br><small>${o.distance_mi.toLocaleString()} mi from you</small>` : ""}</dd>
          <dt>Cost</dt><dd>${esc(o.cost_label)}</dd>
          <dt>Level</dt><dd>${esc(o.skill_levels.join(", "))}</dd>
          <dt>Ages</dt><dd>${o.min_age}–${o.max_age}</dd>
          <dt>Who can join</dt><dd>${esc(o.eligibility)}</dd>
        </dl>
        <p>${esc(o.description)}</p>
        ${o.deadline_estimated ? `<p class="hint">The listed deadline has passed, so this is next cycle's estimated date. Check the site.</p>` : ""}
      </div>
      <div class="panel map-panel"><div id="opp-map"></div></div>
      <div class="panel">
        <h2>${personal ? "Why it matches you" : "How it scores"}</h2>
        ${!personal ? `<p class="hint"><a href="#/quiz">Take the quiz</a> to get a personal score.</p>` : ""}
        ${o.reasons.strong.length ? `<p class="why good">Strong on ${esc(o.reasons.strong.join(", "))}</p>` : ""}
        ${o.reasons.weak.length ? `<p class="why weak">Weaker on ${esc(o.reasons.weak.join(", "))}</p>` : ""}
        ${flags.map((f) => `<p class="why warn">Check: ${esc(f)}</p>`).join("")}
        <div class="factor-bars">${Object.entries(o.factors).map(([k, v]) => `<div class="bar-row"><span>${k}</span><i style="width:${pct(v)}%"></i><b>${pct(v)}</b></div>`).join("")}</div>
      </div>
      <div class="panel span3"><h2>Your pathway</h2>${personal ? pathwayHtml(data.pathway) : `<p class="empty">Take the quiz to see your pathway.</p>`}
        <p class="hint">This program covers: <b>${esc(o.skill_levels.join(", "))}</b>.</p></div>
      <div class="panel span3"><h2>Similar programs</h2><div class="minis row">${data.similar.map((s) => `<a class="mini" href="#/opportunity/${encodeURIComponent(s.id)}"><span class="score sm" style="background:${scoreColor(s.compatibility)}">${s.compatibility}</span><span class="mini-body"><strong>${esc(s.name)}</strong><span class="meta">${esc(s.type)}</span></span></a>`).join("")}</div></div>
    </div>`;
  if (personal) wirePathway();
  const map = makeMap($("#opp-map"), { scrollWheelZoom: false });
  const pt = [o.lat, o.lng];
  L.circleMarker(pt, { radius: 11, color: COLORS.ink, weight: 2, fillColor: TYPE_COLORS[o.type], fillOpacity: 0.95 }).addTo(map).bindPopup(esc(o.name));
  const home = state.profile?.home;
  if (home?.lat != null && !localChapters) {
    const h = [home.lat, home.lng];
    L.circleMarker(h, { radius: 8, color: COLORS.berry, fillColor: COLORS.surface, fillOpacity: 1, weight: 3 }).addTo(map).bindPopup("Home");
    L.polyline([h, pt], { color: COLORS.berry, weight: 2, dashArray: "6 6" }).addTo(map);
    map.fitBounds(L.latLngBounds([h, pt]).pad(0.3), { maxZoom: 11 });
  } else map.setView(pt, 10);
}
