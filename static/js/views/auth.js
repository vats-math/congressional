// Sign in and create account (one view, two modes).
import { api } from "../api.js";
import { $ } from "../dom.js";
import { blankProfile, clearGuest, loadGuest, saveProfile, state } from "../state.js";
import { LOGO } from "../ui.js";

function view(mode) {
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
      <p class="auth-alt">${signup ? `Already have an account? <a href="#/login">Sign in</a>` : `New here? <a href="#/signup">Create an account</a>`}</p>
      <div class="divider"><span>or</span></div>
      <a class="btn ghost wide" href="#/quiz" id="guest-btn">Continue as guest</a>
    </div>
  </section>`;
}

function wire(signup) {
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
}

export const login = { html: () => view("login"), after: () => wire(false) };
export const signup = { html: () => view("signup"), after: () => wire(true) };
