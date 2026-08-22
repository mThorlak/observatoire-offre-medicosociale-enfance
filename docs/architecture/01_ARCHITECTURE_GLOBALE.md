Voici l'architecture cible. Elle part de trois contraintes non négociables issues de l'analyse : les fichiers ne tiennent pas en mémoire sur Termux, les libellés doivent venir de l'extérieur, et un observatoire scientifique doit pouvoir rejouer et justifier chaque chiffre.

## 1. Décisions structurantes

**D1 — Un entrepôt local SQLite entre l'ingestion et l'analyse.** C'est la décision pivot. Elle règle d'un coup la mémoire (écriture par lots, mémoire bornée), la relecture (on ne reparse jamais 1,4 Go pour répondre à une question), les jointures multi-sources et la reproductibilité. `sqlite3` est dans la bibliothèque standard, fonctionne sur Termux, encaisse plusieurs millions de lignes et sait indexer. Sans cette couche, chaque source ajoutée obligerait à recharger tout en mémoire simultanément.

**D2 — Un modèle pivot indépendant des sources.** Aucune couche au-dessus du pivot ne connaît de vocabulaire de source. C'est ce qui permet d'ajouter INSEE ou ROR sans toucher au cœur : une source coûte un connecteur, ses tables miroir et une règle de projection, rien d'autre.

> **Précision (2026-08-22, OOM-46).** La lecture littérale de D2 — « le schéma d'entrepôt ne décalque aucune source » — a été abandonnée. La couche 2 **est** un miroir par source, assumé et confiné ; le pivot est posé au-dessus en tant que donnée calculée au sens de D3. Motifs mesurés, options écartées et contraintes de mise en œuvre : **`07_DECISION_PIVOT_HYBRIDE.md`**.

**D3 — Séparation stricte entre le lu et le calculé.** Les tables issues des sources sont immuables une fois chargées. Les tables de classement, de périmètre et d'indicateurs sont recalculables intégralement sans réingestion. Changer la taxonomie ne doit jamais coûter une relecture de 2 Go.

**D4 — Les nomenclatures, la taxonomie et le périmètre sont des données versionnées, pas du code.** Le V1 codait « Institut Thérapeutique Éducatif… » en dur dans un module Python. Ces règles deviennent des fichiers de référence datés, validés à l'exécution, et chaque résultat porte le numéro de version des règles qui l'ont produit.

**D5 — Provenance sur chaque ligne.** Source, millésime, lot d'ingestion, date. Sans cela, impossible de faire des séries temporelles ni de répondre à « d'où sort ce chiffre ».

**D6 — Aucun échec silencieux.** Chaque étape produit des compteurs entrée/sortie et des invariants bloquants. Un export ne peut pas être produit sur un entrepôt en échec.

---

## 2. Vue en couches

```
6  RESTITUTION      export_excel · export_tabulaire · export_geo · rapport
5  ANALYSE          vues · indicateurs · qualite
4  DOMAINE          taxonomie · perimetre · dispositifs · capacites · identite
3  RÉFÉRENTIELS     nomenclatures · territoires
2  ENTREPÔT         schema · entrepot · chargement
1  ACQUISITION      contrat_source · flux_json · sources/*
0  SOCLE            config · journal · controles
    ─────────────────────────────────────────────────
    ORCHESTRATION   pipeline · cli
```

Règle de dépendance : une couche ne connaît que les couches strictement inférieures. Le domaine ignore l'existence de FINESS et de JSON. La restitution ignore le métier. L'acquisition ignore la taxonomie.

---

## 3. Modules et responsabilités

**Couche 0 — Socle**

| Module | Responsabilité | Ne fait jamais |
|---|---|---|
| `config` | Chemins, millésime courant, seuils, paramètres d'exécution | Aucune logique métier |
| `journal` | Journalisation structurée, compteurs par étape, trace d'exécution horodatée | Décider d'un arrêt |
| `controles` | Déclaration et évaluation des invariants, classement par sévérité (bloquant / avertissement) | Corriger les données |

**Couche 1 — Acquisition**

| Module | Responsabilité |
|---|---|
| `flux_json` | Lecture incrémentale d'un gros JSON, à mémoire bornée, restituant les objets d'un tableau racine un par un. Générique, aucune connaissance de FINESS |
| `contrat_source` | Le contrat que tout connecteur respecte : déclarer son identité et son millésime, calculer l'empreinte du fichier, produire des enregistrements canoniques, déclarer les nomenclatures qu'il apporte et les identifiants qu'il expose |
| `sources/finess_structures` | Traduit `pmej` / `ege` / `gco` / `gcc` en entités, adresses, contacts, engagements, événements, groupements du pivot |
| `sources/finess_activites` | Traduit `activitesExercees` et `capacite[]` en activités et capacités du pivot. Ignore délibérément `activitesAutorisees` (redondant) sauf pour contrôle croisé |
| `sources/insee`, `sources/cnsa`, `sources/ror`, `sources/ign`, `sources/osm` | À venir, même contrat, même point d'insertion |

Chaque connecteur fait une seule chose : **traduire**. Aucun filtrage métier, aucun classement, aucun calcul. Un connecteur qui déciderait ce qui relève de l'enfance serait une erreur d'architecture.

**Couche 2 — Entrepôt**

| Module | Responsabilité |
|---|---|
| `schema` | Définition déclarative des tables, clés, contraintes et index |
| `entrepot` | Ouverture, transactions, création et reconstruction du schéma, index posés après chargement |
| `chargement` | Écriture par lots des enregistrements canoniques, gestion du lot d'ingestion et de la provenance, idempotence par empreinte de fichier |

**Couche 3 — Référentiels**

| Module | Responsabilité |
|---|---|
| `nomenclatures` | Tables code → libellé versionnées par domaine (catégorie, discipline, mode de fonctionnement, public, statut de capacité, type d'engagement, MFT, type de voie…). Résolution, et surtout **signalement exhaustif des codes rencontrés mais inconnus** |
| `territoires` | Communes, départements, régions, rattachements. Alimenté provisoirement par dérivation du COG, remplacé sans rupture par INSEE |

**Couche 4 — Domaine**

| Module | Responsabilité |
|---|---|
| `identite` | Résolution des identifiants et gestion de la table de liens externes. Point d'entrée unique de tout appariement inter-sources |
| `taxonomie` | Classement déclaratif **par codes** en familles et sous-familles, validé contre les nomenclatures au chargement |
| `perimetre` | Règles du champ enfance-adolescence : catégories retenues, codes public, bornes d'âge, natures d'activité. Produit une qualification motivée, pas un booléen nu |
| `dispositifs` | Détection des fonctionnements en dispositif à partir des engagements (`DISP/DIT`, `UEM`, `UEE`, `UEA`, `PCP`, `EMA`…) |
| `capacites` | Règles d'interprétation autorisée / installée, unités de mesure, non-double-comptage entre niveaux EJ et ET |

**Couche 5 — Analyse**

| Module | Responsabilité |
|---|---|
| `vues` | Vues dénormalisées stables : établissement enrichi, activité enrichie, capacité enrichie. Contrat unique entre le métier et la restitution |
| `indicateurs` | Agrégats, densités rapportées à la population, séries par millésime |
| `qualite` | Complétude, couverture des jointures, codes inconnus, écarts de recoupement entre feuilles et tables |

**Couche 6 — Restitution**

| Module | Responsabilité |
|---|---|
| `export_excel` | Écriture en flux, générique, à mémoire constante. Aucune règle métier |
| `export_tabulaire` | CSV/TSV pour réutilisation statistique |
| `export_geo` | GeoJSON pour cartographie |
| `rapport` | Synthèse d'exécution : volumétrie, invariants, versions des règles |

**Orchestration** : `pipeline` enchaîne les étapes, gère la reprise et l'idempotence ; `cli` expose les commandes.

---

## 4. Modèle de données pivot

**Traçabilité** — `lot_ingestion` (source, millésime, date d'exécution, empreinte du fichier, nombre lu, nombre retenu, statut). Chaque ligne de chaque table porte l'identifiant de son lot.

**Entités** — `entite_juridique`, `etablissement`, `adresse`, `contact`, `activite`, `capacite`, `engagement`, `evenement`, `groupement` et `groupement_membre`, `zone_intervention`, `relation_etablissement`.

Points de conception importants :

- `etablissement` porte le code catégorie, jamais le libellé. Le libellé est une jointure, pas une donnée.
- `adresse` porte latitude, longitude, méthode de géocodage et score. Elle est prête pour IGN et OSM sans modification.
- `activite` porte le triplet en codes, les quatre bornes d'âge, la nature, l'état et les dates d'autorisation.
- `capacite` porte le statut et l'unité en codes, avec les qualifiants (habilitation, type de logement, genre, mode de financement).
- `etat` et `date_fermeture` sont conservés partout : les entités fermées ne sont pas filtrées à l'ingestion, elles le sont à l'analyse. C'est ce qui rend les séries temporelles possibles.

**Charnière d'extensibilité** — `identifiant_externe` : entité pivot, type d'entité, système (FINESS, SIREN, SIRET, ROR, OSM, COG…), valeur, méthode d'appariement, indice de confiance, lot. Toute source nouvelle s'accroche ici. C'est cette table, et elle seule, qui évite une refonte quand ROR ou OSM arrivent.

**Soupape** — `attribut_source` : couple clé/valeur rattaché à une entité, pour les champs propres à une source qui ne méritent pas encore une colonne. À utiliser avec parcimonie : c'est une réserve d'évolution, pas un fourre-tout.

**Tables calculées, entièrement reconstructibles** — `classement_taxonomie`, `qualification_perimetre`, `dispositif`, `indicateur`. Chacune porte la version des règles appliquées.

---

## 5. Pipeline

| Étape | Entrée | Sortie | Invariant bloquant |
|---|---|---|---|
| 0 · Préparer | Fichiers sources | Lot ouvert, empreintes, millésime | Fichier absent, illisible ou millésime déjà chargé |
| 1 · Ingérer | Flux JSON | Tables sources peuplées | Zéro entité ingérée ; écart entre lu et retenu au-delà du seuil |
| 2 · Référencer | Nomenclatures | Table de libellés validée | Taux de codes inconnus au-delà du seuil |
| 3 · Apparier | Identifiants | Liens d'identité | Établissement sans entité juridique rattachée |
| 4 · Qualifier | Règles versionnées | Classements, périmètre, dispositifs | Règle référençant un code inexistant |
| 5 · Analyser | Vues | Indicateurs, séries | Totaux non recoupables entre niveaux |
| 6 · Restituer | Vues et indicateurs | Excel, CSV, GeoJSON | Étape 5 en échec |
| 7 · Contrôler | Journal, compteurs | Rapport de qualité | — |

Propriétés exigées de chaque étape : idempotence, reprise possible à l'étape suivante, compteurs entrée/sortie journalisés, aucune modification des étapes amont. Les étapes 4 à 6 doivent pouvoir être rejouées seules, en quelques secondes, sans retoucher aux fichiers sources — c'est la condition pour itérer sur la taxonomie et le périmètre.

---

## 6. Points d'accroche des sources futures

| Source | Ce qu'elle apporte | Où elle s'accroche | Clé de jointure | Impact sur le cœur |
|---|---|---|---|---|
| **INSEE** | Libellés et hiérarchie des territoires, population par commune, SIRENE | `territoires`, `nomenclatures`, `identifiant_externe` | `cog_commune`, SIREN/SIRET | Aucun. Remplace la dérivation provisoire du COG |
| **CNSA** | Capacités financées, catégorisation ESMS, remontées d'activité | Table de faits parallèle à `capacite`, jamais en écrasement | N° FINESS ET | Additif. Permet la confrontation autorisé / installé / financé |
| **ROR** | Offre opérationnelle, unités, disponibilités | Nouvelle table de faits + `identifiant_externe` | FINESS puis identifiant ROR | Additif |
| **IGN** | Géocodage de référence, contours administratifs | `adresse` (colonnes déjà prévues), table de géométries territoriales | Coordonnées, `cog_commune` | Additif |
| **OSM** | Points d'intérêt, accessibilité, desserte | `identifiant_externe` + un module `appariement_spatial` dédié | Proximité géographique et nom | Additif, avec indice de confiance obligatoire |

Le test de validité de l'architecture est simple : **ajouter une source doit coûter un connecteur, éventuellement une nomenclature et une règle d'appariement. Rien d'autre ne doit bouger.** Si l'ajout d'INSEE oblige à modifier `etablissement` ou `export_excel`, le découpage est mauvais.

---

## 7. Correspondance V1 → V2

| V1 | Devient |
|---|---|
| `lecture_csv.py` | `flux_json` + `sources/finess_structures` + `sources/finess_activites` |
| `categories.py` | Absorbé par `nomenclatures` (libellés) et `indicateurs` (comptages) |
| `taxonomie.py` | `taxonomie` réindexé sur les codes + un fichier de règles versionné |
| `excel.py` | `export_excel` en écriture flux |
| `observatoire.py` | Éclaté en `pipeline` + `cli` ; les conversions namedtuple ↔ dict disparaissent avec l'entrepôt |

---

## 8. Ce que l'architecture exclut délibérément

Pas d'ORM, pas de framework, pas de service ni d'API : le contexte d'exécution reste un poste local et Termux. Pas de chargement intégral en mémoire, à aucune étape. Pas de logique métier dans les connecteurs ni dans les exports. Pas de libellé écrit en dur dans du code Python. Pas de filtrage du périmètre à l'ingestion : on charge tout, on qualifie ensuite. Et pas de dépendance tierce autre qu'`openpyxl` pour la restitution Excel, isolée dans un seul module afin de rester remplaçable.
