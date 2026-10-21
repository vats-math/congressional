// Leaflet setup shared by the explore map and the opportunity detail map. `L` is the global from vendor/leaflet.js.
import { state } from "./state.js";

export function destroyMaps() {
  state.maps.forEach((m) => m.remove());
  state.maps = [];
}

export function makeMap(el, opts = {}) {
  const base = {
    // OpenStreetMap's own tiles: no API key. (CARTO's free tiles started showing "API key required".)
    Streets: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom: 19 }),
    Satellite: L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Tiles &copy; Esri", maxZoom: 19 }),
  };
  const map = L.map(el, { worldCopyJump: true, minZoom: 2, layers: [base.Streets], ...opts }).setView([25, 0], 2);
  map._baseLayers = base;
  state.maps.push(map);
  return map;
}
