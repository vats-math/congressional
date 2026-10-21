// World map + ranked list of every program, re-rankable with a typed description.
import { api } from "../api.js";
import { COLORS, TYPE_COLORS } from "../constants.js";
import { $, $$, esc } from "../dom.js";
import { geocode } from "../geo.js";
import { makeMap } from "../map.js";
import { state } from "../state.js";
import { SCORE_BANDS, scoreColor } from "../ui.js";

export function html() {
  return `
  <section class="explore-head">
    <div><h1>Explore the map</h1><p class="lede">Every program in the database, scored for ${state.profile?.sport ? "your profile" : "a general profile"}. Type a description to re-rank.</p></div>
    <form id="explore-form" class="explore-form">
      <input id="query" maxlength="1000" placeholder="e.g. I'm 14, play recreational soccer and want travel opportunities near Dallas"/>
      <button class="btn" type="submit">Rank</button>
    </form>
  </section>
  <section class="stats" id="stats" hidden></section>
  <section class="workspace">
    <div class="list-pane"><div class="list-head"><h2>Ranked matches</h2><p id="list-meta">Loading…</p></div><ol id="results"></ol></div>
    <div class="map-pane">
      <div class="map-tools"><label>Color by <select id="color-mode">
        <option value="type">Opportunity type</option><option value="score">Compatibility score</option>
        <option value="affordability">Affordability</option><option value="eligibility">Eligibility</option></select></label></div>
      <div class="map-legend" id="legend"></div><div id="map"></div>
    </div>
  </section>`;
}

// Map colors per mode. Each mode uses the brand colors plus one neutral, so the legend stays short.
const AFFORD = [[0.95, COLORS.seafoamDeep, "Free"], [0.5, COLORS.berry, "Low to moderate / unknown"], [0, COLORS.plum, "High"]];
const ELIGIBILITY = { eligible: [COLORS.seafoamDeep, "Eligible"], outside: [COLORS.berry, "Age or distance outside range"], blocked: [COLORS.neutral, "Residency / not joinable"] };

export function after() {
  const ex = { items: [], profile: {}, mode: "type", markers: new Map() };
  const map = makeMap($("#map"));
  const clusters = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 45,
    iconCreateFunction: (c) => { const n = c.getChildCount(), s = n < 10 ? 30 : n < 50 ? 38 : 46;
      return L.divIcon({ html: `<span>${n}</span>`, className: "cluster", iconSize: [s, s] }); } }).addTo(map);
  const heat = L.heatLayer([], {
    radius: 28, blur: 22, maxZoom: 9, minOpacity: 0.25,
    gradient: { 0.2: COLORS.seafoam, 0.6: COLORS.berry, 1: COLORS.plum },
  });
  const homeLayer = L.layerGroup().addTo(map);
  L.control.layers(map._baseLayers, { Opportunities: clusters, "Density heatmap": heat, "Home & radius": homeLayer }).addTo(map);
  L.control.scale().addTo(map);

  const affordColor = (a) => AFFORD.find(([min]) => a >= min)[1];
  const eligibilityKey = (i) => (i.eligible ? "eligible" : i.residency_ok ? "outside" : "blocked");
  const colorFor = (i) => ex.mode === "score" ? scoreColor(i.compatibility) : ex.mode === "affordability" ? affordColor(i.affordability)
    : ex.mode === "eligibility" ? ELIGIBILITY[eligibilityKey(i)][0] : TYPE_COLORS[i.type] || COLORS.neutral;
  const legend = () => {
    const row = (c, t) => `<div class="legend-row"><span class="swatch" style="background:${c}"></span>${t}</div>`;
    const sets = {
      score: ["Compatibility", SCORE_BANDS.map(([, c, t]) => [c, t])],
      affordability: ["Cost", AFFORD.map(([, c, t]) => [c, t])],
      eligibility: ["Eligibility", Object.values(ELIGIBILITY)],
      type: ["Type", Object.entries(TYPE_COLORS).map(([t, c]) => [c, t])],
    };
    const [title, rows] = sets[ex.mode];
    $("#legend").innerHTML = `<strong>${title}</strong>${rows.map(([c, t]) => row(c, t)).join("")}<div class="legend-note">Bigger dot = higher score</div>`;
  };

  function draw(fit) {
    clusters.clearLayers(); homeLayer.clearLayers(); ex.markers.clear();
    ex.items.forEach((i) => {
      const m = L.circleMarker([i.lat, i.lng], { radius: 5 + i.compatibility / 12, color: i.eligible ? COLORS.ink : COLORS.neutral,
        weight: i.eligible ? 1.5 : 1, dashArray: i.eligible ? null : "2 3", fillColor: colorFor(i), fillOpacity: i.eligible ? 0.9 : 0.55 })
        .bindPopup(`<div class="pop"><strong>${i.compatibility} · ${esc(i.name)}</strong><br>${esc(i.type)} · ${esc(i.city)}, ${esc(i.country)}<br>${esc(i.cost_label)}<br><a href="#/opportunity/${encodeURIComponent(i.id)}">View details →</a></div>`);
      m.on("click", () => highlight(i.id));
      ex.markers.set(i.id, m); clusters.addLayer(m);
    });
    heat.setLatLngs(ex.items.map((i) => [i.lat, i.lng, 0.3 + i.compatibility / 140]));
    const p = ex.profile;
    if (p.lat != null) {
      L.circleMarker([p.lat, p.lng], { radius: 9, color: COLORS.berry, fillColor: COLORS.surface, fillOpacity: 1, weight: 3 }).bindPopup("Home").addTo(homeLayer);
      if (p.max_distance_km) L.circle([p.lat, p.lng], { radius: p.max_distance_km * 1000, color: COLORS.berry, weight: 1.5, fillOpacity: 0.04, dashArray: "6 6" }).addTo(homeLayer);
      if (fit) map.flyToBounds(L.latLngBounds([[p.lat, p.lng], ...ex.items.filter((i) => i.eligible).slice(0, 10).map((i) => [i.lat, i.lng])]).pad(0.2), { maxZoom: 9, duration: 0.6 });
    }
  }
  function highlight(id) {
    $$(".card").forEach((c) => { const on = c.dataset.id === id; c.classList.toggle("active", on); if (on) c.scrollIntoView({ block: "nearest", behavior: "smooth" }); });
  }
  function list(data) {
    $("#list-meta").textContent = `${data.count} programs scored. Click one to see it on the map.`;
    $("#results").innerHTML = ex.items.slice(0, 60).map((i, n) => `<li class="card${i.eligible ? "" : " dim"}" data-id="${esc(i.id)}">
      <div class="score" style="background:${scoreColor(i.compatibility)}">${i.compatibility}</div>
      <div class="body"><span class="pill" style="background:${TYPE_COLORS[i.type]}">${esc(i.type)}</span><span class="pill outline">${esc(i.sport)}</span>
        <h3>${n + 1}. ${esc(i.name)}</h3>
        <p class="meta">${esc(i.city)}, ${esc(i.country)}${i.distance_mi != null ? ` · ${i.distance_mi.toLocaleString()} mi` : ""} · ages ${i.min_age}–${i.max_age} · ${esc(i.cost_label)}</p>
        ${i.reasons.strong.length ? `<p class="why good">Strong match: ${esc(i.reasons.strong.join(", "))}</p>` : ""}
        ${!i.eligible ? `<p class="why warn">Check eligibility</p>` : ""}
        <p class="links"><a href="#/opportunity/${encodeURIComponent(i.id)}">Details →</a></p></div></li>`).join("");
  }
  function stats(a) {
    const el = $("#stats"); el.hidden = false;
    el.innerHTML = [["Programs", a.count], ["Mean score", a.mean_score], ["Median cost", a.median_cost == null ? "—" : `$${a.median_cost.toLocaleString()}`],
      ["Travel", `${a.travel_share}%`], ["Eligible", `${a.eligible_share}%`], ["Top-25% cutoff", a.top_quartile_cutoff]]
      .map(([l, v]) => `<div class="stat"><span>${l}</span><strong>${esc(v)}</strong></div>`).join("");
  }
  async function run(query, fit) {
    const p = state.profile || {};
    const body = { query, eligible_only: false };
    if (!query && p.sport) Object.assign(body, { age: p.age, sport: p.sport === "multi" ? null : p.sport, skill: p.skill, budget_usd: p.budget_usd,
      max_distance_km: p.max_distance_mi ? p.max_distance_mi * 1.60934 : null });
    if (p.home?.lat != null && !/\b(near|in|around|from)\b/i.test(query)) Object.assign(body, { lat: p.home.lat, lng: p.home.lng, country: p.home.country, city: p.home.label });
    let data = await api("/api/match", { method: "POST", body });
    if (data.needs_geocode) {
      const hit = await geocode(data.needs_geocode).catch(() => null);
      if (hit) data = await api("/api/match", { method: "POST", body: { ...body, lat: hit.lat, lng: hit.lng, country: hit.country, city: hit.label } });
    }
    ex.items = data.recommendations; ex.profile = data.profile;
    list(data); stats(data.analysis); draw(fit);
  }
  $("#color-mode").addEventListener("change", (e) => { ex.mode = e.target.value; legend(); draw(false); });
  $("#explore-form").addEventListener("submit", (e) => { e.preventDefault(); run($("#query").value.trim(), true).catch((err) => ($("#list-meta").textContent = err.message)); });
  $("#results").addEventListener("click", (e) => {
    if (e.target.closest("a")) return;
    const card = e.target.closest(".card"); if (!card) return;
    const m = ex.markers.get(card.dataset.id);
    if (m) clusters.zoomToShowLayer(m, () => m.openPopup());
    highlight(card.dataset.id);
  });
  legend();
  return run("", true).catch((err) => ($("#list-meta").textContent = err.message));
}
