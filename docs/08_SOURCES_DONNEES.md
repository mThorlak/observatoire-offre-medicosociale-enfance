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
