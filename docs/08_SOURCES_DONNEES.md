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

`scripts/telecharger_finess_structures.py` — interroge l'API, sélectionne la ressource journalière (jamais la mensuelle, distinguée par le préfixe du titre), télécharge en flux, puis vérifie systématiquement **taille et checksum** contre les valeurs publiées avant d'écrire un fichier de métadonnées à côté du `.json.gz` (provenance : id de ressource, URL, taille, checksum, date de publication source, date de téléchargement). Refuse explicitement si zéro ou plusieurs ressources journalières sont trouvées, ou si taille/checksum divergent — jamais de fichier silencieusement corrompu ou mal identifié. Aucune dépendance tierce.

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

`scripts/telecharger_finess_activites.py` — interroge l'API, sélectionne la ressource journalière (jamais la mensuelle, distinguée par le préfixe du titre), télécharge en flux, puis vérifie systématiquement **taille et checksum** contre les valeurs publiées avant d'écrire un fichier de métadonnées à côté du `.json.gz` (provenance : id de ressource, URL, taille, checksum, date de publication source, date de téléchargement). Refuse explicitement si zéro ou plusieurs ressources journalières sont trouvées, ou si taille/checksum divergent — jamais de fichier silencieusement corrompu ou mal identifié. Aucune dépendance tierce.

Testé hors réseau réel dans `tests/test_telecharger_finess_activites.py` (le double d'`urllib.request.urlopen` rejoue la forme de réponse constatée le 19/08/2026).

Le connecteur de couche 1 existant (`src/finess_activites.py`) est déjà validé contre ce format d'extrait (585 746 activités du millésime 202607, cf. tests intégrés).

## Automatisation

Aucun environnement d'exécution utilisé pour développer ce projet (sessions Claude comprises) n'a d'accès réseau sortant vers data.gouv.fr — constaté par diagnostic complet. Le téléchargement quotidien est donc automatisé sur une infrastructure qui a un accès réseau normal : un workflow GitHub Actions planifié, `.github/workflows/finess-activites-quotidien.yml`, qui appelle le script ci-dessus tous les jours à 06:00 UTC.

**Note** : Lors de la session du 19/08/2026, l'accès réseau a exceptionnellement fonctionné pour la constatation initiale de l'API, mais le principe reste que l'automatisation fiable et reproductible passe par un runner GitHub Actions, comme pour Structures — ne pas en déduire que l'accès réseau est garanti dans toutes les sessions futures.

**Politique de rétention** (identique à Structures, à revoir si le besoin d'historique change) :

- chaque fichier quotidien est archivé en artefact GitHub Actions, conservé **7 jours** puis supprimé automatiquement par GitHub (politique initiale identique à celle adoptée pour Structures avant vérification de la consommation réelle, à revoir après observation) ;
- le **1er de chaque mois**, le fichier du jour est en plus publié comme snapshot permanent — une GitHub Release taguée `finess-activites-AAAA-MM`, qui n'expire jamais.

Le fichier brut n'est **jamais committé dans git** (voir `.gitignore`, `/donnees/`) : seuls les artefacts CI et les releases mensuelles en portent une copie durable, hors de l'historique git.

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
