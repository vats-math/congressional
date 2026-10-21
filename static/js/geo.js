// Turning place names into coordinates and back (offline gazetteer first, then OpenStreetMap).
import { api } from "./api.js";
import { NOMINATIM } from "./constants.js";

export async function geocode(place) {
  const local = await api(`/api/geocode?q=${encodeURIComponent(place)}`).catch(() => ({ found: false }));
  if (local.found) return local;
  const res = await fetch(`${NOMINATIM}/search?format=jsonv2&limit=1&addressdetails=1&accept-language=en&q=${encodeURIComponent(place)}`);
  if (!res.ok) throw new Error("Location lookup is unavailable right now.");
  const [hit] = await res.json();
  if (!hit) return null;
  return { lat: Number(hit.lat), lng: Number(hit.lon), country: hit.address?.country || null,
    label: hit.display_name.split(",").slice(0, 2).join(",").trim() };
}

export async function reverseGeocode(lat, lng) {
  try {
    const r = await fetch(`${NOMINATIM}/reverse?format=jsonv2&accept-language=en&zoom=10&lat=${lat}&lon=${lng}`);
    const d = await r.json();
    return { country: d.address?.country || null, label: d.address?.city || d.address?.town || d.address?.county || "My location" };
  } catch { return { country: null, label: "My location" }; }
}

export function currentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("Location isn't supported in this browser."));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve(p.coords),
      (e) => reject(new Error(`Location blocked: ${e.message}`)),
      { timeout: 10000 }
    );
  });
}
