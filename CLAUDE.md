# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Observatoire national libre de l'offre médico-sociale enfance/adolescents, construit à partir de
données publiques (FINESS, à terme INSEE/CNSA/ROR/IGN/OSM). Double finalité : un logiciel
réutilisable et reproductible, et des travaux scientifiques exploitant les données produites.
Stdlib only + `openpyxl` (restitution Excel) — pas d'ORM, pas de framework, pas de service ni d'API :
le contexte d'exécution cible reste un poste local et Termux (téléphone). Python 3.9+ compatible.

**Deux contraintes distinctes, à ne pas confondre** :
- **Contrainte d'exécution** (`requirements.txt`, `openpyxl` seul) : ce que `src/` a le droit
  d'importer. Stdlib + `openpyxl`, rien d'autre — c'est ce qui garantit que le pipeline tourne sur un
  poste local et sur Termux. `grep -rn "import pytest" src/` ne doit jamais rien renvoyer.
- **Contrainte de développement** (`requirements-dev.txt` : `pytest`, `black`) : ce qu'il faut pour
  écrire, formater et tester le code. Ces paquets ne sont **jamais** importés par `src/` ; ils
  n'ont pas à être installés pour lancer le pipeline. Ajouter un outil de dev ici est libre, ajouter
  une dépendance à `requirements.txt` est une décision d'architecture.

Tracking: Linear team **OOM**, project **OOMS**, epic **OOM-6** "POC 1 — Pipeline FINESS
bout-en-bout minimal".

## Commands

Il n'y a pas de `pyproject.toml`/`setup.py` : le code s'exécute directement depuis `src/`, jamais
installé en package. Deux variables d'environnement sont nécessaires pour tout invoquer depuis la
racine du dépôt :

```bash
export PYTHONPATH=src
export PYTHONIOENCODING=utf-8   # sinon UnicodeEncodeError sur les → et accents (console Windows cp1252)
```

**CLI d'acquisition** (`src/cli.py`, cinq commandes) :
```bash
python src/cli.py inspecter <fichier.json.gz> [--source structures|activites] [--echantillon]
python src/cli.py inventaire <structures.json.gz> <activites.json.gz> [--sortie inventaire_codes.csv]
python src/cli.py integrite <structures.json.gz> <activites.json.gz>
python src/cli.py tout <structures.json.gz> <activites.json.gz>
python src/cli.py charger <base.sqlite> <structures.json.gz> [--activites ...] [--creer] [--remplacer]
python src/cli.py restituer <base.sqlite> [--sortie restitution/]   # export CSV + rapport (OOM-14)
```
Rendu du site statique (couche 6, hors CLI) : `python src/export_html.py <base.sqlite> --sortie site/`
(une page par département par défaut, `--decoupage national` pour une liste unique).

**Tests** — pas de pytest, pas d'assert : chaque `tests/test_*.py` est un script autonome qui
s'exécute directement, incrémente un compteur local `ok`/`ko` via une fonction `verifier(...)`, et se
termine par `sys.exit(1 si ko else 0)`. Lancer un seul fichier :
```bash
python tests/test_entrepot.py
```
Lancer toute la suite d'un coup (OOM-101) :
```bash
python tests/tout.py        # -v pour afficher aussi la sortie des fichiers qui passent
```
`tests/tout.py` découvre `tests/test_*.py` dynamiquement (aucune liste en dur), exécute chacun dans un
sous-processus (même interpréteur, `PYTHONPATH=src` et `PYTHONIOENCODING=utf-8` posés pour l'enfant,
cwd = racine), affiche la sortie des échecs puis un résumé (passés, échoués, noms des échecs) et sort
en 1 si un fichier au moins a un code de retour non nul — plantage à l'import compris (D6).
**Option retenue : agrégateur stdlib, plutôt que conversion à pytest.** Motif : il ne touche à aucun
fichier de test (chacun reste exécutable seul, le contrat `verifier`/`sys.exit` est inchangé), il ne
demande rien d'autre que la stdlib — donc tourne aussi là où `requirements-dev.txt` n'est pas
installé (Termux) — et l'isolation par sous-processus empêche un fichier de polluer l'état global
(modules importés, fichiers temporaires) d'un autre. Une conversion pytest reste possible plus tard
sans remettre en cause cet agrégateur. `tests/echantillon/`
contient l'échantillon FINESS réel versionné dont dépendent `test_chargement.py` et consorts ; il doit
rester committé (voir `.gitignore`, exception explicite). `tests/generer.tests.py` fabrique des CSV de
fixture synthétiques dans `tests/data/` pour les tests de la V1 historique (`categories`/`taxonomie`).

**Scripts utilitaires** (`scripts/`) : `telecharger_finess_structures.py` (récupération quotidienne,
tourne aussi via `.github/workflows/`), `recensement.py` (à rejouer sur tout nouveau millésime, avant
toute ingestion — révèle une dérive de schéma), `construire_echantillon.py` (régénère l'échantillon de
test par fermeture transitive à partir de fichiers complets). `mesures/` contient les scripts de
mesure de performance/RSS utilisés pour justifier les décisions de `docs/architecture/06_DECISIONS_SCHEMA.md`
(nature `[mesure]`).

## Architecture

Le détail normatif vit dans `docs/architecture/` (généré/tenu à jour à la main, ne pas dupliquer ici) :
`01_ARCHITECTURE_GLOBALE.md` (vue en couches, décisions D1-D6 — **D7 à D10 ne sont écrits que
dans ce fichier-ci**), `03_SCHEMA_PIVOT.md` (schéma cible), `06_DECISIONS_SCHEMA.md` (**généré par
`schema.py`** depuis les déclarations du code — ne jamais l'éditer à la main). Lire ces trois avant
toute modification structurelle.

**Vue en couches, dépendance strictement descendante** (une couche ne connaît que les couches
inférieures — le domaine ignore FINESS, la restitution ignore le métier, l'acquisition ignore la
taxonomie) :
```
6  RESTITUTION      export_excel · export_tabulaire · export_html · export_geo · rapport
5  ANALYSE          vues · indicateurs · qualite
4  DOMAINE          taxonomie · perimetre · dispositifs · capacites · identite
3  RÉFÉRENTIELS     nomenclatures · territoires
2  ENTREPÔT         schema · entrepot · chargement
1  ACQUISITION      contrat_source · flux_json · sources FINESS (finess_structures, finess_activites)
0  SOCLE            config · journal · controles
    ─────────────────────────────────────────────────
    ORCHESTRATION   cli (pipeline à venir)
```
La couche 6 couvre **toute** forme de restitution, publication web comprise : `export_html` rend les
pages du site depuis l'entrepôt, `export_geo` produit les sorties géographiques (GeoJSON, tuiles).
Une page publiée n'est pas une application cliente posée à côté du pipeline, c'est une sortie de la
couche 6 au même titre qu'un CSV ou un classeur Excel (D7).

État actuel (POC 1, epic OOM-6, **Done** — milestone 100%) : couches 0-3 posées et branchées sur le
CLI, couche 4 pas encore nécessaire pour ce POC (comptage brut, pas de qualification de périmètre),
couche 5 (`indicateurs.py`, OOM-13) et couche 6 (`export_tabulaire.py`/`restituer`, OOM-14) posées et
vérifiées de bout en bout sur l'extrait réel. Extensions "front simple" (epic OOM-22) et
"intégration FINESS-Activités" (epic OOM-26) — **Done** : `export_front.py` (OOM-19, OOM-27) résout
les libellés via `nomenclatures`/`territoires` et expose `etablissements_bruts` et
`activites_par_etablissement` (niveau `ET` uniquement, capacités imbriquées ; `code_nature` exposé
brut — aucune nomenclature versionnée ne couvre encore ce domaine, donc `libelle_nature` vaut
toujours `None`, jamais une valeur inventée). Son écriture JSON (`exporter` → `front/data/`,
gitignored) ne sert plus aucune page depuis la suppression des anciens HTML écrits à la main (OOM-104) ;
elle est conservée en l'état, hors périmètre de la refonte.

**Couche 6 — site par gabarits (épopée « socle de restitution », OOM-100 à OOM-104, OOM-106)** :
`export_html.py` (contrat A : `rendre(entrepot, dossier_gabarits, dossier_sortie,
decoupage="departement") -> dict`) rend `index.html` (accueil avec mention de périmètre, OOM-103, et
un lien vers chaque page départementale), `indicateur.html` (tableau département × catégorie de la
couche 5) et, selon le découpage, une page d'établissements par département (`departement.html`,
défaut, OOM-106) ou une liste nationale unique `liste.html` (`--decoupage national`, conservée pour
la consultation locale : ~55 Mo à l'échelle réelle, elle viole D9). Gabarits dans `front/gabarits/`
(`base.html` + un gabarit par page, blocs `<!-- BLOC nom -->…<!-- FIN nom -->` substitués par
`string.Template`, aucune logique dans le gabarit), puis recopie de `front/actifs/` (feuille de style
commune `ooms.css`, îlot `filtres.js`, OOM-102) dans `site/actifs/`. Tout le contenu utile est dans le
HTML ; le JS n'ajoute que tri et filtres (D10). Un gabarit ou un bloc manquant lève `ErreurExportHtml`
avant toute écriture, chemin dans le message ; un code hors référentiel est rendu `[non résolu]` avec
son code brut, jamais un libellé inventé. La liste des départements est une donnée versionnée
(`referentiels/departements.csv`, COG INSEE, lue par `territoires.charger_departements`), jamais une
liste en dur. Couvert par `tests/test_export_html.py` (OOM-104, OOM-106). Rendu du site :
```bash
python src/export_html.py <base.sqlite> [--sortie site/] [--gabarits front/gabarits/] [--decoupage departement|national]
python -m http.server -d site   # consultation locale ; site/ est gitignored (D8)
```

**Contrat B — chemins du site** (figé par OOM-106, consommé par OOM-107 ; ne bouge plus). Relatifs à
`site/` :

| Chemin | Contenu |
|---|---|
| `index.html`, `indicateur.html` | pages nationales (accueil, indicateur) |
| `departement/<code>.html` | une page par département de `referentiels/departements.csv` (101), **même sans établissement** (page explicite, jamais une absence de fichier) ; `<code>` = code département INSEE **en texte** : `01`…`95`, `2A`, `2B`, `971`…`976` — jamais converti en nombre |
| `departement/indetermine.html` | établissements dont le `cog_commune` est absent, non résolu, ou résolu en un code hors référentiel (`975`, `98x`…) — visibles, jamais écartés |
| `donnees/activites/<code>.json`, `donnees/activites/indetermine.json` | fragments d'activités par département, même `<code>` que la page ; **produits et chargés à la demande par OOM-107**, pas encore écrits (les activités restent embarquées dans les pages départementales) |
| `actifs/` | feuille de style et îlots JS |

Tous les liens entre pages sont **relatifs** (site servi sous le sous-chemin GitHub Pages
`/observatoire-offre-medicosociale-enfance/`) : une page de `departement/` rejoint la racine par `../`.
Aucune page ne charge de JSON national. Chaque page départementale rappelle en une ligne la mention de
périmètre de l'accueil. La somme des établissements des pages départementales est vérifiée égale au
total avant écriture (`ErreurExportHtml` sinon, D6).

**Principes non négociables** (violer l'un d'eux est un bug d'architecture, pas un détail
d'implémentation) :
- **D1** Entrepôt SQLite local entre ingestion et analyse — jamais de chargement intégral en mémoire,
  à aucune étape (contrainte dure : les fichiers source ne tiennent pas en mémoire sur Termux).
- **D2** Modèle pivot indépendant des sources — les sources s'adaptent au pivot, jamais l'inverse.
- **D3** Séparation stricte lu/calculé — les tables sources sont immuables une fois chargées ; les
  tables de classement/périmètre/indicateurs sont intégralement recalculables sans réingestion.
- **D4** Nomenclatures, taxonomie et périmètre sont des données versionnées (`referentiels/`), jamais
  du code Python en dur — c'était l'erreur explicitement citée de la V1 (libellés codés en dur dans un
  module).
- **D5** Provenance sur chaque ligne (`id_lot` : source, millésime, date, empreinte du fichier).
- **D6** Aucun échec silencieux — chaque étape produit des compteurs entrée/sortie et des invariants
  bloquants ; un export ne peut pas sortir d'un entrepôt en échec. Un code de nomenclature inconnu se
  **signale**, ne se tait jamais et ne plante pas non plus.
- **D7** Le front est une restitution, pas une application — toute page publiée est produite par la
  couche 6 depuis l'entrepôt ; aucun HTML écrit à la main hors `front/gabarits/`. Un gabarit ne
  calcule rien : s'il lui faut une valeur, c'est à la couche 5 de la produire.
- **D8** Aucune donnée générée n'est versionnée — `site/`, `front/data/` et les archives de tuiles
  restent hors de git, régénérables par une commande. `tests/echantillon/` demeure l'exception
  explicite qu'il est déjà (voir `.gitignore`).
- **D9** Budget de charge utile par page — aucune page ne dépasse **500 Ko** de données au chargement
  initial ; au-delà, on découpe ou on charge à la demande.
- **D10** Le JavaScript est un îlot, jamais le socle — toute page rend son contenu utile sans JS ; le
  JS ajoute du confort (tri, filtre, carte), il ne conditionne jamais l'accès à l'information.

**Schéma** (`schema.py`, cf. `06_DECISIONS_SCHEMA.md`) : toutes les colonnes sont `TEXT` (la couche 1
émet tout en texte verbatim — des numéros FINESS commencent par `2A`/`2B`) ; `etablissement` porte le
code catégorie, jamais le libellé (le libellé est une jointure) ; `etat_objet`/`date_fermeture` sont
conservés partout — les entités fermées ne sont filtrées qu'à l'analyse, jamais à l'ingestion, ce qui
rend les séries temporelles possibles ; plusieurs rattachements sont polymorphes (`adresse`, `contact`,
`engagement`, `evenement` référencent EJ/ET/GROUPEMENT selon `type_porteur`) et donc **non déclarables
en clé étrangère SQL** — ils sont vérifiés en Python par `controles.VerificateurRelations`
(`cli.py integrite`), pas par SQLite ; aucun index de performance n'est déclaré sans mesure préalable
démontrant un besoin insatisfait.

**Piège de nommage — coordonnées d'`adresse`.** Les quatre colonnes géographiques ne disent pas ce
que leur nom suggère, et les deux `direction_*` sont en plus inversées entre elles :

| Colonne | Contenu réel | Exemple |
|---|---|---|
| `coordonnee_x` | **longitude** WGS84, degrés décimaux | `6.139885` |
| `coordonnee_y` | **latitude** WGS84, degrés décimaux | `46.362063` |
| `direction_longitude` | **X / easting** Lambert 93 (EPSG:2154), mètres | `941342.52` |
| `direction_latitude` | **Y / northing** Lambert 93 (EPSG:2154), mètres | `6589480.53` |

Vérifié par reprojection sur l'échantillon versionné : les `direction_*` sont la projection Lambert 93
exacte des `coordonnee_*`, concordance au centième. Pour toute sortie géographique (GeoJSON, carte) :
longitude = `coordonnee_x`, latitude = `coordonnee_y` — **jamais** les `direction_*`, qui ne sont ni
des degrés ni dans l'ordre que leur nom annonce. Les six colonnes issues de `coordonneesGeographique`
sont nulles ou renseignées ensemble.

**Charnière d'extensibilité** : `identifiant_externe` (entité pivot, système externe, valeur, méthode
d'appariement, confiance) est le point d'accroche unique pour toute source future (INSEE, ROR, CNSA,
IGN, OSM) — le test de validité de l'architecture est qu'ajouter une source ne coûte qu'un connecteur
et éventuellement une nomenclature, rien d'autre ne doit bouger.

## Workflow multi-agents (Orca)

Ce dépôt tourne sous Orca : plusieurs agents Claude peuvent travailler en parallèle, **chacun dans son
propre worktree/branche** (`orca worktree create --base-branch <branche-source>`), jamais dans un
worktree partagé — deux agents écrivant dans le même checkout produisent des collisions de fichiers
(vécu sur ce dépôt : deux branches orphelines `worktree-agent-*` contenaient des ré-implémentations
indépendantes et abandonnées d'OOM-11/OOM-12). Quand une tâche dépend du résultat d'une autre tâche en
cours ailleurs (ex. OOM-14 restitution dépend de l'indicateur d'OOM-13), l'agent aval doit se mettre
d'accord sur un contrat de fonction explicite (nom, signature, forme du retour) et développer contre
un stub local respectant ce contrat, plutôt que de réimplémenter le module amont — puis intégrer pour
de vrai (fetch/merge) une fois que le module amont a atterri sur la branche source.

---

*Ce fichier doit être tenu à jour : le mettre à jour au fil de l'eau (nouvelles commandes, nouvelle
couche branchée, décision d'architecture) plutôt que de le laisser dériver du code réel.*
