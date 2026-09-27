/*
  harnais_activites.js — exécute front/actifs/activites.js sous Node, dans un
  DOM factice minimal, contre un vrai serveur HTTP (lancé par
  tests/test_export_html.py, OOM-107). Aucune dépendance : Node 18+ (fetch et
  Event globaux).

  Usage : node harnais_activites.js <activites.js> <scenario.json>
  scenario.json : {"tables": [{"fragment": "<url absolue>",
                               "details": [{"finess": "…", "nombre": n}]}],
                   "ouvertures": [[table, details], ...]}
  Chaque ouverture ouvre le panneau puis attend la fin du chargement. Écrit
  sur stdout un JSON : requêtes fetch avant toute ouverture, après chaque
  ouverture, et l'état final de chaque panneau.
*/
"use strict";
const fs = require("fs");

class Noeud {
  constructor(nom) {
    this.nodeName = nom; this.enfants = []; this.parent = null;
    this.dataset = {}; this.className = ""; this._texte = ""; this.ecouteurs = {};
  }
  appendChild(n) { n.parent = this; this.enfants.push(n); return n; }
  removeChild(n) { this.enfants.splice(this.enfants.indexOf(n), 1); n.parent = null; return n; }
  get nextSibling() {
    if (!this.parent) return null;
    const f = this.parent.enfants; return f[f.indexOf(this) + 1] || null;
  }
  set textContent(t) { this.enfants = []; this._texte = String(t); }
  get textContent() { return this._texte + this.enfants.map((e) => e.textContent).join(""); }
  tous(pred, acc = []) { this.enfants.forEach((e) => { if (pred(e)) acc.push(e); e.tous(pred, acc); }); return acc; }
  querySelectorAll(sel) {
    const m = /^(\w+)(?:\[data-(\w+)\])?$/.exec(sel);
    if (!m) throw new Error("sélecteur non géré par le harnais : " + sel);
    return this.tous((e) => e.nodeName === m[1] && (!m[2] || m[2] in e.dataset));
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  addEventListener(type, f) { (this.ecouteurs[type] = this.ecouteurs[type] || []).push(f); }
  dispatchEvent(ev) { (this.ecouteurs[ev.type] || []).forEach((f) => f(ev)); return true; }
}
class Texte extends Noeud { constructor(t) { super("#text"); this._texte = t; } }

const [scriptActivites, cheminScenario] = process.argv.slice(2);
const scenario = JSON.parse(fs.readFileSync(cheminScenario, "utf8"));
const racine = new Noeud("body");
const tables = scenario.tables.map((t) => {
  const table = racine.appendChild(new Noeud("table"));
  table.dataset.fragment = t.fragment;
  const panneaux = t.details.map((d) => {
    const details = table.appendChild(new Noeud("details"));
    details.dataset.finess = d.finess;
    details.appendChild(new Noeud("summary")).textContent = d.nombre + " activité(s)";
    details.appendChild(new Noeud("p")).textContent = "Détail chargé à l'ouverture (JavaScript requis).";
    details.evenements = 0;
    details.addEventListener("activites-chargees", () => { details.evenements += 1; });
    return details;
  });
  return { table, panneaux };
});

global.document = {
  createElement: (nom) => new Noeud(nom),
  createTextNode: (t) => new Texte(t),
  querySelectorAll: (sel) => racine.querySelectorAll(sel),
};
const requetes = [];
const fetchReel = global.fetch;
global.fetch = (url) => { requetes.push(url); return fetchReel(url); };

async function attendre(details) {
  for (let i = 0; i < 500 && details.dataset.enCours; i += 1) {
    await new Promise((r) => setTimeout(r, 10));
  }
}

function etat(details) {
  const lignes = details.querySelectorAll("tr").filter((tr) => tr.dataset.nature !== undefined);
  const alerte = details.querySelectorAll("p").find((p) => p.className === "alerte");
  const liens = details.tous((e) => e.nodeName === "a").map((a) => a.href);
  return {
    finess: details.dataset.finess,
    chargees: !!details.dataset.chargees,
    lignes: lignes.length,
    natures: lignes.map((tr) => tr.dataset.nature),
    texte: details.textContent,
    alerte: alerte ? alerte.textContent : null,
    liens,
    evenements: details.evenements,
    vide: details.enfants.length <= 1,
  };
}

(async () => {
  require(require("path").resolve(scriptActivites));
  const sortie = { requetes_initiales: requetes.slice(), apres_ouverture: [] };
  for (const [t, d] of scenario.ouvertures) {
    const details = tables[t].panneaux[d];
    details.open = !details.open ? true : details.open;
    details.dispatchEvent(new Event("toggle"));
    await attendre(details);
    sortie.apres_ouverture.push({ requetes: requetes.length, panneau: etat(details) });
    details.open = false;
    details.dispatchEvent(new Event("toggle"));
  }
  sortie.requetes = requetes;
  process.stdout.write(JSON.stringify(sortie));
})().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(2); });
