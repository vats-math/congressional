/* PlayPath single-page app: hash router + views. All data comes from the FastAPI backend. */
const TYPE_COLORS = window.TYPE_COLORS || {};
const NOMINATIM = "https://nominatim.openstreetmap.org";
const GUEST_KEY = "playpath_guest_profile";
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pct = (v) => Math.round(v * 100);

// ---------- options used by the quiz and settings ----------
const SPORTS = ["soccer", "basketball", "volleyball", "softball", "tennis", "swimming", "track", "lacrosse",
  "field hockey", "hockey", "golf", "gymnastics", "wrestling", "rugby", "netball", "multi"];
const SPORT_ICONS = { soccer: "⚽", basketball: "🏀", volleyball: "🏐", softball: "🥎", tennis: "🎾", swimming: "🏊‍♀️",
  track: "🏃‍♀️", lacrosse: "🥍", "field hockey": "🏑", hockey: "🏒", golf: "⛳", gymnastics: "🤸‍♀️", wrestling: "🤼‍♀️",
  rugby: "🏉", netball: "🏐", multi: "✨" };
const LEVELS = [
  ["beginner", "Beginner", "New to the sport or just learning the basics"],
  ["recreational", "Recreational", "I play for fun in a local league or at school"],
  ["competitive", "Competitive", "I play on a club or select team and have tried out"],
  ["elite", "Elite", "Academy, ODP, or high-performance level"],
  ["college", "College-level", "Ready to play in college"],
];
const COMPETITIONS = [
  ["rec_league", "Rec league", "Local, everyone plays"],
  ["school_team", "School team", "Middle or high school"],
  ["club_travel", "Club / travel team", "Tryouts, regional travel"],
  ["tournaments", "Tournaments & showcases", "Weekend events, ID camps"],
  ["college_recruiting", "College recruiting", "Camps, scholarships"],
  ["community", "Community programs", "Nonprofits, mentoring"],
];
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const TIMES = [["morning", "Morning"], ["afternoon", "Afternoon"], ["evening", "Evening"]];
const TRANSPORT = [
  ["car", "🚗", "I drive"], ["parent", "👨‍👩‍👧", "Family drives me"], ["carpool", "🚙", "Carpool"],
  ["transit", "🚌", "Bus / train"], ["bike_walk", "🚲", "Bike or walk"],
];
const BARRIERS = [
  ["cost", "Cost is a concern"], ["transport", "Getting there is hard"], ["time", "Limited free time"],
  ["disability", "I have a disability / want adaptive sport"], ["new_to_sport", "I'm new to the sport"],
  ["confidence", "I'm nervous about joining"],
];

// ---------- app state ----------
const state = { user: null, profile: null, maps: [] };

function loadGuest() {
  try { return JSON.parse(localStorage.getItem(GUEST_KEY) || "null"); } catch { return null; }
}
function saveGuest(p) {
  try { localStorage.setItem(GUEST_KEY, JSON.stringify(p)); } catch { /* private mode: keep in memory */ }
}
function clearGuest() {
  try { localStorage.removeItem(GUEST_KEY); } catch { /* ignore */ }
}

async function api(path, { method = "GET", body } = {}) {
  // Static build (GitHub Pages): docs/local-api.js answers the same paths in the browser.
  if (window.LOCAL_API) return window.LOCAL_API(path, { method, body });
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    credentials: "same-origin",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = typeof data.detail === "string" ? data.detail : data.detail?.[0]?.msg || `Error ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

async function saveProfile(profile) {
  state.profile = profile;
  if (state.user) await api("/api/profile", { method: "PUT", body: profile });
  else saveGuest(profile);
}

const blankProfile = () => ({
  sport: null, age: null, skill: null, competitions: [], availability: [], budget_usd: null,
  max_distance_mi: 25, transport: null, home: {}, barriers: [], goal_level: null, goal_text: "",
});

// ---------- geocoding ----------
async function geocode(place) {
  const local = await api(`/api/geocode?q=${encodeURIComponent(place)}`).catch(() => ({ found: false }));
  if (local.found) return local;
  const res = await fetch(`${NOMINATIM}/search?format=jsonv2&limit=1&addressdetails=1&accept-language=en&q=${encodeURIComponent(place)}`);
  if (!res.ok) throw new Error("Location lookup is unavailable right now.");
  const [hit] = await res.json();
  if (!hit) return null;
  return { lat: Number(hit.lat), lng: Number(hit.lon), country: hit.address?.country || null,
    label: hit.display_name.split(",").slice(0, 2).join(",").trim() };
}
async function reverseGeocode(lat, lng) {
  try {
    const r = await fetch(`${NOMINATIM}/reverse?format=jsonv2&accept-language=en&zoom=10&lat=${lat}&lon=${lng}`);
    const d = await r.json();
    return { country: d.address?.country || null, label: d.address?.city || d.address?.town || d.address?.county || "My location" };
  } catch { return { country: null, label: "My location" }; }
}
function currentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("Location isn't supported in this browser."));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve(p.coords),
      (e) => reject(new Error(`Location blocked: ${e.message}`)),
      { timeout: 10000 }
    );
  });
}

// ---------- maps ----------
function destroyMaps() {
  state.maps.forEach((m) => m.remove());
  state.maps = [];
}
function makeMap(el, opts = {}) {
  const base = {
    Streets: L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
      attribution: "&copy; OpenStreetMap contributors &copy; CARTO", maxZoom: 19 }),
    Satellite: L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Tiles &copy; Esri", maxZoom: 19 }),
  };
  const map = L.map(el, { worldCopyJump: true, minZoom: 2, layers: [base.Streets], ...opts }).setView([25, 0], 2);
  map._baseLayers = base;
  state.maps.push(map);
  return map;
}
function scoreColor(s) {
  if (s >= 85) return "#1b7f4b";
  if (s >= 70) return "#4c9a2a";
  if (s >= 55) return "#d49a1a";
  if (s >= 40) return "#d9682b";
  return "#a33a3a";
}

// ---------- shared UI ----------
const LOGO = `<svg class="logo" viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="19" fill="#12443d"/>
  <path d="M10 28 C16 28 14 13 21 13 S27 22 31 12" fill="none" stroke="#f4efe6" stroke-width="3" stroke-linecap="round"/>
  <circle cx="31" cy="12" r="3.2" fill="#d45b45"/></svg>`;

function renderNav(current) {
  const hasProfile = !!state.profile?.sport;
  const signedIn = !!state.user;
  const link = (view, href, text) => `<a href="${href}" class="${current === view ? "on" : ""}">${text}</a>`;
  let links;
  if (signedIn || hasProfile) {
    links = link("dashboard", "#/dashboard", "Dashboard") + link("explore", "#/explore", "Explore map") + link("settings", "#/settings", "Settings") +
      (signedIn ? `<button class="ghost small" data-action="signout">Sign out</button>`
                : `<a class="btn small" href="#/signup">Save my plan</a>`);
  } else {
    links = link("landing", "#/", "Home") + link("explore", "#/explore", "Explore map") + link("login", "#/login", "Sign in") +
      `<a class="btn small" href="#/signup">Get started</a>`;
  }
  $("#nav").innerHTML = `<div class="nav-inner shell">
      <a class="brand" href="${signedIn || hasProfile ? "#/dashboard" : "#/"}">${LOGO}<span>PlayPath</span></a>
      <button class="nav-toggle" aria-label="Menu" data-action="menu">☰</button>
      <nav class="nav-links">${links}</nav>
    </div>
    ${!signedIn && hasProfile ? `<div class="guest-bar">You're browsing as a guest. Your answers are saved only in this browser. <a href="#/signup">Create an account</a> to keep them.</div>` : ""}`;
}

document.addEventListener("click", async (e) => {
  const action = e.target.closest("[data-action]")?.dataset.action;
  if (action === "menu") $(".nav-links")?.classList.toggle("open");
  if (action === "signout") {
    await api("/api/auth/logout", { method: "POST" }).catch(() => {});
    state.user = null;
    state.profile = loadGuest();
    location.hash = "#/";
    render();
  }
});

function chip(name, value, label, checked, type = "checkbox") {
  return `<label class="chip"><input type="${type}" name="${name}" value="${esc(value)}" ${checked ? "checked" : ""}/><span>${label}</span></label>`;
}
function availabilityGrid(selected = []) {
  return `<div class="avail" role="group" aria-label="Availability">
    <span></span>${DAYS.map((d) => `<b>${d}</b>`).join("")}
    ${TIMES.map(([t, label]) => `<span class="avail-label">${label}</span>${DAYS.map((d) => {
      const v = `${d}-${t}`;
      return `<label class="cell" title="${d} ${label}"><input type="checkbox" name="availability" value="${v}" ${selected.includes(v) ? "checked" : ""}/><i></i></label>`;
    }).join("")}`).join("")}
  </div>`;
}
const checkedValues = (root, name) => $$(`input[name="${name}"]:checked`, root).map((i) => i.value);
const radioValue = (root, name) => $(`input[name="${name}"]:checked`, root)?.value ?? null;

function homeField(home = {}) {
  return `<div class="home-row">
      <input id="home-input" placeholder="City, e.g. Dallas, TX" value="${esc(home.label || "")}" autocomplete="off"/>
      <button type="button" class="ghost small" id="home-locate">📍 Use my location</button>
    </div><p class="hint" id="home-status">${home.lat != null ? `✓ Saved: ${esc(home.label)}${home.country ? `, ${esc(home.country)}` : ""}` : "Type your city and press Enter. We only use it to measure distance."}</p>`;
}
function wireHomeField(root, onSet) {
  const status = $("#home-status", root);
  const input = $("#home-input", root);
  $("#home-locate", root).addEventListener("click", async () => {
    status.textContent = "Locating…";
    try {
      const c = await currentPosition();
      const rev = await reverseGeocode(c.latitude, c.longitude);
      const home = { lat: c.latitude, lng: c.longitude, ...rev };
      input.value = home.label;
      status.textContent = `✓ Using ${home.label}${home.country ? `, ${home.country}` : ""}`;
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
      status.textContent = `✓ Found ${hit.label}${hit.country ? `, ${hit.country}` : ""}`;
      onSet({ lat: hit.lat, lng: hit.lng, label: hit.label, country: hit.country });
    } catch (err) { status.textContent = err.message; }
  };
  input.addEventListener("change", lookup);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); input.blur(); } });
}

function deadlineText(item) {
  if (!item.next_deadline) return "Rolling / see site";
  return item.deadline_estimated ? `${item.next_deadline} (est.)` : item.next_deadline;
}
function miniCard(item, extra = "") {
  return `<a class="mini" href="#/opportunity/${encodeURIComponent(item.id)}">
    <span class="score sm" style="background:${scoreColor(item.compatibility)}">${item.compatibility}</span>
    <span class="mini-body"><strong>${esc(item.name)}</strong>
    <span class="meta"><span class="dot" style="background:${TYPE_COLORS[item.type]}"></span>${esc(item.type)} · ${esc(item.distance)} · ${esc(item.cost)}</span>${extra}</span></a>`;
}

// ---------- views ----------
const views = {};

views.landing = () => `
  <section class="hero">
    <div>
      <p class="kicker">For girls and women in sport</p>
      <h1>Find where you <em>play</em> next.</h1>
      <p class="lede">PlayPath matches you with real teams, leagues, camps, and programs from schools, colleges,
        rec centers, nonprofits, and clubs, ranked by how well they fit you.</p>
      <div class="cta">
        <a class="btn" href="#/signup">Find my opportunities</a>
        <a class="btn ghost" href="#/explore">Explore the map</a>
      </div>
      <a class="textlink" href="#/quiz" data-guest="1">or continue as a guest →</a>
    </div>
    <div class="hero-art" aria-hidden="true">
      <div class="hero-card"><span class="score" style="background:#1b7f4b">94</span><div><b>Dallas Cup Girls Divisions</b><small>Tournament · 9 mi · travel</small></div></div>
      <div class="hero-card"><span class="score" style="background:#4c9a2a">82</span><div><b>YMCA Youth Soccer (Girls)</b><small>Recreation · local chapter</small></div></div>
      <div class="hero-card"><span class="score" style="background:#d49a1a">67</span><div><b>College ID Camp</b><small>College · 450 mi</small></div></div>
      <p class="hero-note">Example scores. Yours depend on your answers.</p>
    </div>
  </section>

  <section class="why-section">
    <div>
      <h2>Why we built this</h2>
      <p>By age 14, girls drop out of sports at about twice the rate of boys. One reason is simply not knowing what's
        out there, what it costs, or whether they're eligible. The options are scattered across hundreds of club
        sites, school pages, and rec department flyers.</p>
      <p>We wanted one place that gathers them, explains them honestly, and points each athlete to her next step.</p>
    </div>
    <ul class="facts">
      <li><b>Real listings</b><span>Every result is a program in our database with a link to its official site. Nothing is generated.</span></li>
      <li><b>Worldwide map</b><span>See where programs are, how clustered they are, and what's affordable.</span></li>
      <li><b>Honest about gaps</b><span>Our data is strongest for U.S. soccer right now, and we say so.</span></li>
    </ul>
  </section>

  <section class="how">
    <h2>How it works</h2>
    <ol class="steps">
      <li><span>1</span><b>Take the quiz</b><p>Sport, age, level, schedule, budget, how you get around, and anything that makes it harder to play.</p></li>
      <li><span>2</span><b>We score every program</b><p>A ranking algorithm weighs 9 factors, including sport, age, skill, distance, cost, travel, and deadlines, and checks eligibility.</p></li>
      <li><span>3</span><b>Get your plan</b><p>A weekly plan built around your free time, a suggested next level, and a pathway toward your goal.</p></li>
      <li><span>4</span><b>Explore and adjust</b><p>Browse the map, open any program to see why it matches, and change your answers anytime.</p></li>
    </ol>
  </section>`;
views.landing.after = () => {
  $("[data-guest]")?.addEventListener("click", () => { if (!state.profile) state.profile = blankProfile(); });
};

function authView(mode) {
  const signup = mode === "signup";
  return `<section class="auth">
    <div class="auth-card">
      <div class="auth-brand">${LOGO}<span>PlayPath</span></div>
      <h1>${signup ? "Create your account" : "Welcome back"}</h1>
      <form id="auth-form" novalidate>
        ${signup ? `<label class="stack">Name<input name="name" autocomplete="given-name" placeholder="First name"/></label>` : ""}
        <label class="stack">Email<input name="email" type="email" autocomplete="email" required placeholder="you@example.com"/></label>
        <label class="stack">Password<input name="password" type="password" autocomplete="${signup ? "new-password" : "current-password"}" required minlength="8" placeholder="${signup ? "At least 8 characters" : "Your password"}"/></label>
        <p class="form-error" id="auth-error" role="alert"></p>
        <button class="btn wide" type="submit">${signup ? "Create account" : "Sign in"}</button>
      </form>
      ${window.LOCAL_API ? `<p class="hint">This version runs fully in your browser. Your account is saved on this device only.</p>` : ""}
      <p class="auth-alt">${signup ? `Already have an account? <a href="#/login">Sign in</a>` : `New here? <a href="#/signup">Create an account</a>`}</p>
      <div class="divider"><span>or</span></div>
      <a class="btn ghost wide" href="#/quiz" id="guest-btn">Continue as guest</a>
    </div>
  </section>`;
}
views.login = () => authView("login");
views.signup = () => authView("signup");
views.login.after = views.signup.after = () => {
  const signup = location.hash.startsWith("#/signup");
  $("#guest-btn").addEventListener("click", () => { if (!state.profile) state.profile = blankProfile(); });
  $("#auth-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const btn = $("button[type=submit]", e.target);
    btn.disabled = true;
    try {
      const data = await api(signup ? "/api/auth/signup" : "/api/auth/login", {
        method: "POST", body: { email: f.get("email"), password: f.get("password"), name: f.get("name") || "" } });
      state.user = data.user;
      const guest = loadGuest();
      if (data.profile) state.profile = data.profile;
      else if (guest?.sport) { await saveProfile(guest); clearGuest(); } // carry guest answers into the new account
      else state.profile = null;
      location.hash = state.profile?.sport ? "#/dashboard" : "#/quiz";
    } catch (err) {
      $("#auth-error").textContent = err.message;
    } finally { btn.disabled = false; }
  });
};

// ----- quiz -----
const QUIZ_STEPS = [
  { title: "What sport do you play, or want to play?",
    render: (p) => `<div class="chips grid4">${SPORTS.map((s) => chip("sport", s, `${SPORT_ICONS[s]} ${s === "multi" ? "Not sure yet" : s}`, p.sport === s, "radio")).join("")}</div>`,
    read: (r, p) => { p.sport = radioValue(r, "sport"); return p.sport ? null : "Pick a sport (or “Not sure yet”)."; } },
  { title: "How old are you?",
    render: (p) => `<input class="big-input" name="age" type="number" min="5" max="80" inputmode="numeric" value="${p.age ?? ""}" placeholder="14"/>
      <p class="hint">Programs have age limits. We only recommend ones you can join.</p>`,
    read: (r, p) => { const v = Number($("[name=age]", r).value); if (!v || v < 5 || v > 80) return "Enter an age between 5 and 80."; p.age = v; return null; } },
  { title: "What's your experience level?",
    render: (p) => `<div class="options">${LEVELS.map(([v, l, d]) => `<label class="option"><input type="radio" name="skill" value="${v}" ${p.skill === v ? "checked" : ""}/><span><b>${l}</b><small>${d}</small></span></label>`).join("")}</div>
      <label class="stack">Skills you want to work on (optional)<input name="goal_text" maxlength="300" value="${esc(p.goal_text)}" placeholder="e.g. footwork, speed, getting noticed by college coaches"/></label>`,
    read: (r, p) => { p.skill = radioValue(r, "skill"); p.goal_text = $("[name=goal_text]", r).value.trim(); return p.skill ? null : "Choose the level closest to you."; } },
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
    render: (p) => `<div class="options three">${TRANSPORT.map(([v, i, l]) => `<label class="option center"><input type="radio" name="transport" value="${v}" ${p.transport === v ? "checked" : ""}/><span><em>${i}</em><b>${l}</b></span></label>`).join("")}</div>`,
    read: (r, p) => { p.transport = radioValue(r, "transport"); return p.transport ? null : "Choose how you'll usually travel."; } },
  { title: "Anything that makes playing harder? And what's your goal?", sub: "Optional. This helps us suggest the right programs.",
    render: (p) => `<div class="chips">${BARRIERS.map(([v, l]) => chip("barriers", v, l, p.barriers.includes(v))).join("")}</div>
      <label class="stack">My goal is to reach…<select name="goal_level"><option value="">Just have fun / not sure</option>${LEVELS.map(([v, l]) => `<option value="${v}" ${p.goal_level === v ? "selected" : ""}>${l}</option>`).join("")}</select></label>`,
    read: (r, p) => { p.barriers = checkedValues(r, "barriers"); p.goal_level = $("[name=goal_level]", r).value || null; return null; } },
];

let quizDraft = null;
let quizStep = 0;
views.quiz = () => {
  if (!quizDraft) { quizDraft = structuredClone({ ...blankProfile(), ...(state.profile || {}) }); quizStep = 0; }
  const step = QUIZ_STEPS[quizStep];
  return `<section class="quiz">
    <div class="progress"><i style="width:${(100 * (quizStep + 1)) / QUIZ_STEPS.length}%"></i></div>
    <p class="kicker">Question ${quizStep + 1} of ${QUIZ_STEPS.length}</p>
    <h1>${step.title}</h1>${step.sub ? `<p class="lede">${step.sub}</p>` : ""}
    <form id="quiz-form" novalidate>${step.render(quizDraft)}
      <p class="form-error" id="quiz-error" role="alert"></p>
      <div class="quiz-nav">
        ${quizStep ? `<button type="button" class="ghost" id="quiz-back">Back</button>` : "<span></span>"}
        <button type="submit" class="btn">${quizStep === QUIZ_STEPS.length - 1 ? "Build my plan" : "Next"}</button>
      </div>
    </form></section>`;
};
views.quiz.after = () => {
  const form = $("#quiz-form");
  const step = QUIZ_STEPS[quizStep];
  step.after?.(form, quizDraft);
  $("#quiz-back")?.addEventListener("click", () => { step.read(form, quizDraft); quizStep--; render(); });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = step.read(form, quizDraft);
    if (err) { $("#quiz-error").textContent = err; return; }
    if (quizStep < QUIZ_STEPS.length - 1) { quizStep++; render(); return; }
    await saveProfile(quizDraft);
    quizDraft = null;
    location.hash = "#/dashboard";
  });
};

// ----- dashboard -----
views.dashboard = () => `<section id="dash"><p class="loading">Building your plan…</p></section>`;
views.dashboard.after = async () => {
  if (!state.profile?.sport) { location.hash = "#/quiz"; return; }
  const plan = await api("/api/plan", { method: "POST", body: state.profile });
  const p = state.profile;
  const name = state.user?.name || "there";
  const sessions = plan.sessions.length
    ? plan.sessions.map((s) => `<a class="session" href="#/opportunity/${encodeURIComponent(s.id)}">
        <div class="session-day"><b>${s.day}</b><small>${esc(s.time)}</small></div>
        <div class="session-body"><strong>${esc(s.name)}</strong>
          <span class="meta">📍 ${esc(s.distance)} · 💲 ${esc(s.cost)}</span>
          <span class="meta muted">Your free slot. Confirm the practice time on the program's site.</span></div>
        <span class="score sm" style="background:${scoreColor(s.compatibility)}">${s.compatibility}</span></a>`).join("")
    : `<p class="empty">${plan.no_slots ? "Add your free times in Settings to get a weekly plan." : "No eligible weekly programs within your travel range yet. Try a bigger distance in Settings, or check the map."}</p>`;
  const up = plan.step_up;
  $("#dash").innerHTML = `
    <div class="dash-head">
      <div><p class="kicker">Your plan · ${esc(p.sport)} · age ${esc(p.age)}</p><h1>Hi ${esc(name)} 👋</h1>
      <p class="lede">Built from your quiz answers and ranked against every program in our database.</p></div>
      <div class="dash-actions"><a class="btn ghost small" href="#/settings">Edit answers</a><a class="btn small" href="#/explore">Open map</a></div>
    </div>
    <div class="dash-grid">
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
};

function pathwayHtml(steps) {
  return `<div class="pathway">${steps.map((s, i) => `
    <div class="pstep ${s.status}${s.is_goal ? " goal" : ""}">
      ${s.status === "current" ? `<span class="here">📍 You are here</span>` : ""}
      ${s.is_goal ? `<span class="flag">🏁 Goal</span>` : ""}
      <span class="pdot">${s.status === "past" ? "✓" : i + 1}</span>
      <b>${esc(s.label)}</b>
      ${s.example ? `<a href="#/opportunity/${encodeURIComponent(s.example.id)}">${esc(s.example.name)}</a>` : `<small>No program in range</small>`}
    </div>${i < steps.length - 1 ? `<span class="arrow" aria-hidden="true">→</span>` : ""}`).join("")}</div>
    <div class="goal-row"><button type="button" class="ghost small" id="change-goal">Change my goal</button>
      <span id="goal-editor" hidden><select id="goal-select"><option value="">Just have fun</option>${LEVELS.map(([v, l]) => `<option value="${v}" ${state.profile?.goal_level === v ? "selected" : ""}>${l}</option>`).join("")}</select>
      <button type="button" class="btn small" id="goal-save">Save goal</button></span></div>`;
}
function wirePathway() {
  $("#change-goal")?.addEventListener("click", () => { $("#goal-editor").hidden = false; $("#goal-select").focus(); });
  $("#goal-save")?.addEventListener("click", async () => {
    await saveProfile({ ...state.profile, goal_level: $("#goal-select").value || null });
    render();
  });
}

// ----- opportunity detail -----
views.opportunity = () => `<section id="opp"><p class="loading">Loading…</p></section>`;
views.opportunity.after = async (id) => {
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
        ${o.reasons.strong.length ? `<p class="why good">✓ Strong on ${esc(o.reasons.strong.join(", "))}</p>` : ""}
        ${o.reasons.weak.length ? `<p class="why weak">✗ Weaker on ${esc(o.reasons.weak.join(", "))}</p>` : ""}
        ${flags.map((f) => `<p class="why warn">⚠ ${esc(f)}</p>`).join("")}
        <div class="factor-bars">${Object.entries(o.factors).map(([k, v]) => `<div class="bar-row"><span>${k}</span><i style="width:${pct(v)}%"></i><b>${pct(v)}</b></div>`).join("")}</div>
      </div>
      <div class="panel span3"><h2>Your pathway</h2>${personal ? pathwayHtml(data.pathway) : `<p class="empty">Take the quiz to see your pathway.</p>`}
        <p class="hint">This program covers: <b>${esc(o.skill_levels.join(", "))}</b>.</p></div>
      <div class="panel span3"><h2>Similar programs</h2><div class="minis row">${data.similar.map((s) => `<a class="mini" href="#/opportunity/${encodeURIComponent(s.id)}"><span class="score sm" style="background:${scoreColor(s.compatibility)}">${s.compatibility}</span><span class="mini-body"><strong>${esc(s.name)}</strong><span class="meta">${esc(s.type)}</span></span></a>`).join("")}</div></div>
    </div>`;
  if (personal) wirePathway();
  const map = makeMap($("#opp-map"), { scrollWheelZoom: false });
  const pt = [o.lat, o.lng];
  L.circleMarker(pt, { radius: 11, color: "#14201e", weight: 2, fillColor: TYPE_COLORS[o.type], fillOpacity: 0.95 }).addTo(map).bindPopup(esc(o.name));
  const home = state.profile?.home;
  if (home?.lat != null && !localChapters) {
    const h = [home.lat, home.lng];
    L.circleMarker(h, { radius: 8, color: "#d45b45", fillColor: "#fff", fillOpacity: 1, weight: 3 }).addTo(map).bindPopup("Home");
    L.polyline([h, pt], { color: "#d45b45", weight: 2, dashArray: "6 6" }).addTo(map);
    map.fitBounds(L.latLngBounds([h, pt]).pad(0.3), { maxZoom: 11 });
  } else map.setView(pt, 10);
};

// ----- explore (world map + ranked list) -----
views.explore = () => `
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
views.explore.after = () => {
  const ex = { items: [], profile: {}, mode: "type", markers: new Map() };
  const map = makeMap($("#map"));
  const clusters = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 45,
    iconCreateFunction: (c) => { const n = c.getChildCount(), s = n < 10 ? 30 : n < 50 ? 38 : 46;
      return L.divIcon({ html: `<span>${n}</span>`, className: "cluster", iconSize: [s, s] }); } }).addTo(map);
  const heat = L.heatLayer([], { radius: 28, blur: 22, maxZoom: 9, minOpacity: 0.25 });
  const homeLayer = L.layerGroup().addTo(map);
  L.control.layers(map._baseLayers, { Opportunities: clusters, "Density heatmap": heat, "Home & radius": homeLayer }).addTo(map);
  L.control.scale().addTo(map);

  const affordColor = (a) => (a >= 0.95 ? "#1b7f4b" : a >= 0.8 ? "#6aa84f" : a >= 0.5 ? "#d49a1a" : "#c0392b");
  const colorFor = (i) => ex.mode === "score" ? scoreColor(i.compatibility) : ex.mode === "affordability" ? affordColor(i.affordability)
    : ex.mode === "eligibility" ? (i.eligible ? "#1b7f4b" : i.residency_ok ? "#d49a1a" : "#8a8a8a") : TYPE_COLORS[i.type] || "#888";
  const legend = () => {
    const row = (c, t) => `<div class="legend-row"><span class="swatch" style="background:${c}"></span>${t}</div>`;
    const sets = {
      score: ["Compatibility", [["#1b7f4b", "85–100"], ["#4c9a2a", "70–84"], ["#d49a1a", "55–69"], ["#d9682b", "40–54"], ["#a33a3a", "under 40"]]],
      affordability: ["Cost", [["#1b7f4b", "Free"], ["#6aa84f", "Low"], ["#d49a1a", "Moderate / unknown"], ["#c0392b", "High"]]],
      eligibility: ["Eligibility", [["#1b7f4b", "Eligible"], ["#d49a1a", "Age or distance outside range"], ["#8a8a8a", "Residency / not joinable"]]],
      type: ["Type", Object.entries(TYPE_COLORS).map(([t, c]) => [c, t])],
    };
    const [title, rows] = sets[ex.mode];
    $("#legend").innerHTML = `<strong>${title}</strong>${rows.map(([c, t]) => row(c, t)).join("")}<div class="legend-note">Bigger dot = higher score</div>`;
  };

  function draw(fit) {
    clusters.clearLayers(); homeLayer.clearLayers(); ex.markers.clear();
    ex.items.forEach((i) => {
      const m = L.circleMarker([i.lat, i.lng], { radius: 5 + i.compatibility / 12, color: i.eligible ? "#14201e" : "#777",
        weight: i.eligible ? 1.5 : 1, dashArray: i.eligible ? null : "2 3", fillColor: colorFor(i), fillOpacity: i.eligible ? 0.9 : 0.55 })
        .bindPopup(`<div class="pop"><strong>${i.compatibility} · ${esc(i.name)}</strong><br>${esc(i.type)} · ${esc(i.city)}, ${esc(i.country)}<br>${esc(i.cost_label)}<br><a href="#/opportunity/${encodeURIComponent(i.id)}">View details →</a></div>`);
      m.on("click", () => highlight(i.id));
      ex.markers.set(i.id, m); clusters.addLayer(m);
    });
    heat.setLatLngs(ex.items.map((i) => [i.lat, i.lng, 0.3 + i.compatibility / 140]));
    const p = ex.profile;
    if (p.lat != null) {
      L.circleMarker([p.lat, p.lng], { radius: 9, color: "#d45b45", fillColor: "#fff", fillOpacity: 1, weight: 3 }).bindPopup("Home").addTo(homeLayer);
      if (p.max_distance_km) L.circle([p.lat, p.lng], { radius: p.max_distance_km * 1000, color: "#d45b45", weight: 1.5, fillOpacity: 0.04, dashArray: "6 6" }).addTo(homeLayer);
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
        ${i.reasons.strong.length ? `<p class="why good">✓ ${esc(i.reasons.strong.join(", "))}</p>` : ""}
        ${!i.eligible ? `<p class="why warn">⚠ Check eligibility</p>` : ""}
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
};

// ----- settings -----
views.settings = () => {
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
        <h3>How I get there</h3><div class="chips">${TRANSPORT.map(([v, i, l]) => chip("transport", v, `${i} ${l}`, p.transport === v, "radio")).join("")}</div>
      </div>
      <div class="panel"><h2>Challenges</h2><div class="chips">${BARRIERS.map(([v, l]) => chip("barriers", v, l, p.barriers.includes(v))).join("")}</div></div>
      <div class="save-bar"><span id="save-status" role="status"></span><a class="ghost btn" href="#/quiz" id="retake">Retake quiz</a><button class="btn" type="submit">Save changes</button></div>
    </form></section>`;
};
views.settings.after = () => {
  const form = $("#settings-form");
  let home = state.profile.home || {};
  wireHomeField(form, (h) => (home = h));
  $("#retake").addEventListener("click", () => { quizDraft = null; });
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
      goal_text: (f.get("goal_text") || "").trim(), competitions: checkedValues(form, "competitions"),
      budget_usd: num("budget_usd"), availability: checkedValues(form, "availability"), home,
      max_distance_mi: num("max_distance_mi"), transport: radioValue(form, "transport"), barriers: checkedValues(form, "barriers"),
    };
    try {
      if (state.user && f.get("name") != null) state.user = (await api("/api/me", { method: "PUT", body: { name: f.get("name") } })).user;
      await saveProfile(next);
      $("#save-status").textContent = "✓ Saved. Your plan is updated.";
      renderNav("settings");
    } catch (err) { $("#save-status").textContent = err.message; }
  });
};

// ---------- router ----------
const ROUTES = [
  [/^#\/?$/, "landing"], [/^#\/login$/, "login"], [/^#\/signup$/, "signup"], [/^#\/quiz$/, "quiz"],
  [/^#\/dashboard$/, "dashboard"], [/^#\/explore$/, "explore"], [/^#\/settings$/, "settings"],
  [/^#\/opportunity\/(.+)$/, "opportunity"],
];
async function render() {
  destroyMaps();
  const hash = location.hash || "#/";
  let name = "landing", arg;
  for (const [re, view] of ROUTES) {
    const m = hash.match(re);
    if (m) { name = view; arg = m[1] && decodeURIComponent(m[1]); break; }
  }
  if (name === "landing" && (state.user || state.profile?.sport)) name = "dashboard";
  if ((name === "login" || name === "signup") && state.user) name = "dashboard";
  if (name !== "quiz") quizDraft = null;
  renderNav(name);
  const view = $("#view");
  view.innerHTML = views[name](arg);
  view.dataset.view = name;
  window.scrollTo(0, 0);
  try { await views[name].after?.(arg); } catch (err) { view.insertAdjacentHTML("beforeend", `<p class="form-error">${esc(err.message)}</p>`); }
}
window.addEventListener("hashchange", render);

(async function boot() {
  const me = await api("/api/me").catch(() => ({ user: null, profile: null }));
  state.user = me.user;
  state.profile = me.user ? me.profile : loadGuest();
  render();
})();
