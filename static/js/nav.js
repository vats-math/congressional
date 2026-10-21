// Top navigation bar and the global clicks it handles (mobile menu, sign out).
import { api } from "./api.js";
import { $ } from "./dom.js";
import { loadGuest, state } from "./state.js";
import { LOGO } from "./ui.js";

export function renderNav(current) {
  const hasProfile = !!state.profile?.sport;
  const signedIn = !!state.user;
  const link = (view, href, text) => `<a href="${href}" class="${current === view ? "on" : ""}">${text}</a>`;
  let links;
  if (signedIn || hasProfile) {
    links = link("dashboard", "#/dashboard", "Dashboard") + link("simulate", "#/simulate", "What if?") + link("explore", "#/explore", "Explore map") + link("settings", "#/settings", "Settings") +
      (signedIn ? `<button class="ghost small" data-action="signout">Sign out</button>`
                : `<a class="btn small" href="#/signup">Save my plan</a>`);
  } else {
    links = link("landing", "#/", "Home") + link("explore", "#/explore", "Explore map") + link("login", "#/login", "Sign in") +
      `<a class="btn small" href="#/signup">Get started</a>`;
  }
  $("#nav").innerHTML = `<div class="nav-inner shell">
      <a class="brand" href="${signedIn || hasProfile ? "#/dashboard" : "#/"}">${LOGO}<span>PlayPath</span></a>
      <button class="nav-toggle" aria-label="Menu" data-action="menu">Menu</button>
      <nav class="nav-links">${links}</nav>
    </div>
    ${!signedIn && hasProfile ? `<div class="guest-bar">You're browsing as a guest. Your answers are saved only in this browser. <a href="#/signup">Create an account</a> to keep them.</div>` : ""}`;
}

export function wireGlobalActions() {
  document.addEventListener("click", async (e) => {
    const action = e.target.closest("[data-action]")?.dataset.action;
    if (action === "menu") $(".nav-links")?.classList.toggle("open");
    if (action === "signout") {
      await api("/api/auth/logout", { method: "POST" }).catch(() => {});
      state.user = null;
      state.profile = loadGuest();
      location.hash = "#/";
      state.rerender();
    }
  });
}
