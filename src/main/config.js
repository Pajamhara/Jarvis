// Configuration utilisateur stockée en JSON (thème, devise, taille de fenêtre…)
const fs = require("fs");
const path = require("path");

const DEFAULTS = {
  theme: "dark",
  currency: "EUR",
  windowWidth: 1280,
  windowHeight: 800,
  initialBalance: 0,
};

let file = null;
let cache = { ...DEFAULTS };

function sanitize(patch) {
  const out = {};
  if (patch.theme === "dark" || patch.theme === "light") out.theme = patch.theme;
  if (typeof patch.currency === "string" && /^[A-Z]{3}$/.test(patch.currency)) out.currency = patch.currency;
  for (const k of ["windowWidth", "windowHeight"]) {
    if (Number.isFinite(patch[k]) && patch[k] >= 400) out[k] = Math.round(patch[k]);
  }
  if (Number.isFinite(patch.initialBalance)) out.initialBalance = patch.initialBalance;
  return out;
}

function init(userDataDir) {
  file = path.join(userDataDir, "config.json");
  cache = { ...DEFAULTS };
  try {
    Object.assign(cache, sanitize(JSON.parse(fs.readFileSync(file, "utf8"))));
  } catch {
    /* premier lancement ou fichier illisible : valeurs par défaut */
  }
  return get();
}

function get() {
  return { ...cache };
}

function save(patch) {
  cache = { ...cache, ...sanitize(patch) };
  try {
    fs.writeFileSync(file, JSON.stringify(cache, null, 2));
  } catch (e) {
    console.error("Impossible d'écrire config.json :", e);
  }
  return get();
}

module.exports = { init, get, save, DEFAULTS };
