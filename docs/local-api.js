/* Stand-in for the FastAPI server when PlayPath runs as static pages (GitHub Pages / opened from disk).
 * Answers the same /api/* paths app.js calls. Accounts live in this browser's localStorage only:
 * they are not shared across devices, and clearing site data removes them. */
(function () {
  const E = window.PlayPathEngine;
  const USERS = "playpath_users";
  const SESSION = "playpath_session";
  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  const read = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
  const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { throw new Error("This browser is blocking storage, so accounts can't be saved. Continue as a guest instead."); } };
  const users = () => read(USERS, {});
  const publicUser = (u) => (u ? { id: u.id, email: u.email, name: u.name } : null);
  const current = () => { const email = read(SESSION, null); return email ? users()[email] || null : null; };
  const fail = (msg, status = 400) => { throw Object.assign(new Error(msg), { status }); };
  const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");

  async function hash(password, saltHex) {
    if (!window.crypto?.subtle) fail("This browser can't create accounts here. Continue as a guest instead.");
    const salt = new Uint8Array(saltHex.match(/../g).map((h) => parseInt(h, 16)));
    const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveBits"]);
    return hex(await crypto.subtle.deriveBits({ name: "PBKDF2", salt, iterations: 200000, hash: "SHA-256" }, key, 256));
  }

  function saveUser(u) { const all = users(); all[u.email] = u; write(USERS, all); }

  const routes = [
    ["GET", /^\/api\/me$/, () => { const u = current(); return { user: publicUser(u), profile: u?.profile || null }; }],
    ["PUT", /^\/api\/me$/, (b) => { const u = current() || fail("Sign in required", 401); u.name = (b.name || "").trim().slice(0, 80); saveUser(u); return { user: publicUser(u) }; }],
    ["DELETE", /^\/api\/me$/, () => { const u = current() || fail("Sign in required", 401); const all = users(); delete all[u.email]; write(USERS, all); localStorage.removeItem(SESSION); return { ok: true }; }],
    ["POST", /^\/api\/auth\/signup$/, async (b) => {
      const email = (b.email || "").trim().toLowerCase();
      if (!EMAIL_RE.test(email)) fail("Enter a valid email address.");
      if ((b.password || "").length < 8) fail("Password must be at least 8 characters.");
      if (users()[email]) fail("An account with that email already exists on this device.");
      const salt = hex(crypto.getRandomValues(new Uint8Array(16)));
      const u = { id: Date.now(), email, name: (b.name || "").trim().slice(0, 80), salt, hash: await hash(b.password, salt), profile: null };
      saveUser(u); write(SESSION, email);
      return { user: publicUser(u), profile: null };
    }],
    ["POST", /^\/api\/auth\/login$/, async (b) => {
      const u = users()[(b.email || "").trim().toLowerCase()];
      if (!u || (await hash(b.password || "", u.salt)) !== u.hash) fail("Email or password is incorrect. Accounts are saved per device and browser.", 401);
      write(SESSION, u.email);
      return { user: publicUser(u), profile: u.profile };
    }],
    ["POST", /^\/api\/auth\/logout$/, () => { localStorage.removeItem(SESSION); return { ok: true }; }],
    ["PUT", /^\/api\/profile$/, (b) => { const u = current() || fail("Sign in required", 401); u.profile = b; saveUser(u); return { profile: b }; }],
    ["POST", /^\/api\/plan$/, (b) => E.buildPlan(b)],
    ["POST", /^\/api\/match$/, (b) => E.match(b)],
    ["POST", /^\/api\/opportunity\/(.+)$/, (b, m) => E.opportunity(decodeURIComponent(m[1]), b)],
    ["GET", /^\/api\/opportunities$/, () => ({ count: E.catalog.length, opportunities: E.catalog })],
    ["GET", /^\/api\/geocode\?q=(.*)$/, (b, m) => E.geocodeOffline(decodeURIComponent(m[1]))],
  ];

  window.LOCAL_API = async function (path, { method = "GET", body } = {}) {
    for (const [verb, re, handler] of routes) {
      const m = path.match(re);
      if (m && verb === method) return handler(body || {}, m);
    }
    fail(`Not found: ${method} ${path}`, 404);
  };
})();
