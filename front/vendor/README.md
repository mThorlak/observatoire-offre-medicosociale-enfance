# Dépendances JavaScript vendorisées (OOM-113)

Seules dépendances JavaScript d'exécution du site, copiées telles quelles dans
`site/vendor/` par `src/export_html.py` et chargées par `front/actifs/carte.js`
**au clic** sur « Afficher la carte », jamais par le HTML initial (D9). Aucune
n'est chargée depuis un CDN : la version est figée ici, octet pour octet
(`.gitattributes` : `-text`).

| Fichier | Paquet npm | Version | Licence | SHA-256 |
|---|---|---|---|---|
| `maplibre-gl/maplibre-gl.js` | `maplibre-gl` (`dist/`) | 5.24.0 | BSD-3-Clause (`maplibre-gl/LICENSE.txt`) | `45a9b07a9189ce56054c620a947ccf41e291e58c95e9b61533b740aaa65ee5cb` |
| `maplibre-gl/maplibre-gl.css` | `maplibre-gl` (`dist/`) | 5.24.0 | idem | `ab1e70d59ec40465bae7e7030da2f3ccf28133fd502e62bd598eefbadfd7a732` |
| `pmtiles/pmtiles.js` | `pmtiles` (`dist/`, build IIFE, global `pmtiles`) | 4.5.0 | BSD-3-Clause (`pmtiles/LICENSE`) | `caf981bc46f6327ee7e65d5dc964d89d38a69f60edca2bd4c5c890c21b554c6c` |

MapLibre 5 plutôt que 6 : la 6 n'est plus publiée qu'en modules ES répartis
en plusieurs fichiers ; la 5.24.0 est la dernière à fournir un build UMD en un
seul fichier, que `carte.js` injecte par une simple balise `<script>`.
Le paquet npm `pmtiles` ne contient pas sa licence : `pmtiles/LICENSE` est
celle du dépôt `protomaps/PMTiles`.

Les commentaires `sourceMappingURL` des deux scripts sont conservés (fichiers
intacts) ; les `.map` ne sont pas vendorisés.

Mise à jour :

```bash
npm pack maplibre-gl@<version> pmtiles@<version>   # puis extraire dist/ et la licence
sha256sum front/vendor/*/*                          # reporter les empreintes ici et dans CLAUDE.md
```
