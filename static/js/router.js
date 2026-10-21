// Hash router: maps #/address to a view module and renders it into <main id="view">.
import { $, esc } from "./dom.js";
import { destroyMaps } from "./map.js";
import { renderNav } from "./nav.js";
import { state } from "./state.js";
import * as landing from "./views/landing.js";
import { login, signup } from "./views/auth.js";
import * as quiz from "./views/quiz.js";
import * as dashboard from "./views/dashboard.js";
import * as simulate from "./views/simulate.js";
import * as opportunity from "./views/opportunity.js";
import * as explore from "./views/explore.js";
import * as settings from "./views/settings.js";

const VIEWS = { landing, login, signup, quiz, dashboard, simulate, opportunity, explore, settings };

const ROUTES = [
  [/^#\/?$/, "landing"], [/^#\/login$/, "login"], [/^#\/signup$/, "signup"], [/^#\/quiz$/, "quiz"],
  [/^#\/dashboard$/, "dashboard"], [/^#\/simulate$/, "simulate"], [/^#\/explore$/, "explore"], [/^#\/settings$/, "settings"],
  [/^#\/opportunity\/(.+)$/, "opportunity"],
];

export async function render() {
  destroyMaps();
  const hash = location.hash || "#/";
  let name = "landing", arg;
  for (const [re, view] of ROUTES) {
    const m = hash.match(re);
    if (m) { name = view; arg = m[1] && decodeURIComponent(m[1]); break; }
  }
  if (name === "landing" && (state.user || state.profile?.sport)) name = "dashboard";
  if ((name === "login" || name === "signup") && state.user) name = "dashboard";
  if (name !== "quiz") state.quiz.draft = null;
  renderNav(name);
  const view = $("#view");
  view.innerHTML = VIEWS[name].html(arg);
  view.dataset.view = name;
  window.scrollTo(0, 0);
  try { await VIEWS[name].after?.(arg); } catch (err) { view.insertAdjacentHTML("beforeend", `<p class="form-error">${esc(err.message)}</p>`); }
}
