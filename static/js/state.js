// App-wide state: who is signed in, their quiz answers, open maps, and the quiz in progress.
import { api } from "./api.js";
import { GUEST_KEY } from "./constants.js";

export const state = {
  user: null,
  profile: null,
  maps: [],
  quiz: { draft: null, step: 0 },
  // Set by router.js. Views call state.rerender() instead of importing the router (avoids a circular import).
  rerender: () => {},
};

export function loadGuest() {
  try { return JSON.parse(localStorage.getItem(GUEST_KEY) || "null"); } catch { return null; }
}
export function saveGuest(p) {
  try { localStorage.setItem(GUEST_KEY, JSON.stringify(p)); } catch { /* private mode: keep in memory */ }
}
export function clearGuest() {
  try { localStorage.removeItem(GUEST_KEY); } catch { /* ignore */ }
}

export async function saveProfile(profile) {
  state.profile = profile;
  if (state.user) await api("/api/profile", { method: "PUT", body: profile });
  else saveGuest(profile);
}

export const blankProfile = () => ({
  sport: null, age: null, skill: null, years_since_played: null, competitions: [], availability: [], budget_usd: null,
  max_distance_mi: 25, transport: null, home: {}, barriers: [], goal_level: null, goal_text: "",
});
