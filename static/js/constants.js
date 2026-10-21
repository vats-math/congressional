// Fixed lists and colors shared by every screen.
export const TYPE_COLORS = window.TYPE_COLORS || {};
export const NOMINATIM = "https://nominatim.openstreetmap.org";
export const GUEST_KEY = "playpath_guest_profile";

// Brand palette: plum, berry, seafoam. Everything else is a neutral or a tint of these.
// Keep in sync with the :root tokens in static/styles.css.
export const COLORS = {
  plum: "#462255",
  berry: "#AA4465",
  seafoam: "#93E1D8",
  seafoamDeep: "#3F756D",
  ink: "#2A1633",
  muted: "#6E6177",
  neutral: "#9A8FA1",
  surface: "#FFFFFF",
};

export const SPORTS = ["soccer", "basketball", "volleyball", "softball", "tennis", "swimming", "track", "lacrosse",
  "field hockey", "hockey", "golf", "gymnastics", "wrestling", "rugby", "netball", "multi"];
export const LEVELS = [
  ["beginner", "Beginner", "New to the sport or just learning the basics"],
  ["recreational", "Recreational", "I play for fun in a local league or at school"],
  ["competitive", "Competitive", "I play on a club or select team and have tried out"],
  ["elite", "Elite", "Academy, ODP, or high-performance level"],
  ["college", "College-level", "Ready to play in college"],
];
export const COMPETITIONS = [
  ["rec_league", "Rec league", "Local, everyone plays"],
  ["school_team", "School team", "Middle or high school"],
  ["club_travel", "Club / travel team", "Tryouts, regional travel"],
  ["tournaments", "Tournaments & showcases", "Weekend events, ID camps"],
  ["college_recruiting", "College recruiting", "Camps, scholarships"],
  ["community", "Community programs", "Nonprofits, mentoring"],
];
export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const TIMES = [["morning", "Morning"], ["afternoon", "Afternoon"], ["evening", "Evening"]];
export const TRANSPORT = [
  ["car", "I drive"], ["parent", "Family drives me"], ["carpool", "Carpool"],
  ["transit", "Bus / train"], ["bike_walk", "Bike or walk"],
];
export const BARRIERS = [
  ["cost", "Cost is a concern"], ["transport", "Getting there is hard"], ["time", "Limited free time"],
  ["disability", "I have a disability / want adaptive sport"], ["new_to_sport", "I'm new to the sport"],
  ["confidence", "I'm nervous about joining"], ["social", "I don't know anyone there"],
  ["environment", "A past team didn't feel welcoming"], ["family", "Family responsibilities"],
  ["injury", "Coming back from an injury"],
];

// What the advisor (app/advisor.py) can detect in her own words, and how we ask her to confirm it.
// `value` is the quiz barrier it turns into once she says yes.
export const DETECTED = {
  experience: { value: "new_to_sport", text: "It sounds like you're new to the sport or coming back after a break." },
  confidence: { value: "confidence", text: "It sounds like trying out feels intimidating." },
  social: { value: "social", text: "It sounds like you're worried about not knowing anyone." },
  cost: { value: "cost", text: "It sounds like cost is a worry." },
  transport: { value: "transport", text: "It sounds like getting there is hard." },
  time: { value: "time", text: "It sounds like your schedule is tight." },
  environment: { value: "environment", text: "It sounds like a past team didn't feel welcoming." },
  family: { value: "family", text: "It sounds like family responsibilities make it harder." },
  injury: { value: "injury", text: "It sounds like you're dealing with an injury." },
};
