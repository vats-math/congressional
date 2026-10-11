/* PlayPath engine for the no-server (GitHub Pages) version.
 * JavaScript port of app/parser.py, app/ranking.py, app/recommender.py, app/analysis.py and app/plan.py.
 * Keep it in step with the Python code when the scoring rules change. */
(function () {
  const D = window.PLAYPATH_DATA;
  const SCOPE_NATIONAL = new Set(D.scopeNational);
  const SCOPE_RESOURCE = new Set(D.scopeResource);
  const ADAPTIVE_ONLY = new Set(D.adaptiveOnly);
  const KM_PER_MI = 1.60934;
  const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
  const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const round = (v, d = 0) => { const f = 10 ** d; return Math.round(v * f) / f; };

  // ---------------- parser ----------------
  const SPORT_ALIASES = {
    soccer: ["soccer", "football", "futbol", "fútbol", "footy", "goalkeeper"],
    basketball: ["basketball", "hoops", "bball", "wnba"],
    volleyball: ["volleyball", "vb"],
    softball: ["softball", "fastpitch"],
    tennis: ["tennis"],
    swimming: ["swimming", "swim", "swimmer", "aquatic"],
    track: ["track", "running", "runner", "sprinter", "cross country", "xc", "5k"],
    lacrosse: ["lacrosse", "lax"],
    "field hockey": ["field hockey"],
    hockey: ["hockey", "ice hockey"],
    golf: ["golf", "golfer"],
    gymnastics: ["gymnastics", "gymnast"],
    wrestling: ["wrestling", "wrestle", "wrestler"],
    rugby: ["rugby"],
    netball: ["netball"],
    multi: ["sport", "sports", "athlete", "multi"],
  };
  const SKILL_PATTERNS = [
    ["elite", /\b(elite|odp|national team|academy|high[-\s]?performance)\b/i],
    ["competitive", /\b(competitive|club|travel team|select|showcase)\b/i],
    ["college", /\b(college[-\s]level|ncaa|d1|division\s?i)\b/i],
    ["recreational", /\b(recreational|rec\b|casual|fun|beginner-friendly)\b/i],
    ["beginner", /\b(beginner|new to|never played|just starting)\b/i],
  ];
  const CITIES_BY_LEN = [...D.cities].sort((a, b) => b.name.length - a.name.length);
  const title = (s) => s.replace(/\b\w/g, (c) => c.toUpperCase());

  function findSport(t) {
    for (const [sport, aliases] of Object.entries(SPORT_ALIASES)) {
      for (const a of [...aliases].sort((x, y) => y.length - x.length)) {
        if (new RegExp(`\\b${escapeRe(a)}\\b`).test(t)) return sport;
      }
    }
    return null;
  }
  function findAge(t) {
    let m = t.match(/\b(?:i(?:['’]?m| am)?|age)\s*(\d{1,2})\b/);
    if (!m) m = t.match(/\b(\d{1,2})\s*(?:years?\s*old|yo)\b/);
    if (!m) return null;
    const a = Number(m[1]);
    return a >= 3 && a <= 80 ? a : null;
  }
  const findSkill = (t) => (SKILL_PATTERNS.find(([, re]) => re.test(t)) || [null])[0];
  function findTravel(t) {
    if (/\b(travel|showcase|tournament|odp|national|away|id camp)\b/i.test(t)) return true;
    if (/\b(local only|stay local|no travel|recreational only)\b/i.test(t)) return false;
    return null;
  }
  function findBudget(t) {
    let m = t.match(/\$\s?(\d{2,5})/);
    if (m) return Number(m[1]);
    m = t.match(/\b(?:under|below|less than|max)\s+(\d{2,5})(?!\s*(?:miles?|mi|km|kilomet))\b/);
    if (m) return Number(m[1]);
    if (/\b(free|no cost|low[-\s]?cost|affordable)\b/i.test(t)) return 200;
    return null;
  }
  function findDistanceKm(t) {
    let m = t.match(/within\s+(\d{1,4})\s*(?:miles?|mi)\b/i);
    if (m) return Number(m[1]) * KM_PER_MI;
    m = t.match(/within\s+(\d{1,4})\s*km\b/i);
    return m ? Number(m[1]) : null;
  }
  const findCity = (t) => CITIES_BY_LEN.find((c) => new RegExp(`\\b${escapeRe(c.name)}\\b`).test(t)) || null;
  function findPlacePhrase(t) {
    const m = t.match(/\b(?:near|around|in|from|close to)\s+([a-z][a-z .'-]{2,40}?)(?:\s+(?:and|but|for|to|with|who|that|within|under|looking|want|wants|play|playing|i|im)\b|[,.;!?]|$)/);
    if (!m) return null;
    const place = m[1].trim();
    return ["the area", "my area", "town", "high school", "college", "school"].includes(place) ? null : place;
  }
  function intentTypes(t) {
    const map = [
      ["college", /\b(college|ncaa|university|scholarship)\b/i],
      ["school", /\b(high school|school team|hs\b)\b/i],
      ["recreation", /\b(rec|parks?|ymca|ayso)\b/i],
      ["nonprofit", /\b(nonprofit|free program|community)\b/i],
      ["club", /\b(club team|academy|travel team)\b/i],
      ["national", /\b(national|odp|federation|tournament)\b/i],
    ];
    return map.filter(([, re]) => re.test(t)).map(([k]) => k);
  }
  function parseQuery(query, base = {}) {
    const p = { ...base };
    const t = (query || "").trim().toLowerCase();
    if (!t) return p;
    const sport = findSport(t); if (sport) p.sport = sport;
    const age = findAge(t); if (age != null) p.age = age;
    const skill = findSkill(t); if (skill) p.skill = skill;
    const travel = findTravel(t); if (travel != null) p.wants_travel = travel;
    const budget = findBudget(t); if (budget != null) p.budget_usd = budget;
    const dist = findDistanceKm(t); if (dist != null) p.max_distance_km = dist;
    const city = findCity(t);
    if (city && p.lat == null) Object.assign(p, { lat: city.lat, lng: city.lng, home_label: title(city.name), home_country: city.country });
    else if (!city && p.lat == null) { const place = findPlacePhrase(t); if (place) p.place_query = place; }
    if (/\b(disabilit\w*|adaptive|special olympics|para[-\s]?athlete|intellectual)\b/.test(t)) p.adaptive = true;
    const types = intentTypes(t); if (types.length) p.intent_types = types;
    p.raw_query = query;
    return p;
  }
  function resolveHome(cityQuery, lat, lng, country) {
    if (lat != null && lng != null) return { lat, lng, home_label: cityQuery || "Your location", home_country: country };
    if (cityQuery) {
      const c = findCity(cityQuery.toLowerCase());
      if (c) return { lat: c.lat, lng: c.lng, home_label: title(c.name), home_country: c.country };
      return { place_query: cityQuery.trim() };
    }
    return {};
  }

  // ---------------- TF-IDF recommender ----------------
  const STOP = new Set(("a an and are as at be for from i im in is it my of on or the to want with find play looking " +
    "am me near into who that this years old opportunities").split(" "));
  const tokenize = (s) => (s.toLowerCase().match(/[a-z]+/g) || []).filter((w) => w.length > 2 && !STOP.has(w));
  const docText = (o) => [o.name, o.organization, o.type, o.sport, o.sport, o.skill_levels.join(" "), o.description,
    o.eligibility, o.city, o.region, o.country, o.is_travel ? "travel" : "local"].join(" ");
  const counts = (toks) => toks.reduce((m, t) => m.set(t, (m.get(t) || 0) + 1), new Map());
  class TfidfIndex {
    constructor(rows) {
      const docs = rows.map((r) => counts(tokenize(docText(r))));
      const n = Math.max(docs.length, 1);
      const df = new Map();
      docs.forEach((d) => d.forEach((_, t) => df.set(t, (df.get(t) || 0) + 1)));
      this.idf = new Map([...df].map(([t, c]) => [t, Math.log((1 + n) / (1 + c)) + 1]));
      this.vectors = new Map(rows.map((r, i) => [r.id, this.weigh(docs[i])]));
    }
    weigh(c) {
      const v = new Map();
      c.forEach((cnt, t) => { const w = (1 + Math.log(cnt)) * (this.idf.get(t) || 0); if (w) v.set(t, w); });
      const norm = Math.sqrt([...v.values()].reduce((s, x) => s + x * x, 0)) || 1;
      v.forEach((w, t) => v.set(t, w / norm));
      return v;
    }
    static cos(a, b) { if (a.size > b.size) [a, b] = [b, a]; let s = 0; a.forEach((w, t) => (s += w * (b.get(t) || 0))); return s; }
    queryScores(text) {
      const q = this.weigh(counts(tokenize(text)));
      if (!q.size) return new Map();
      return new Map([...this.vectors].map(([id, v]) => [id, TfidfIndex.cos(q, v)]));
    }
    similar(id, k = 5) {
      const base = this.vectors.get(id);
      if (!base) return [];
      return [...this.vectors].filter(([i]) => i !== id).map(([i, v]) => [i, TfidfIndex.cos(base, v)])
        .sort((a, b) => b[1] - a[1]).slice(0, k);
    }
  }
  const INDEX = new TfidfIndex(D.catalog);

  // ---------------- ranking ----------------
  function haversineKm(lat1, lng1, lat2, lng2) {
    const r = Math.PI / 180, dp = (lat2 - lat1) * r, dl = (lng2 - lng1) * r;
    const a = Math.sin(dp / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dl / 2) ** 2;
    return 2 * 6371 * Math.asin(Math.sqrt(a));
  }
  const RELATED = { soccer: ["track"], track: ["soccer"], softball: ["baseball"] };
  function sportScore(u, o) {
    if (!u) return 0.55;
    if (u === "multi" || o === "multi") return 0.72;
    if (u === o) return 1;
    return (RELATED[u] || []).includes(o) ? 0.35 : 0.08;
  }
  function ageScore(age, lo, hi) {
    if (age == null) return [0.6, true];
    if (age >= lo && age <= hi) return [1 - (0.15 * Math.abs(age - (lo + hi) / 2)) / Math.max(hi - lo, 1), true];
    return [clamp(0.35 - 0.08 * (age < lo ? lo - age : age - hi)), false];
  }
  const SKILL_RANK = { beginner: 0, recreational: 1, competitive: 2, elite: 3, college: 4 };
  function skillScore(u, levels, wantsTravel) {
    if (!u) return 0.55;
    const target = SKILL_RANK[u] ?? 1;
    const best = Math.min(...levels.map((s) => Math.abs(target - (SKILL_RANK[s] ?? 1))));
    let base = [1, 0.78, 0.45, 0.22, 0.1][Math.min(best, 4)];
    if (wantsTravel && levels.includes("elite")) base = Math.min(1, base + 0.08);
    return base;
  }
  function travelScore(w, isTravel, type) {
    if (w == null) return 0.5;
    if (w) return isTravel ? (["club", "national", "college"].includes(type) ? 1 : 0.85) : 0.18;
    return isTravel ? 0.4 : 0.95;
  }
  function proximityScore(home, lat, lng, maxKm) {
    if (!home) return [0.5, null, true];
    const d = haversineKm(home[0], home[1], lat, lng);
    const cap = maxKm || 4000;
    if (d > cap) return [clamp((0.15 * cap) / d), d, false];
    return [clamp(Math.exp(-d / (cap * 0.55))), d, true];
  }
  function affordScore(budget, cost) {
    if (cost == null || cost === 0) return 1;
    if (budget == null) return clamp(1 - cost / 8000);
    if (cost <= budget) return 1 - 0.15 * (cost / Math.max(budget, 1));
    return clamp(0.55 - 0.35 * ((cost - budget) / Math.max(budget, 1)));
  }
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  function nextDeadline(s) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || "");
    if (!m) return [null, false];
    const now = new Date(); const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const due = new Date(+m[1], +m[2] - 1, +m[3]);
    if (due >= today) return [due, false];
    for (const y of [today.getFullYear(), today.getFullYear() + 1]) {
      let c = new Date(y, +m[2] - 1, +m[3]);
      if (c.getMonth() !== +m[2] - 1) c = new Date(y, +m[2] - 1, 28); // Feb 29
      if (c >= today) return [c, true];
    }
    return [null, false];
  }
  function deadlineScore(due) {
    if (!due) return 0.6;
    const days = Math.floor((due - new Date(new Date().toDateString())) / 86400000);
    if (days < 14) return 0.7;
    if (days < 60) return 0.95;
    if (days < 180) return 1;
    return 0.8;
  }
  const typeScore = (types, t) => (!types || !types.length ? 0.55 : types.includes(t) ? 1 : 0.28);
  const WEIGHTS = { sport: 0.22, age: 0.16, skill: 0.11, travel: 0.11, proximity: 0.18, affordability: 0.1, deadline: 0.04, type: 0.03, relevance: 0.05 };
  const LABELS = { sport: "sport", age: "age range", skill: "skill level", travel: "travel preference", proximity: "distance",
    affordability: "cost", deadline: "deadline timing", type: "program type", relevance: "prompt keywords" };
  function scopeFor(id) {
    if (SCOPE_RESOURCE.has(id)) return ["resource", null];
    if (SCOPE_NATIONAL.has(id)) return ["national", null];
    if (id in D.scopeRegionalKm) return ["regional", D.scopeRegionalKm[id]];
    return ["open", null];
  }
  function reasons(f, p) {
    const asked = { sport: p.sport, age: p.age, skill: p.skill, travel: p.wants_travel, proximity: p.lat, affordability: p.budget_usd,
      type: p.intent_types, relevance: p.raw_query, deadline: true };
    const has = (k) => asked[k] !== undefined && asked[k] !== null;
    return { strong: Object.keys(f).filter((k) => f[k] >= 0.85 && has(k)).map((k) => LABELS[k]),
      weak: Object.keys(f).filter((k) => f[k] < 0.4 && has(k)).map((k) => LABELS[k]) };
  }
  function affordabilityIndex(cost) {
    if (cost == null) return 0.5;
    if (cost <= 0) return 1;
    return round(Math.max(0, 1 - Math.min(cost, 8000) / 8000) ** 1.5, 3);
  }
  function rankOpportunity(p, o, relevance) {
    const home = p.lat != null && p.lng != null ? [Number(p.lat), Number(p.lng)] : null;
    const sport = sportScore(p.sport, o.sport);
    const [age, eligibleAge] = ageScore(p.age, o.min_age, o.max_age);
    const skill = skillScore(p.skill, o.skill_levels, p.wants_travel);
    const travel = travelScore(p.wants_travel, o.is_travel, o.type);
    let [proximity, dist, within] = proximityScore(home, o.lat, o.lng, p.max_distance_km);
    const [scope, scopeKm] = scopeFor(o.id);
    let residencyOk = true;
    if (scope === "national") {
      if (p.home_country) { residencyOk = p.home_country === o.country; if (residencyOk) { proximity = Math.max(proximity, 0.85); within = true; } }
    } else if (scope === "regional" && dist != null) residencyOk = dist <= (scopeKm || 0);
    if (ADAPTIVE_ONLY.has(o.id) && !p.adaptive) residencyOk = false;
    const [due, estimated] = nextDeadline(o.deadline);
    const f = { sport, age, skill, travel, proximity, affordability: affordScore(p.budget_usd, o.cost_usd),
      deadline: deadlineScore(due), type: typeScore(p.intent_types, o.type), relevance: relevance == null ? 0.5 : clamp(relevance) };
    let score = Math.round(100 * Object.keys(WEIGHTS).reduce((s, k) => s + f[k] * WEIGHTS[k], 0));
    const eligible = eligibleAge && within && residencyOk && scope !== "resource";
    if (!eligible) score = Math.min(score, 62);
    if (!residencyOk) score = Math.min(score, 40);
    return { ...o, compatibility: score, distance_km: dist == null ? null : round(dist, 1),
      distance_mi: dist == null ? null : round(dist * 0.621371, 1), eligible, eligible_age: eligibleAge, within_radius: within,
      residency_ok: residencyOk, scope, next_deadline: due ? iso(due) : null, deadline_estimated: estimated,
      color: D.typeColors[o.type] || "#888888", factors: Object.fromEntries(Object.entries(f).map(([k, v]) => [k, round(v, 3)])),
      reasons: reasons(f, p), affordability: affordabilityIndex(o.cost_usd) };
  }
  function rankCatalog(p, rows = D.catalog) {
    let rel = null;
    if (p.raw_query) {
      const raw = INDEX.queryScores(p.raw_query);
      const top = Math.max(0, ...raw.values());
      if (top > 0) rel = new Map([...raw].map(([k, v]) => [k, v / top]));
    }
    return rows.map((r) => rankOpportunity(p, r, rel ? rel.get(r.id) : null)).sort((a, b) =>
      b.compatibility - a.compatibility || (a.distance_km == null) - (b.distance_km == null) || (a.distance_km || 0) - (b.distance_km || 0));
  }

  // ---------------- analysis ----------------
  const median = (xs) => { if (!xs.length) return null; const s = [...xs].sort((a, b) => a - b), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const countBy = (xs, key) => xs.reduce((m, x) => ((m[x[key]] = (m[x[key]] || 0) + 1), m), {});
  const topN = (obj, n) => Object.fromEntries(Object.entries(obj).sort((a, b) => b[1] - a[1]).slice(0, n));
  function quantile(xs, q) { const s = [...xs].sort((a, b) => a - b), pos = (s.length - 1) * q, lo = Math.floor(pos); return s[lo] + (s[Math.min(lo + 1, s.length - 1)] - s[lo]) * (pos - lo); }
  function analyze(r) {
    if (!r.length) return { count: 0, mean_score: 0, median_cost: null, travel_share: 0, eligible_share: 0, by_type: {}, by_sport: {},
      by_country: {}, score_by_type: {}, score_histogram: {}, affordability_bands: {}, density: [], top_quartile_cutoff: 0 };
    const costs = r.map((x) => x.cost_usd).filter((c) => c != null);
    const bands = { free: 0, under_500: 0, "500_2000": 0, over_2000: 0 };
    costs.forEach((c) => (c <= 0 ? bands.free++ : c <= 499 ? bands.under_500++ : c <= 2000 ? bands["500_2000"]++ : bands.over_2000++));
    const hist = { "0-40": 0, "41-55": 0, "56-70": 0, "71-85": 0, "86-100": 0 };
    r.forEach((x) => { const s = x.compatibility; hist[s <= 40 ? "0-40" : s <= 55 ? "41-55" : s <= 70 ? "56-70" : s <= 85 ? "71-85" : "86-100"]++; });
    const sums = {};
    r.forEach((x) => { (sums[x.type] ||= [0, 0]); sums[x.type][0] += x.compatibility; sums[x.type][1]++; });
    const cells = new Map();
    r.forEach((x) => { const k = `${Math.floor(x.lat / 2)},${Math.floor(x.lng / 2)}`; const c = cells.get(k) || { n: 0, s: 0 }; c.n++; c.s += x.compatibility; cells.set(k, c); });
    const md = median(costs);
    return {
      count: r.length,
      mean_score: round(r.reduce((s, x) => s + x.compatibility, 0) / r.length, 1),
      top_quartile_cutoff: Math.trunc(quantile(r.map((x) => x.compatibility), 0.75)),
      median_cost: md == null ? null : Math.trunc(md),
      unknown_cost: r.length - costs.length,
      travel_share: round((100 * r.filter((x) => x.is_travel).length) / r.length, 1),
      eligible_share: round((100 * r.filter((x) => x.eligible).length) / r.length, 1),
      by_type: topN(countBy(r, "type"), 99), by_sport: topN(countBy(r, "sport"), 8), by_country: topN(countBy(r, "country"), 8),
      score_by_type: Object.fromEntries(Object.entries(sums).map(([k, [s, n]]) => [k, round(s / n, 1)]).sort((a, b) => b[1] - a[1])),
      score_histogram: hist, affordability_bands: bands,
      density: [...cells].map(([k, c]) => { const [cy, cx] = k.split(",").map(Number); return { lat: (cy + 0.5) * 2, lng: (cx + 0.5) * 2, count: c.n, mean_score: round(c.s / c.n, 1) }; })
        .sort((a, b) => b.count - a.count),
    };
  }

  // ---------------- plan ----------------
  const LEVELS = ["beginner", "recreational", "competitive", "elite", "college"];
  const LEVEL_LABELS = { beginner: "Beginner", recreational: "Recreational", competitive: "Competitive / club", elite: "Elite / academy", college: "College" };
  const COMP_TYPES = { rec_league: "recreation", school_team: "school", club_travel: "club", tournaments: "national", college_recruiting: "college", community: "nonprofit" };
  const TRAVEL_COMPS = ["club_travel", "tournaments", "college_recruiting"];
  const TRANSPORT_MI = { bike_walk: 5, transit: 15, carpool: 30, parent: 40, car: 40 };
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const TIMES = { morning: "Morning (7–11 am)", afternoon: "Afternoon (12–4 pm)", evening: "Evening (5–8 pm)" };

  function toRankingProfile(q) {
    const comps = q.competitions || [], barriers = new Set(q.barriers || []), home = q.home || {};
    const p = { sport: q.sport || null, age: q.age ?? null, skill: q.skill || null, budget_usd: q.budget_usd ?? null,
      intent_types: comps.filter((c) => c in COMP_TYPES).map((c) => COMP_TYPES[c]), adaptive: barriers.has("disability") || null };
    if (!p.intent_types.length) p.intent_types = null;
    if (q.max_distance_mi) p.max_distance_km = Number(q.max_distance_mi) * KM_PER_MI;
    if (comps.length) p.wants_travel = comps.some((c) => TRAVEL_COMPS.includes(c));
    if (barriers.has("cost") && p.budget_usd == null) p.budget_usd = 200;
    if (home.lat != null && home.lng != null) Object.assign(p, { lat: Number(home.lat), lng: Number(home.lng), home_label: home.label || "Home", home_country: home.country });
    if (q.goal_text) p.raw_query = q.goal_text;
    return Object.fromEntries(Object.entries(p).filter(([, v]) => v !== null && v !== undefined));
  }
  function weeklyOk(i, capKm) {
    if (!i.eligible || i.scope === "resource") return false;
    if (!["club", "recreation", "school", "nonprofit"].includes(i.type)) return false;
    if (i.scope === "national") return true;
    return i.distance_km == null || i.distance_km <= capKm;
  }
  function cardSummary(i) {
    const local = i.scope === "national" && i.residency_ok;
    const distance = local ? "Find your local chapter" : i.distance_mi == null ? "—" : i.distance_mi < 1 ? "under 1 mi" : `${i.distance_mi.toLocaleString()} mi`;
    return { id: i.id, name: i.name, type: i.type, compatibility: i.compatibility, distance, cost: i.cost_label, levels: i.skill_levels,
      next_deadline: i.next_deadline, deadline_estimated: i.deadline_estimated, why: i.reasons.strong };
  }
  function nextLevel(skill) { if (!skill || !LEVELS.includes(skill)) return "recreational"; const i = LEVELS.indexOf(skill); return LEVELS[i + 1] || null; }
  function pathway(skill, goal, ranked) {
    const current = SKILL_RANK[skill || "beginner"] ?? 0;
    const target = goal ? SKILL_RANK[goal] : null;
    return LEVELS.map((level) => {
      const r = SKILL_RANK[level];
      let status = r < current ? "past" : r === current ? "current" : "upcoming";
      if (target != null && r > target) status = "beyond";
      const ex = ranked.find((x) => x.eligible && x.skill_levels.includes(level) && x.scope !== "resource");
      return { level, label: LEVEL_LABELS[level], status, is_goal: level === goal, example: ex ? { id: ex.id, name: ex.name } : null };
    });
  }
  function buildPlan(q) {
    const profile = toRankingProfile(q);
    const ranked = rankCatalog(profile);
    let capMi = TRANSPORT_MI[q.transport || "car"] ?? 40;
    if (q.max_distance_mi) capMi = Math.min(capMi, Number(q.max_distance_mi));
    const reachable = ranked.filter((r) => weeklyOk(r, capMi * KM_PER_MI));
    const budget = profile.budget_usd;
    const fits = (r) => (!q.skill || r.skill_levels.includes(q.skill)) && (budget == null || r.cost_usd == null || r.cost_usd <= budget);
    const fitting = reachable.filter(fits);
    const weekly = (fitting.length ? fitting : reachable).slice(0, 3);
    const slots = (q.availability || []).map((s) => s.split("-")).filter(([d, t]) => DAYS.includes(d) && t in TIMES)
      .sort((a, b) => DAYS.indexOf(a[0]) - DAYS.indexOf(b[0]) || Object.keys(TIMES).indexOf(a[1]) - Object.keys(TIMES).indexOf(b[1])).slice(0, 4);
    const order = weekly.length >= 3 ? [0, 0, 1, 2] : weekly.length === 2 ? [0, 0, 1, 1] : [0, 0, 0, 0];
    const sessions = weekly.length ? slots.map(([day, time], i) => ({ day, time: TIMES[time], ...cardSummary(weekly[order[i]]) })) : [];
    const nxt = nextLevel(profile.skill);
    let stepUp = null;
    if (nxt && profile.skill) {
      const cand = ranked.find((r) => r.eligible && r.skill_levels.includes(nxt) && r.scope !== "resource" && !(weekly[0] && r.id === weekly[0].id));
      stepUp = { after: "After 4–6 weeks of consistent sessions", level: nxt, label: LEVEL_LABELS[nxt], program: cand ? cardSummary(cand) : null };
    }
    const events = profile.wants_travel ? ranked.filter((r) => r.eligible && r.is_travel && ["national", "college"].includes(r.type)).slice(0, 3).map(cardSummary) : [];
    const b = new Set(q.barriers || []), tips = [];
    if (b.has("cost")) tips.push("Cost: the free and low-cost programs are ranked higher. Ask clubs about financial aid. Many offer it but don't advertise it.");
    if (b.has("transport") || ["bike_walk", "transit"].includes(q.transport)) tips.push(`Getting there: weekly picks stay within ${Math.trunc(capMi)} mi because of how you travel.`);
    if (b.has("time")) tips.push("Time: the plan uses only the slots you marked as available.");
    if (b.has("disability")) tips.push("Adaptive sport: programs with adaptive or unified divisions are included.");
    if (b.has("new_to_sport") || b.has("confidence")) tips.push("New or nervous? Start with a recreational group. They focus on learning, not tryouts.");
    return { profile, sessions, no_slots: !slots.length, weekly_programs: weekly.map(cardSummary), step_up: stepUp, events,
      pathway: pathway(profile.skill, q.goal_level, ranked), top_matches: ranked.filter((r) => r.eligible).slice(0, 8).map(cardSummary), tips };
  }

  // ---------------- endpoints (same shapes as the FastAPI app) ----------------
  function match(body) {
    const form = { age: body.age, sport: body.sport, skill: body.skill, budget_usd: body.budget_usd, max_distance_km: body.max_distance_km,
      wants_travel: body.wants_travel, ...resolveHome(body.city, body.lat, body.lng, body.country) };
    Object.keys(form).forEach((k) => (form[k] === null || form[k] === undefined) && delete form[k]);
    const profile = parseQuery(body.query || "", {});
    if ("lat" in form) delete profile.place_query;
    Object.assign(profile, form);
    if (body.types && body.types.length) profile.intent_types = body.types;
    let ranked = rankCatalog(profile);
    const total = ranked.length;
    if (body.eligible_only) ranked = ranked.filter((r) => r.eligible);
    return { profile, count: ranked.length, catalog_size: total, needs_geocode: "lat" in profile ? null : profile.place_query || null,
      recommendations: ranked, analysis: analyze(ranked), source: "browser" };
  }
  function opportunity(id, quiz) {
    if (!D.catalog.some((r) => r.id === id)) throw Object.assign(new Error("unknown opportunity"), { status: 404 });
    const ranked = rankCatalog(toRankingProfile(quiz));
    const byId = new Map(ranked.map((r) => [r.id, r]));
    return { opportunity: byId.get(id), pathway: pathway(quiz.skill, quiz.goal_level, ranked),
      similar: INDEX.similar(id, 4).map(([i]) => ({ id: i, name: byId.get(i).name, compatibility: byId.get(i).compatibility, type: byId.get(i).type })) };
  }
  function geocodeOffline(q) {
    const h = resolveHome(q.slice(0, 100));
    return h.lat == null ? { found: false } : { found: true, lat: h.lat, lng: h.lng, label: h.home_label, country: h.home_country };
  }

  window.PlayPathEngine = { parseQuery, rankCatalog, analyze, buildPlan, match, opportunity, geocodeOffline, catalog: D.catalog };
})();
