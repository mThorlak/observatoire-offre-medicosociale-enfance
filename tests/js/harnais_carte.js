/*
  harnais_carte.js — exécute front/actifs/carte.js sous Node, dans un DOM
  factice minimal, avec des doublures de MapLibre, de pmtiles et de fetch
  (lancé par tests/test_export_html.py, OOM-113). Aucun navigateur, aucune
  dépendance : Node 18+.

  Usage : node harnais_carte.js <carte.js> <scenario.json>
  scenario.json :
    {"dataset": {…data-* de #carte, en camelCase, lus dans la page rendue},
     "base": "<URL de la page>",
     "scripts_en_echec": ["<src>", …],     script dont le chargement échoue
     "fond": {"statut": 200} | {"reseau": true},
     "webgl": true | false,                false : new Map() lève
     "evenements": [{"sourceId": "…", "message": "…"}],  erreurs après « load »
     "clic_point": {"properties": {…}, "coordinates": [lon, lat]} | null,
     "clics_bouton": n}                    clics successifs sur le bouton
  Écrit sur stdout un JSON : état avant tout clic (requêtes, éléments
  injectés, visibilité), puis après chaque clic sur le bouton, et ce que la
  doublure de MapLibre a reçu (options, contrôles, protocole, source,
  calque, fenêtre du point cliqué).
*/
"use strict";
const fs = require("fs");
const path = require("path");

class Noeud {
  constructor(nom) {
    this.nodeName = nom; this.enfants = []; this.parent = null; this.dataset = {};
    this.className = ""; this._texte = ""; this.ecouteurs = {}; this.hidden = false;
    this.style = {};
  }
  appendChild(n) { n.parent = this; this.enfants.push(n); if (this.surAjout) this.surAjout(n); return n; }
  removeChild(n) { this.enfants.splice(this.enfants.indexOf(n), 1); n.parent = null; return n; }
  get firstChild() { return this.enfants[0] || null; }
  set textContent(t) { this.enfants = []; this._texte = String(t); }
  get textContent() { return this._texte + this.enfants.map((e) => e.textContent).join(""); }
  tous(pred, acc = []) { this.enfants.forEach((e) => { if (pred(e)) acc.push(e); e.tous(pred, acc); }); return acc; }
  addEventListener(type, f) { (this.ecouteurs[type] = this.ecouteurs[type] || []).push(f); }
  declencher(type) { (this.ecouteurs[type] || []).forEach((f) => f({ type })); }
}
class Texte extends Noeud { constructor(t) { super("#text"); this._texte = t; } }

const [scriptCarte, cheminScenario] = process.argv.slice(2);
const sc = JSON.parse(fs.readFileSync(cheminScenario, "utf8"));

// La page : les éléments que carte.js cherche, dans l'état du HTML rendu.
const elements = {};
for (const [id, nom] of [["carte", "div"], ["carte-commande", "p"], ["afficher-carte", "button"],
                         ["carte-etat", "div"]]) {
  elements[id] = new Noeud(nom);
  elements[id].hidden = id !== "afficher-carte";
}
Object.assign(elements.carte.dataset, sc.dataset);
const tete = new Noeud("head");
const injectes = [];
const requetes = [];
const recu = { protocoles: [], controles: [], sources: [], calques: [], cartes: [], fenetres: [] };
let carteCourante = null;

// Doublures de MapLibre et de pmtiles, posées quand leur script « se charge ».
class Carte {
  constructor(options) {
    if (sc.webgl === false) throw new Error("WebGL indisponible");
    this.options = options; this.ecouteurs = {}; this.canvas = { style: {} };
    recu.cartes.push({ bounds: options.bounds, fitBoundsOptions: options.fitBoundsOptions,
                       style: options.style && (options.style.layers || []).some((c) => c.id === "fond-neutre")
                         ? "neutre" : options.style,
                       conteneur: options.container === elements.carte,
                       attributionControl: options.attributionControl });
    carteCourante = this;
  }
  addControl(c) { recu.controles.push(c); return this; }
  on(type, calque, f) {
    if (typeof calque === "function") { f = calque; calque = null; }
    (this.ecouteurs[type] = this.ecouteurs[type] || []).push({ calque, f });
    return this;
  }
  emettre(type, calque, ev) {
    (this.ecouteurs[type] || []).filter((e) => e.calque === calque).forEach((e) => e.f(ev));
  }
  addSource(id, def) { recu.sources.push({ id, ...def }); }
  addLayer(def) { recu.calques.push(def); }
  getCanvas() { return this.canvas; }
}
class Fenetre {
  setLngLat(p) { this.position = p; return this; }
  setDOMContent(n) { this.contenu = n; return this; }
  addTo() {
    recu.fenetres.push({
      position: this.position, texte: this.contenu.textContent,
      liens: this.contenu.tous((e) => e.nodeName === "a").map((a) => a.href),
    });
    return this;
  }
}
const maplibre = {
  Map: Carte, Popup: Fenetre,
  addProtocol: (nom, f) => recu.protocoles.push({ nom, fonction: typeof f }),
  AttributionControl: class { constructor(o) { this.type = "attribution"; this.options = o; } },
  NavigationControl: class { constructor(o) { this.type = "navigation"; this.options = o; } },
};
const pmtiles = { Protocol: class { constructor() { this.tile = () => {}; } } };

tete.surAjout = (n) => {
  if (n.nodeName === "script") {
    injectes.push({ type: "script", src: n.src });
    setTimeout(() => {
      if ((sc.scripts_en_echec || []).includes(n.src)) return n.onerror && n.onerror({});
      if (n.src === sc.dataset.maplibre) global.maplibregl = maplibre;
      if (n.src === sc.dataset.pmtiles) global.pmtiles = pmtiles;
      n.onload && n.onload({});
    }, 0);
  } else {
    injectes.push({ type: n.nodeName, href: n.href, rel: n.rel });
  }
};

global.window = global;
global.document = {
  head: tete,
  baseURI: sc.base,
  getElementById: (id) => elements[id] || null,
  createElement: (nom) => new Noeud(nom),
  createTextNode: (t) => new Texte(t),
};
global.fetch = (url) => {
  requetes.push(url);
  if (sc.fond && sc.fond.reseau) return Promise.reject(new Error("Failed to fetch"));
  const statut = (sc.fond && sc.fond.statut) || 200;
  return Promise.resolve({ ok: statut < 400, status: statut,
                           json: () => Promise.resolve({ version: 8, sources: {}, layers: [] }) });
};

const attendre = (ms = 30) => new Promise((r) => setTimeout(r, ms));

function etat() {
  return {
    requetes: requetes.slice(),
    injectes: injectes.slice(),
    maplibre_charge: typeof global.maplibregl !== "undefined",
    carte_cachee: elements.carte.hidden,
    commande_cachee: elements["carte-commande"].hidden,
    bouton_desactive: !!elements["afficher-carte"].disabled,
    etat_cache: elements["carte-etat"].hidden,
    etat_texte: elements["carte-etat"].textContent,
    messages: elements["carte-etat"].enfants.length,
    cartes: recu.cartes.length,
  };
}

(async () => {
  require(path.resolve(scriptCarte));
  const sortie = { avant_clic: etat(), apres_clics: [] };
  await attendre();
  sortie.avant_clic_attente = etat();
  for (let i = 0; i < (sc.clics_bouton || 1); i += 1) {
    carteCourante = null;
    elements["afficher-carte"].declencher("click");
    await attendre();
    if (carteCourante) {
      carteCourante.emettre("load", null, {});
      for (const ev of sc.evenements || []) {
        carteCourante.emettre("error", null, { sourceId: ev.sourceId, error: new Error(ev.message) });
      }
      if (sc.clic_point) {
        carteCourante.emettre("click", "etablissements", {
          features: [{ properties: sc.clic_point.properties,
                       geometry: { type: "Point", coordinates: sc.clic_point.coordinates } }] });
      }
      await attendre();
    }
    sortie.apres_clics.push(etat());
  }
  sortie.recu = {
    protocoles: recu.protocoles, sources: recu.sources, calques: recu.calques,
    cartes: recu.cartes, fenetres: recu.fenetres,
    controles: recu.controles.map((c) => ({ type: c.type, options: c.options })),
  };
  process.stdout.write(JSON.stringify(sortie));
})().catch((e) => { process.stderr.write(String((e && e.stack) || e)); process.exit(2); });
