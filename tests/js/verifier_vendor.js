/*
  verifier_vendor.js — évalue les scripts vendorisés (OOM-113) comme le ferait
  une balise <script> classique, dans un contexte isolé où `window` est
  l'objet global, et écrit sur stdout ce qu'ils exposent de l'API qu'utilise
  front/actifs/carte.js. Pas de WebGL sous Node : rien n'est instancié, sauf
  `pmtiles.Protocol`, qui n'en a pas besoin.

  Usage : node verifier_vendor.js <maplibre-gl.js> <pmtiles.js>
*/
"use strict";
const fs = require("fs");
const vm = require("vm");

const [maplibre, pmtiles] = process.argv.slice(2);
const ctx = { console, URL, URLSearchParams, Blob, TextDecoder, TextEncoder, setTimeout,
              clearTimeout, Promise, performance, fetch, AbortController };
ctx.window = ctx;
ctx.self = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(pmtiles, "utf8"), ctx, { filename: pmtiles });
vm.runInContext(fs.readFileSync(maplibre, "utf8"), ctx, { filename: maplibre });
const m = ctx.maplibregl;
const p = ctx.pmtiles;
process.stdout.write(JSON.stringify({
  maplibre_version: m && typeof m.getVersion === "function" ? m.getVersion() : null,
  maplibre: m ? ["Map", "Popup", "AttributionControl", "NavigationControl", "addProtocol"]
    .filter((n) => typeof m[n] === "function") : [],
  pmtiles: p ? ["Protocol", "PMTiles"].filter((n) => typeof p[n] === "function") : [],
  protocole_tile: p && typeof p.Protocol === "function" ? typeof new p.Protocol().tile : null,
}));
