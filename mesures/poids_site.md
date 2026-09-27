# Poids du site — mesure D9 (OOM-109, OOM-115)

Site mesuré : `site/` · 434 pages HTML, 225 fragments, 3 actifs.  
Budget D9 : 500.0 Ko bruts au chargement initial (HTML + actifs référencés, hors fragments chargés à la demande).

## Chargement initial, par type de page

| Type | Pages | Médiane (Ko) | Max (Ko) | Max gzip (Ko) | Page la plus lourde | Hors budget |
|---|---:|---:|---:|---:|---|---:|
| `departement/*.html` | 102 | 8.0 | 8.7 | 3.0 | `departement/75.html` | 0 |
| `departement/*/*.html` | 225 | 367.7 | 410.2 | 40.2 | `departement/35/3.html` | 0 |
| `index.html` | 1 | 36.6 | 36.6 | 8.7 | `index.html` | 0 |
| `indicateur.html` | 1 | 29.1 | 29.1 | 6.7 | `indicateur.html` | 0 |
| `indicateur/*.html` | 105 | 32.9 | 40.7 | 7.8 | `indicateur/59.html` | 0 |

**Page la plus lourde : `departement/35/3.html`, 410.2 Ko au chargement initial** (HTML 391.6 Ko + actifs `actifs/activites.js`, `actifs/filtres.js`, `actifs/ooms.css` ; 40.2 Ko en gzip), soit 0.8 × le budget.

## Fragments chargés à la demande (hors budget initial)

| Type | Fichiers | Médiane (Ko) | Max (Ko) | Max gzip (Ko) | Plus lourd | Total (Ko) |
|---|---:|---:|---:|---:|---|---:|
| `donnees/activites/*/*.json` | 225 | 334.8 | 710.7 | 34.9 | `donnees/activites/13/4.json` | 74964.9 |

## Actifs

| Actif | Brut (Ko) | gzip (Ko) |
|---|---:|---:|
| `actifs/activites.js` | 6.2 | 2.3 |
| `actifs/filtres.js` | 6.6 | 2.3 |
| `actifs/ooms.css` | 5.8 | 1.9 |

## Verdict D9

Budget tenu : aucune page au-delà de 500.0 Ko.
## Provenance de la mesure (ajoutée à la main, 27/09/2026, OOM-115)

Chaîne rejouée en local sur les extraits complets du même jour, hors dépôt (`donnees/`, `site/`
gitignorés, D8) — mêmes fichiers que la mesure d'OOM-109 :

| Étape | Commande | Résultat |
|---|---|---|
| Acquisition | `scripts/telecharger_finess_structures.py`, `scripts/telecharger_finess_activites.py` | `finess-structures-journalier-20260927.json.gz` (50 395 722 o, sha1 `3bb1babe…`) et `finess-activites-journalier-20260927.json.gz` (58 629 376 o, sha1 `27e58b8b…`), checksums vérifiés |
| Chargement | `cli.py charger … --activites … --creer` | 1 min 42 s, millésime 202609, 174 821 établissements, schéma conforme |
| Rendu | `export_html.py donnees/entrepot.sqlite --sortie site/` | 11,1 s, 434 pages (index, indicateur, 105 pages d'indicateur, 102 pages de département, 225 sous-pages), 225 fragments, 295 229 activités, 0 orpheline |
| Mesure | `mesures/poids_site.py site/ --rapport mesures/poids_site.md` | 9,0 s, **code de retour 0** |

Avant / après (OOM-109 → OOM-115), chargement initial brut :

| Type de page | Pages | Médiane (Ko) | Max (Ko) | Max gzip (Ko) | Hors budget |
|---|---:|---:|---:|---:|---:|
| `departement/*.html` avant (toutes les fiches) | 102 | 622,1 | 2 975,7 (`59.html`) | 223,3 | **60** |
| `departement/*.html` après (sommaire, aucune fiche) | 102 | 8,0 | 8,7 (`75.html`) | 3,0 | 0 |
| `departement/*/*.html` après (sous-pages ≤ 1 000 lignes) | 225 | 367,7 | 410,2 (`35/3.html`) | 40,2 | 0 |
| `indicateur.html` avant (tableau entier) | 1 | 2 133,7 | 2 133,7 | 83,1 | **1** |
| `indicateur.html` après (sommaire, 105 départements) | 1 | 29,1 | 29,1 | 6,7 | 0 |
| `indicateur/*.html` après (un département) | 105 | 32,9 | 40,7 (`59.html`) | 7,8 | 0 |
| `index.html` | 1 → 1 | 36,4 → 36,6 | 36,4 → 36,6 | 8,6 → 8,7 | 0 |
| **Total hors budget** | | | | | **61 → 0** |

Éléments de décision (mesurés sur ce même site) :

- Borne `LIGNES_PAR_SOUS_PAGE` = 1 000 : après allègement du balisage (suppression du paragraphe
  d'attente des activités et de `data-dep`, inutile sur une page départementale), une ligne
  d'établissement pèse 364 octets en médiane et 456 au plus ; le reste d'une sous-page 17,0 Ko au
  plus, les actifs 18,5 Ko. Mille fois la ligne la plus longue tiendrait encore sous 500 Ko
  (~480 Ko). Le budget n'est pas pour autant confié à la borne : `export_html.rendre` mesure chaque
  page, actifs compris, et lève `ErreurExportHtml` avant toute écriture au-delà de 500 Ko.
- 67 des 102 pages de département se répartissent en plusieurs sous-pages (Nord : 7, dont 6 pleines) ; les
  autres ont une seule sous-page, sans cas particulier.
- Fragments d'activités : un par sous-page plutôt qu'un par département. Le plus lourd tombe de
  3 144,5 Ko (`59.json`) à 710,7 Ko (`13/4.json`) ; le total est inchangé (74 964,9 Ko), aucun n'est
  chargé à l'ouverture d'une page.
- Indicateur : découpé par département, chaque page a au plus une ligne par catégorie (153
  catégories au tableau), jamais une par établissement : 40,7 Ko au plus. Par catégorie, chaque
  page aurait au plus une ligne par département (105), borne du même ordre ; le découpage par
  département est retenu pour sa symétrie avec les pages départementales.
