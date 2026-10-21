// Entry point: load who is signed in, then start the router.
import { api } from "./api.js";
import { wireGlobalActions } from "./nav.js";
import { render } from "./router.js";
import { loadGuest, state } from "./state.js";

state.rerender = render;
wireGlobalActions();
window.addEventListener("hashchange", render);

const me = await api("/api/me").catch(() => ({ user: null, profile: null }));
state.user = me.user;
state.profile = me.user ? me.profile : loadGuest();
render();
