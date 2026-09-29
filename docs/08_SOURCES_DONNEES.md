# 08 – Sources de données

## 1. Objectif

Ce document recense l'ensemble des sources de données utilisées ou destinées à être utilisées par l'Observatoire national de l'offre médico-sociale.

Il décrit, pour chacune d'elles :

- son producteur ;
- son périmètre ;
- sa fréquence de mise à jour ;
- sa licence ;
- son rôle dans l'observatoire ;
- ses limites ;
- son niveau d'intégration.

Ce document constitue le référentiel documentaire des sources du projet.

---

# 2. Principes généraux

L'observatoire repose exclusivement sur des données dont l'utilisation est compatible avec les objectifs scientifiques du projet.

Chaque source est conservée dans son état d'origine.

Les traitements réalisés par l'observatoire sont reproductibles et n'altèrent jamais les données sources.

Une même information peut provenir de plusieurs producteurs.

Dans ce cas, chaque donnée conserve sa provenance afin d'assurer une traçabilité complète.

---

# 3. Sources actuellement intégrées

## FINESS

### Producteur

Ministère chargé de la Santé

### Type

Référentiel national des établissements sanitaires, sociaux et médico-sociaux.

### Fréquence

Publication mensuelle.

### Rôle

Source principale de l'observatoire.

Elle permet notamment de décrire :

- les entités juridiques ;
- les établissements ;
- les activités ;
- les capacités autorisées ;
- les capacités installées ;
- les dispositifs ;
- les engagements ;
- les événements ;
- les relations entre établissements.

### Identifiants principaux

- FINESS ET
- FINESS EJ

### Forces

- couverture nationale ;
- mise à jour régulière ;
- données officielles ;
- historique des établissements.

### Limites

- certaines nomenclatures sont publiées séparément ;
- qualité variable selon les champs ;
- informations parfois déclaratives ;
- présence d'établissements inactifs.

### Nomenclature des catégories d'établissement

Référentiel versionné : `referentiels/nomenclature_categorie_finess.csv` (D4), lu par
`nomenclatures.charger_categories`. Deux sources officielles, consignées dans son en-tête :

| Lignes | Source | Consultée le |
| --- | --- | --- |
| 274 codes (OOM-12) | DREES/DMSI, data.gouv.fr « FINESS - Extraction des principales nomenclatures » : catégories ouvertes (01-06-2021) et fermées (08-06-2021), PDF | 2026-08-18 |
| 40 codes (OOM-117) | ANS, NOS [`TRE_R66-CategorieEtablissement`](https://mos.esante.gouv.fr/NOS/TRE_R66-CategorieEtablissement/), OID 1.2.250.1.213.1.6.1.8, version `20260505120000` (322 codes), fichier `.tabs`, colonne « Libellé long » | 2026-09-29 |

Les 40 codes ajoutés sont ceux que l'extrait FINESS-Structures journalier du 2026-09-29
(millésime 202609) porte sans que les PDF de 2021 les documentent — les mêmes qu'en 202607 :
218, 220, 242, 259, 324, 345, 359, 400, 403, 405, 447, 450, 451, 452, 601, 602, 605–609, 614,
616, 617, 621, 622, 637–650. Tous figurent dans TRE_R66 : **aucun code observé ne reste non
résolu**. 17 sont des catégories fermées (`statut` = `fermee`, `date_fermeture` = « Date fin »
de TRE_R66), qui subsistent sur des établissements existants — par exemple 220 « Centre
Social » et 405 « Service Social Polyvalent de Secteur », fermées le 2026-03-30, ou 602
« Cabinet de Groupe », fermée le 1999-09-15. Le code 259, écarté en OOM-12 parce que son
libellé PDF était tronqué, est repris avec le libellé complet de TRE_R66. Un code qui
apparaîtrait demain hors référentiel reste signalé (`CodeCategorieInconnu`, compteur
« catégorie(s) non résolue(s) » d'`export_html`), jamais approximé (D6).

**Écart connu, non traité.** Les 274 lignes d'origine n'ont pas été modifiées (OOM-117 ne fait
qu'ajouter). Or TRE_R66 2026 renomme 24 de ces catégories (ex. 209 « Service autonomie aide et
soins (SAAS) » au lieu de « S.P.A.S.A.D. », 460 « Service autonomie aide (SAA) » au lieu de
« S.A.A.D. », 228 « Centre de Santé Sexuelle ») ; pour 17 d'entre elles, la date de fin de TRE_R66 diffère de celle du PDF de 2021
ou existe là où le PDF n'en donnait aucune (ex. 159, 252, 418). Réaligner ces lignes sur TRE_R66 est
une décision distincte (quelle source fait foi, quel libellé pour une catégorie renommée).

### Statut

🟢 Intégré

---

# 4. Sources prévues

## INSEE

### Producteur

Institut national de la statistique et des études économiques.

### Rôle

Apporter le contexte démographique, territorial et socio-économique.

### Informations attendues

- communes ;
- départements ;
- régions ;
- populations ;
- pyramides des âges ;
- densité de population ;
- revenus ;
- pauvreté ;
- chômage ;
- niveau d'études ;
- catégories socioprofessionnelles ;
- urbanisation.

### Utilisations prévues

Calcul des indicateurs territoriaux.

Calcul des densités.

Calcul des taux rapportés à la population.

### Statut

🟡 Prévu

---

## ROR

### Producteur

Agence du Numérique en Santé.

### Rôle

Décrire l'offre opérationnelle.

### Informations attendues

- structures opérationnelles ;
- unités ;
- modalités de prise en charge ;
- contacts ;
- informations de fonctionnement.

### Utilisations prévues

Compléter FINESS.

Améliorer la description fonctionnelle de l'offre.

### Statut

🟡 Prévu

---

## CNSA

### Producteur

Caisse nationale de solidarité pour l'autonomie.

### Rôle

Compléter les informations relatives au secteur médico-social.

### Informations attendues

- financements ;
- capacités ;
- organisation.

### Statut

🟡 Prévu

---

## DREES

### Producteur

Direction de la recherche, des études, de l'évaluation et des statistiques.

### Rôle

Fournir des indicateurs nationaux et territoriaux.

### Informations attendues

- statistiques médico-sociales ;
- données sanitaires ;
- indicateurs nationaux.

### Statut

🟡 Prévu

---

## IGN

### Producteur

Institut national de l'information géographique et forestière.

### Rôle

Référentiel géographique.

### Informations attendues

- limites administratives ;
- géométries ;
- fonds cartographiques.

### Utilisations

Cartographie.

Calculs spatiaux.

Distances.

### Statut

🟡 Prévu

---

## OpenStreetMap

### Producteur

Projet collaboratif international.

### Rôle

Compléter les analyses spatiales.

### Informations attendues

- réseau routier ;
- temps de trajet ;
- accessibilité ;
- points d'intérêt.

### Utilisations

Calcul des temps d'accès.

Études d'accessibilité.

### Statut

🟡 Prévu

---

# 5. Sources potentielles

Selon l'évolution du projet, d'autres bases pourront être intégrées.

Exemples :

- Éducation nationale ;
- Assurance Maladie ;
- Santé publique France ;
- Bases hospitalières ;
- jeux de données régionaux ;
- observatoires départementaux.

Toute nouvelle source devra faire l'objet d'une documentation avant son intégration.

---

# 6. Articulation des sources

Le projet suit une architecture multi-sources.

Chaque producteur est intégré indépendamment.

Les traitements scientifiques sont réalisés sur un modèle de données commun.

L'ajout d'une nouvelle source ne doit pas nécessiter de modifier les traitements existants.

---

# 7. Principes de qualité

Chaque source est évaluée selon plusieurs critères :

- couverture ;
- fraîcheur ;
- stabilité ;
- complétude ;
- cohérence ;
- traçabilité.

Les anomalies sont documentées et conservées.

Les données ne sont jamais corrigées silencieusement.

---

# 8. Gestion des versions

Chaque import conserve :

- la source ;
- le millésime ;
- la date de téléchargement ;
- la date d'intégration ;
- la version éventuelle du schéma ;
- l'empreinte du fichier.

Ces informations permettent de reproduire exactement une analyse.

---

# 9. Évolutivité

L'observatoire est conçu pour intégrer progressivement de nouvelles sources de données.

Le modèle de données pivot garantit que l'ajout d'un nouveau producteur ne remet pas en cause les traitements existants.

Les nouvelles sources ont vocation à enrichir les analyses sans modifier les résultats obtenus à partir des sources déjà intégrées.

  ---

# 10. Classification des sources

Toutes les sources de données n'ont pas le même rôle dans l'observatoire.

Elles sont classées selon leur importance scientifique et leur fonction.

## Sources fondamentales

Ces sources constituent le cœur de l'observatoire.

Sans elles, le projet ne peut pas fonctionner.

| Source | Fonction principale |
|---------|---------------------|
| FINESS | Offre médico-sociale et sanitaire |
| INSEE | Population, territoires et contexte socio-économique |

---

## Sources structurantes

Ces sources enrichissent fortement les analyses mais ne sont pas indispensables au fonctionnement minimal de l'observatoire.

| Source | Fonction principale |
|---------|---------------------|
| ROR | Offre opérationnelle |
| CNSA | Informations complémentaires sur le secteur médico-social |
| DREES | Indicateurs sanitaires et médico-sociaux |
| IGN | Référentiel géographique |

---

## Sources complémentaires

Ces sources permettent des analyses spécifiques.

| Source | Fonction principale |
|---------|---------------------|
| OpenStreetMap | Réseau routier, accessibilité, temps de trajet |
| Éducation nationale | Offre scolaire, dispositifs d'inclusion |
| Jeux de données régionaux | Compléments locaux |

---

# 11. Niveau de confiance

Chaque source est documentée selon plusieurs dimensions.

## Fiabilité

Qualité globale de la donnée produite.

## Complétude

Proportion de champs effectivement renseignés.

## Pérennité

Probabilité que la source reste disponible à long terme.

## Fréquence de mise à jour

Actualisation des données.

## Interopérabilité

Facilité de croisement avec les autres sources.

---

Le tableau suivant synthétise cette évaluation.

| Source | Fiabilité | Complétude | Pérennité | Mise à jour | Interopérabilité |
|---------|-----------|------------|-----------|-------------|------------------|
| FINESS | Très élevée | Élevée | Très élevée | Mensuelle | Très élevée |
| INSEE | Très élevée | Très élevée | Très élevée | Variable selon les jeux | Très élevée |
| ROR | Élevée | Variable | Élevée | Fréquente | Élevée |
| CNSA | Élevée | Élevée | Très élevée | Variable | Élevée |
| DREES | Très élevée | Très élevée | Très élevée | Variable | Élevée |
| IGN | Très élevée | Très élevée | Très élevée | Régulière | Très élevée |
| OpenStreetMap | Bonne | Variable | Très élevée | Continue | Bonne |

---

# 12. Principe de complémentarité

Aucune source n'a vocation à remplacer une autre.

Le projet repose sur la complémentarité des producteurs.

Par exemple :

- FINESS décrit les établissements et les activités autorisées.
- ROR décrit leur fonctionnement opérationnel.
- INSEE décrit les territoires et les populations.
- IGN décrit l'espace géographique.
- OpenStreetMap décrit les réseaux de déplacement.
- DREES apporte des indicateurs sanitaires et médico-sociaux.
- CNSA apporte des informations spécifiques au secteur médico-social.

Le modèle pivot de l'observatoire permet de réunir ces informations sans altérer les données d'origine.

---

# 13. Principes d'intégration

Chaque nouvelle source doit respecter les règles suivantes :

- être documentée avant son intégration ;
- conserver les données d'origine ;
- être versionnée ;
- conserver sa provenance ;
- pouvoir être retirée sans remettre en cause les autres sources ;
- ne jamais modifier rétroactivement les données déjà intégrées.

Ces principes garantissent la reproductibilité des analyses et l'évolutivité de l'observatoire.

---

# 14. Procédure d'acquisition automatisée — FINESS-Structures

Constatée et testée le 13/08/2026, dans le cadre du premier POC.

## API

Le fichier journalier se découvre par l'API JSON de data.gouv.fr, jamais par une URL codée en dur (les URLs de téléchargement changent à chaque publication) :

```
GET https://www.data.gouv.fr/api/1/datasets/finess-structures-1/
```

La réponse porte une liste `resources`. Deux ressources y coexistent au même format (`json.gz`) : le flux journalier (`finess-structures-journalier-AAAAMMJJ.json.gz`) et un mensuel figé (`finess-structures-mensuel-AAAAMM.json.gz`). Chaque ressource porte `id`, `title`, `url` (téléchargement direct, hébergé sur `static.data.gouv.fr`), `filesize` (octets), `checksum` (`{type: "sha1", value: ...}`) et `last_modified`.

## Licence

Divergence repérée entre la page web du jeu de données (« Licence Ouverte / Open Licence v2.0 ») et la réponse de l'API (`ODbL`). Non tranchée à ce jour — à clarifier avant toute réutilisation publique des données produites par l'observatoire.

## Script

`scripts/telecharger_finess_structures.py` — interroge l'API, sélectionne par défaut la ressource journalière (distinguée par le préfixe du titre) ou, avec `--mensuel AAAAMM`, le mensuel figé de ce millésime (voir section 18), télécharge en flux, puis vérifie systématiquement **taille et checksum** contre les valeurs publiées avant d'écrire un fichier de métadonnées à côté du `.json.gz` (provenance : id de ressource, URL, taille, checksum, date de publication source, date de téléchargement). Refuse explicitement si zéro ou plusieurs ressources journalières sont trouvées, ou si taille/checksum divergent — jamais de fichier silencieusement corrompu ou mal identifié. Aucune dépendance tierce.

Testé hors réseau réel dans `tests/test_telecharger_finess_structures.py` (le double d'`urllib.request.urlopen` rejoue la forme de réponse constatée le 13/08/2026).

## Automatisation

Aucun environnement d'exécution utilisé pour développer ce projet (sessions Claude comprises) n'a d'accès réseau sortant vers data.gouv.fr — constaté par diagnostic complet (`curl -v` : tunnel CONNECT refusé par l'allowlist réseau, avant même d'atteindre le site). Le téléchargement quotidien est donc automatisé sur une infrastructure qui a un accès réseau normal : un workflow GitHub Actions planifié, `.github/workflows/finess-structures-quotidien.yml`, qui appelle le script ci-dessus tous les jours à 06:00 UTC.

**Politique de rétention** (décidée le 13/08/2026, à revoir si le besoin d'historique change) :

- chaque fichier quotidien est archivé en artefact GitHub Actions, conservé **35 jours** puis supprimé automatiquement par GitHub ;
- le **1er de chaque mois**, le fichier du jour est en plus publié comme snapshot permanent — une GitHub Release taguée `finess-structures-AAAA-MM`, qui n'expire jamais.

Le fichier brut n'est **jamais committé dans git** (voir `.gitignore`, `/donnees/`) : seuls les artefacts CI et les releases mensuelles en portent une copie durable, hors de l'historique git.

---

# 15. Procédure d'acquisition automatisée — FINESS-Activités

Constatée et testée le 19/08/2026, dans le cadre du premier POC.

## API

Le fichier journalier se découvre par l'API JSON de data.gouv.fr, jamais par une URL codée en dur (les URLs de téléchargement changent à chaque publication) :

```
GET https://www.data.gouv.fr/api/1/datasets/finess-activites-1/
```

La réponse porte une liste `resources`. Deux ressources y coexistent au même format (`json.gz`) : le flux journalier (`finess-activites-journalier-AAAAMMJJ.json.gz`) et un mensuel figé (`finess-activites-mensuel-AAAAMM.json.gz`). Contrairement à l'hypothèse initiale du ticket OOM-25 qui supposait une cadence mensuelle uniquement, l'API publie bien un journalier — le dispositif retenu mire donc Structures à l'identique (sélection du journalier, jamais du mensuel). Chaque ressource porte `id`, `title`, `url` (téléchargement direct, hébergé sur `static.data.gouv.fr`), `filesize` (octets), `checksum` (`{type: "sha1", value: ...}`) et `last_modified`.

## Licence

Le champ API `license` vaut `lov2` (Licence Ouverte v2.0), une seule valeur cohérente. Pas de divergence repérée entre la documentation publique et la réponse API cette fois (contrairement à Structures où une divergence Licence Ouverte / ODbL avait été observée et restait à trancher).

## Script

`scripts/telecharger_finess_activites.py` — interroge l'API, sélectionne par défaut la ressource journalière (distinguée par le préfixe du titre) ou, avec `--mensuel AAAAMM`, le mensuel figé de ce millésime (voir section 18), télécharge en flux, puis vérifie systématiquement **taille et checksum** contre les valeurs publiées avant d'écrire un fichier de métadonnées à côté du `.json.gz` (provenance : id de ressource, URL, taille, checksum, date de publication source, date de téléchargement). Refuse explicitement si zéro ou plusieurs ressources journalières sont trouvées, ou si taille/checksum divergent — jamais de fichier silencieusement corrompu ou mal identifié. Aucune dépendance tierce.

Testé hors réseau réel dans `tests/test_telecharger_finess_activites.py` (le double d'`urllib.request.urlopen` rejoue la forme de réponse constatée le 19/08/2026).

Le connecteur de couche 1 existant (`src/finess_activites.py`) est déjà validé contre ce format d'extrait (585 746 activités du millésime 202607, cf. tests intégrés).

## Automatisation

Aucun environnement d'exécution utilisé pour développer ce projet (sessions Claude comprises) n'a d'accès réseau sortant vers data.gouv.fr — constaté par diagnostic complet. Le téléchargement quotidien est donc automatisé sur une infrastructure qui a un accès réseau normal : un workflow GitHub Actions planifié, `.github/workflows/finess-activites-quotidien.yml`, qui appelle le script ci-dessus tous les jours à 06:00 UTC.

**Note** : Lors de la session du 19/08/2026, l'accès réseau a exceptionnellement fonctionné pour la constatation initiale de l'API, mais le principe reste que l'automatisation fiable et reproductible passe par un runner GitHub Actions, comme pour Structures — ne pas en déduire que l'accès réseau est garanti dans toutes les sessions futures.

**Politique de rétention** (identique à Structures, à revoir si le besoin d'historique change) :

- chaque fichier quotidien est archivé en artefact GitHub Actions, conservé **7 jours** puis supprimé automatiquement par GitHub (politique initiale identique à celle adoptée pour Structures avant vérification de la consommation réelle, à revoir après observation) ;
- le **1er de chaque mois**, le fichier du jour est en plus publié comme snapshot permanent — une GitHub Release taguée `finess-activites-AAAA-MM`, qui n'expire jamais.

Le fichier brut n'est **jamais committé dans git** (voir `.gitignore`, `/donnees/`) : seuls les artefacts CI et les releases mensuelles en portent une copie durable, hors de l'historique git.

## Dérives constatées

### 27/09/2026 — code de nature `ASMR` → `AMSR` (OOM-114)

**Constat.** L'extrait journalier `finess-activites-journalier-20260927.json.gz` (sha1 `27e58b8b…`) code la nature « activité sociale et médico-sociale régulée » en `AMSR` : 227 860 occurrences aux deux niveaux (113 924 `activitesAutorisees`, 113 936 `activitesExercees`), aucune `ASMR`. Le millésime 202607 (échantillon versionné : 2 058 `ASMR`) et l'extrait journalier du 19/08/2026 (113 549 `ASMR` par niveau) écrivent `ASMR`, aucune `AMSR`. Le connecteur ne déclarait que `ASMR` : 227 860 anomalies bloquantes `nature_non_declaree`, `cli.py charger` et `cli.py integrite` en échec.

**Nature de la dérive.** `scripts/recensement.py` rejoué sur les deux extraits (19/08 et 27/09) donne 216 chemins JSON identiques, de mêmes types : le bloc typé s'appelait déjà `typeActiviteAMSR` et garde le même jeu de clés. Seul le code change ; c'est un renommage, pas un changement de contenu.

**Traitement.** Équivalence **déclarée** dans `src/finess_activites.py` (`EQUIVALENCES_NATURE = {"AMSR": "ASMR"}`) : `AMSR` est soumis exactement au contrat de clés d'`ASMR`. Le `code_nature` stocké reste le code lu, verbatim — un extrait 202607 garde `ASMR`, un extrait de septembre `AMSR` ; aucune réécriture d'un code en l'autre (D2/D3). Toute requête aval qui vise cette nature doit donc interroger les deux codes, ou passer par la future nomenclature des natures (OOM-29). Tout autre code, y compris un voisin (`ASRM`, `amsr`, `AMS`), reste une anomalie bloquante `nature_non_declaree` (D6).

**Autres écarts du même recensement, sans effet bloquant** (valeurs nouvelles dans des champs codifiés déjà déclarés, aucun chemin ni type nouveau) : `sousTypeEngagement` `DIS` (Activités) et `SAD` (Structures), `codeEvenement`/`etatObjet1` `033`, `typeObjet2` `AC`, codes AMM `QA014`, `DE024`, `MO031`. Ils relèvent des nomenclatures, pas du connecteur.

---

# 16. Hébergeur de publication — support des requêtes HTTP Range (OOM-99)

Constaté le 19/09/2026 vers 07:00 UTC. Une archive PMTiles n'est lisible depuis le navigateur que si l'hébergeur honore les requêtes `Range` (lecture d'un intervalle d'octets, réponse `206 Partial Content`) ; sinon chaque tuile coûterait le téléchargement de l'archive entière. Vérification faite avant toute génération de tuiles, parce qu'un résultat négatif aurait invalidé le choix d'hébergeur.

## Hébergeur testé

GitHub Pages du dépôt public `mThorlak/observatoire-offre-medicosociale-enfance`, derrière le CDN Fastly de GitHub (`Server: GitHub.com`, `Via: 1.1 varnish`, nœud `cache-par-*`).

## Dispositif de test

- fichier `test.bin` : 1 048 576 octets aléatoires (`/dev/urandom`), SHA-256 `417be7bf3e829e979bb328a6fa989e8bebd8622610bf186628e44ab83e31949a` — seul fichier publié, avec un `.nojekyll` vide ;
- publié par une branche orpheline jetable `gh-pages-test` (un seul commit, sans lien avec l'historique de `main`) et Pages activé en mode **legacy** sur cette branche (`gh api -X POST repos/.../pages -f build_type=legacy -f "source[branch]=gh-pages-test" -f "source[path]=/"`). Chemin retenu parce que le plus simple : un workflow `workflow_dispatch` doit exister sur la branche par défaut pour être déclenchable, et l'environnement `github-pages` n'accepte par défaut que la branche par défaut — aucun des deux n'était possible sans toucher `main`. Aucun workflow n'a été créé ;
- URL : `https://mthorlak.github.io/observatoire-offre-medicosociale-enfance/test.bin`.

## Résultat : Range honoré (206)

`GET` avec `Range: bytes=0-99` :

```
$ curl -r 0-99 -s -D - -o p.bin <url>/test.bin
HTTP/1.1 206 Partial Content
Content-Length: 100
ETag: "6aae3319-100000"
Accept-Ranges: bytes
Content-Range: bytes 0-99/1048576
$ curl -r 0-99 -s <url>/test.bin | wc -c
100
```

Contrôles complémentaires, tous concluants :

- intervalle en milieu de fichier (`-r 524288-524387`) : `206`, `Content-Range: bytes 524288-524387/1048576`, et les 100 octets reçus ont le même SHA-256 que les octets 524 288 à 524 387 du fichier local — l'intervalle servi est exact, pas seulement de la bonne longueur ;
- `If-Range` avec l'ETag fort : `206` ;
- `Accept-Encoding: identity` : `206`, mêmes en-têtes ;
- fichier complet sans `Range` : `200`, SHA-256 identique à l'original ;
- `Content-Type: application/octet-stream`, `Access-Control-Allow-Origin: *` (lecture inter-origines possible), `Cache-Control: max-age=600`.

## Deux réserves consignées

1. **`HEAD` ignore `Range`.** La commande littérale `curl -r 0-99 -sI <url>/test.bin` (qui envoie un `HEAD`) renvoie `200 OK` avec `Content-Length: 1048576` et `Accept-Ranges: bytes`, pas un `206`. C'est le comportement prévu par HTTP (RFC 9110 §14.2 : `Range` ne s'applique qu'à `GET`) et sans conséquence : PMTiles ne lit que par `GET`. La preuve de support est le `GET` ci-dessus, pas le `HEAD`.
2. **Compression à la volée si le client l'accepte.** Avec `Accept-Encoding: gzip, deflate, br, zstd`, le CDN gzippe la réponse et applique l'intervalle au flux **compressé** : `206`, `Content-Encoding: gzip`, `Content-Range: bytes 0-99/1048914`, ETag devenu faible (`W/"..."`). Les 100 octets reçus ne sont alors pas les octets 0-99 du fichier. Les navigateurs ne sont pas exposés : la spécification Fetch impose `Accept-Encoding: identity` dès qu'une requête porte un en-tête `Range`, ce que fait la bibliothèque `pmtiles`. En revanche, tout client hors navigateur (script de vérification, outil en ligne de commande) doit envoyer `Accept-Encoding: identity` explicitement. À revérifier sur la vraie archive `.pmtiles` (dont le type MIME servi pourrait différer) lors de la génération des tuiles.

## Conséquence

GitHub Pages convient pour servir l'archive de tuiles : le repli prévu (archive sur un stockage objet dédié, site inchangé) n'est **pas** nécessaire.

## État laissé en place

Pages est activé en mode legacy sur `gh-pages-test`. La chaîne de publication pérenne (OOM-54) devra basculer la source sur « GitHub Actions » (`gh api -X PUT repos/.../pages -f build_type=workflow`) puis supprimer la branche `gh-pages-test`.

---

# 17. Attribution publiée sur le site (OOM-55)

Consignée le 29/09/2026, avant la mise en ligne publique du site.

## Ce qui est affiché

**Pied de page commun**, sur chaque page et sous-page du site (valeurs de `MENTIONS_PIED` dans `src/export_html.py`, substituées dans `front/gabarits/base.html` ; aucun gabarit ne les écrit en dur, D7 ; pas de script, D10) :

> Retraitement indépendant de données publiques, pas une donnée officielle de l'administration. Données : FINESS, ministère chargé de la Santé, publié sur data.gouv.fr. Code source : https://github.com/mThorlak/observatoire-offre-medicosociale-enfance, sous licence EUPL 1.2.

**Accueil, section « Source et licence »** (`front/gabarits/accueil.html`) :

- producteur et jeux de données, avec lien vers leur page data.gouv.fr (FINESS-Structures, FINESS-Activités) ;
- licence de chaque jeu, **divergence de FINESS-Structures comprise** (voir ci-dessous) ;
- lots chargés dans l'entrepôt ayant produit la page : source, millésime, fichier, empreinte (provenance D5) ;
- paragraphe « Méthode et reproductibilité » : entités fermées conservées mais exclues des comptages, périmètre enfance/adolescents non encore qualifié, construction rejouable avec les commandes du README.

La mention de périmètre (comptage brut, qualification enfance/adolescents non appliquée, OOM-103) reste en tête de l'accueil, avant tout chiffre.

## Divergence de licence de FINESS-Structures — non tranchée

La page web du jeu `finess-structures-1` annonce la Licence Ouverte / Open Licence v2.0 ; le champ `license` de l'API data.gouv.fr vaut `ODbL` (constat du 13/08/2026, section 14). FINESS-Activités ne présente pas cette divergence (`lov2`, section 15). L'observatoire ne tranche pas : l'accueil publie les deux indications telles quelles. Les deux licences exigent la mention de la source, que le pied de page et l'accueil portent ; l'ODbL impose en plus le partage à l'identique d'une base de données dérivée, question à régler avant toute redistribution de l'entrepôt lui-même (hors périmètre d'OOM-55).

## Licence du code

Le code est sous EUPL 1.2 (fichier `LICENSE` à la racine : texte officiel français publié par la Commission européenne). Elle ne s'applique pas aux données FINESS, qui restent sous la licence de leur producteur.

---

# 18. Extrait mensuel figé FINESS — publication du site (OOM-54)

Constaté le 29/09/2026 par l'API data.gouv.fr des deux jeux de données (`finess-structures-1`, `finess-activites-1`).

## Nom

À côté du journalier, chaque jeu publie un extrait **mensuel figé** au même format (`json.gz`), avec la même forme de ressource (`id`, `title`, `url`, `filesize`, `checksum` sha1, `last_modified`) :

- `finess-structures-mensuel-AAAAMM.json.gz`
- `finess-activites-mensuel-AAAAMM.json.gz`

`AAAAMM` est le mois des données : le mensuel `202608` est publié le 1er septembre. Ce motif porte le millésime lu par `finess_commun.extraire_millesime` : le fichier téléchargé doit garder son nom source (OOM-116), sinon le millésime devient `inconnu`, ce qui bloque la publication.

## Rythme de publication observé

| Mensuel | Structures (`created_at`, UTC) | Activités (`created_at`, UTC) | Taille Structures | Taille Activités |
|---|---|---|---:|---:|
| `202607` | 01/08/2026 02:15 (`last_modified` 04:15) | 01/08/2026 02:15 (`last_modified` 04:15) | 50 044 904 o | 57 793 142 o |
| `202608` | 01/09/2026 02:16 | 01/09/2026 02:16 | 50 191 316 o | 58 236 979 o |

Publication le **1er du mois suivant, vers 02:15 UTC**, simultanée sur les deux sources. Deux observations seulement : le rythme est constaté, pas garanti par le producteur.

## Profondeur d'historique disponible

Le 29/09/2026, l'API publie **deux mensuels par source, `202607` et `202608`**, plus le journalier du jour. Le plus ancien est le premier mensuel publié (créé le 01/08/2026 ; la ressource journalière date du 06/05/2026) : aucun mensuel n'a encore été retiré, mais la politique de conservation de data.gouv.fr n'est documentée nulle part. On ne sait donc pas si un mensuel reste publié indéfiniment ou s'il tourne sur une fenêtre glissante. Un millésime passé n'est reconstructible depuis la source que tant que data.gouv.fr le publie ; la conservation durable des extraits relève d'OOM-43 et OOM-45.

## Sélection

Les deux scripts de téléchargement prennent `--mensuel AAAAMM` : ils sélectionnent la ressource dont le titre est exactement `finess-*-mensuel-AAAAMM.json.gz`, puis vérifient taille et checksum comme pour le journalier. Si ce mensuel n'est pas publié (ou l'est en double), le script échoue avec la liste des mensuels disponibles, sans jamais se rabattre sur le journalier ni sur un mois voisin (D6). `--lister-mensuels` affiche les millésimes publiés, un par ligne, croissants, sans rien télécharger. Sans option, le journalier reste le comportement par défaut : les workflows d'acquisition quotidiens sont inchangés.

## Publication du site

`.github/workflows/pages.yml` ne publie plus que des mensuels. L'entrée `millesime` (`AAAAMM`) de `workflow_dispatch` désigne le millésime ; vide, elle vaut le dernier mensuel publié, résolu depuis l'API des deux sources (qui doivent concorder, sinon échec) et affiché dans le résumé du run. Un `schedule` le **3 du mois à 06:00 UTC** publie le dernier mensuel : deux jours de marge sur la publication observée le 1er vers 02:15 UTC. Si le mensuel du mois écoulé manque encore, le run reconstruit le dernier publié et le signale par un avertissement. Reconstruire le même millésime donne un site identique, à l'horodatage « Généré le » près.
