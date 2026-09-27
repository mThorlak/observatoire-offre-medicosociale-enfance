# Poids du site — mesure D9 (OOM-109)

Site mesuré : `site/` · 104 pages HTML, 102 fragments, 3 actifs.  
Budget D9 : 500.0 Ko bruts au chargement initial (HTML + actifs référencés, hors fragments chargés à la demande).

## Chargement initial, par type de page

| Type | Pages | Médiane (Ko) | Max (Ko) | Max gzip (Ko) | Page la plus lourde | Hors budget |
|---|---:|---:|---:|---:|---|---:|
| `departement/*.html` | 102 | 622.1 | 2975.7 | 223.3 | `departement/59.html` | 60 |
| `index.html` | 1 | 36.4 | 36.4 | 8.6 | `index.html` | 0 |
| `indicateur.html` | 1 | 2133.7 | 2133.7 | 83.1 | `indicateur.html` | 1 |

**Page la plus lourde : `departement/59.html`, 2975.7 Ko au chargement initial** (HTML 2957.5 Ko + actifs `actifs/activites.js`, `actifs/filtres.js`, `actifs/ooms.css` ; 223.3 Ko en gzip), soit 6.0 × le budget.

## Fragments chargés à la demande (hors budget initial)

| Type | Fichiers | Médiane (Ko) | Max (Ko) | Max gzip (Ko) | Plus lourd | Total (Ko) |
|---|---:|---:|---:|---:|---|---:|
| `donnees/activites/*.json` | 102 | 610.9 | 3144.5 | 147.3 | `donnees/activites/59.json` | 74964.8 |

## Actifs

| Actif | Brut (Ko) | gzip (Ko) |
|---|---:|---:|
| `actifs/activites.js` | 6.1 | 2.2 |
| `actifs/filtres.js` | 6.6 | 2.3 |
| `actifs/ooms.css` | 5.6 | 1.8 |

## Verdict D9

**Budget dépassé : 61 page(s) sur 104 au-delà de 500.0 Ko.**

| Page | Initial (Ko) | gzip (Ko) | × budget |
|---|---:|---:|---:|
| `departement/59.html` | 2975.7 | 223.3 | 6.0 |
| `departement/75.html` | 2602.4 | 190.3 | 5.2 |
| `departement/69.html` | 2249.0 | 171.0 | 4.5 |
| `departement/13.html` | 2156.7 | 157.8 | 4.3 |
| `indicateur.html` | 2133.7 | 83.1 | 4.3 |
| `departement/44.html` | 1833.6 | 134.1 | 3.7 |
| `departement/95.html` | 1639.4 | 113.0 | 3.3 |
| `departement/76.html` | 1587.1 | 128.2 | 3.2 |
| `departement/35.html` | 1560.4 | 117.4 | 3.1 |
| `departement/62.html` | 1557.1 | 119.7 | 3.1 |
| `departement/92.html` | 1555.2 | 118.1 | 3.1 |
| `departement/33.html` | 1520.3 | 116.4 | 3.0 |
| `departement/38.html` | 1423.7 | 109.6 | 2.8 |
| `departement/31.html` | 1414.2 | 111.5 | 2.8 |
| `departement/93.html` | 1391.1 | 109.1 | 2.8 |
| `departement/78.html` | 1372.1 | 105.2 | 2.7 |
| `departement/94.html` | 1254.8 | 96.3 | 2.5 |
| `departement/29.html` | 1245.9 | 93.3 | 2.5 |
| `departement/06.html` | 1229.7 | 94.5 | 2.5 |
| `departement/34.html` | 1227.7 | 95.8 | 2.5 |
| `departement/91.html` | 1142.9 | 90.8 | 2.3 |
| `departement/83.html` | 1127.0 | 84.7 | 2.3 |
| `departement/77.html` | 1085.0 | 86.1 | 2.2 |
| `departement/49.html` | 1051.7 | 79.7 | 2.1 |
| `departement/67.html` | 998.6 | 83.7 | 2.0 |
| `departement/17.html` | 988.0 | 77.5 | 2.0 |
| `departement/14.html` | 974.1 | 79.7 | 1.9 |
| `departement/42.html` | 940.1 | 75.9 | 1.9 |
| `departement/64.html` | 925.5 | 72.0 | 1.9 |
| `departement/85.html` | 924.8 | 73.7 | 1.8 |
| `departement/57.html` | 910.1 | 74.3 | 1.8 |
| `departement/50.html` | 903.1 | 64.7 | 1.8 |
| `departement/56.html` | 876.3 | 70.5 | 1.8 |
| `departement/54.html` | 854.5 | 73.5 | 1.7 |
| `departement/60.html` | 811.0 | 68.4 | 1.6 |
| `departement/71.html` | 804.7 | 62.7 | 1.6 |
| `departement/74.html` | 778.9 | 64.5 | 1.6 |
| `departement/68.html` | 775.2 | 65.2 | 1.6 |
| `departement/30.html` | 764.4 | 65.4 | 1.5 |
| `departement/22.html` | 764.0 | 62.0 | 1.5 |
| `departement/45.html` | 755.5 | 63.6 | 1.5 |
| `departement/86.html` | 724.0 | 58.7 | 1.4 |
| `departement/63.html` | 716.7 | 60.3 | 1.4 |
| `departement/26.html` | 710.7 | 61.6 | 1.4 |
| `departement/27.html` | 703.4 | 61.0 | 1.4 |
| `departement/72.html` | 695.9 | 57.9 | 1.4 |
| `departement/84.html` | 671.1 | 55.3 | 1.3 |
| `departement/25.html` | 661.8 | 58.7 | 1.3 |
| `departement/80.html` | 661.2 | 57.2 | 1.3 |
| `departement/21.html` | 657.5 | 56.2 | 1.3 |
| `departement/37.html` | 651.7 | 56.6 | 1.3 |
| `departement/51.html` | 630.1 | 54.5 | 1.3 |
| `departement/02.html` | 614.0 | 53.1 | 1.2 |
| `departement/79.html` | 608.7 | 49.9 | 1.2 |
| `departement/974.html` | 602.2 | 50.7 | 1.2 |
| `departement/01.html` | 584.3 | 53.4 | 1.2 |
| `departement/16.html` | 582.1 | 48.9 | 1.2 |
| `departement/40.html` | 572.6 | 47.2 | 1.1 |
| `departement/66.html` | 569.7 | 48.9 | 1.1 |
| `departement/87.html` | 522.4 | 46.2 | 1.0 |
| `departement/47.html` | 507.1 | 44.3 | 1.0 |
## Provenance de la mesure (ajoutée à la main, 27/09/2026)

Chaîne rejouée en local sur les extraits complets du même jour, hors dépôt (`donnees/`, `site/`
gitignorés, D8) :

| Étape | Commande | Résultat |
|---|---|---|
| Acquisition | `scripts/telecharger_finess_structures.py`, `scripts/telecharger_finess_activites.py` | `finess-structures-journalier-20260927.json.gz` (50 395 722 o, sha1 `3bb1babe…`) et `finess-activites-journalier-20260927.json.gz` (58 629 376 o, sha1 `27e58b8b…`), checksums vérifiés |
| Chargement | `cli.py charger … --activites … --creer` | 1 min 59 s, millésime 202609, 5 290 255 lignes (174 821 établissements, 590 440 activités), base 670,1 Mio, 0 anomalie, schéma conforme |
| Intégrité | `cli.py integrite` | 68,6 s, 13 relations, 0 référence orpheline |
| Rendu | `export_html.py donnees/entrepot.sqlite --sortie site/` | 10,7 s, 104 pages, 102 fragments, 295 229 activités, 0 fragment orphelin |
| Mesure | `mesures/poids_site.py site/ --rapport mesures/poids_site.md` | 5,2 s, code de retour 1 (budget dépassé) |

Éléments d'analyse pour le découpage (mesurés sur ce même site) :

- Une ligne d'établissement de page départementale coûte ~450 octets (médiane sur les pages de
  plus de 500 lignes). Le seuil de 500 Ko tombe entre 1 097 et 1 112 lignes : 60 départements
  sur 101 le franchissent. Les pages portent tous les établissements FINESS, toutes catégories,
  faute de couche 4 (périmètre enfance non encore qualifié).
- Sur `departement/59.html` (6 892 lignes, 2 957,5 Ko de HTML), trois motifs répétés à chaque
  ligne pèsent à eux seuls ~700 Ko : le paragraphe d'attente
  `<p class="activites-etat">Détail chargé à l'ouverture…</p>` (~400 Ko), `<span class="code-brut">` (~204 Ko), `data-dep="59"` (~94 Ko). Réduire le
  balisage ne suffit pas : même allégée de moitié, la page resterait à ~3 × le budget.
- `indicateur.html` : 8 434 lignes département × catégorie, ~250 octets chacune (barre de
  proportion en trois `<div>` imbriqués), 2 133,7 Ko.
- Rappel OOM-108 (avant OOM-107) : `departement/59.html` à 6,7 Mo, `indicateur.html` à 2,1 Mo.
  OOM-107 a divisé la page du Nord par ~2,3 en sortant le détail des activités ; l'indicateur
  est inchangé.
- En gzip, toutes les pages passent sous 500 Ko (max 223,3 Ko), mais D9 porte sur la taille
  brute : le navigateur décompresse et construit le DOM de 6 892 lignes quelle que soit la
  compression du transport.

Dépassement non toléré (condition d'arrêt 3 du plan 09) : découpage plus fin ouvert en
**OOM-115**. Aucune optimisation dans OOM-109, hors périmètre.
