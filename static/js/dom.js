// Tiny DOM and formatting helpers.
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
export const pct = (v) => Math.round(v * 100);
export const checkedValues = (root, name) => $$(`input[name="${name}"]:checked`, root).map((i) => i.value);
export const radioValue = (root, name) => $(`input[name="${name}"]:checked`, root)?.value ?? null;
