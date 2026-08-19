# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Observatoire national libre de l'offre médico-sociale enfance/adolescents, construit à partir de
données publiques (FINESS, à terme INSEE/CNSA/ROR/IGN/OSM). Double finalité : un logiciel
réutilisable et reproductible, et des travaux scientifiques exploitant les données produites.
Stdlib only + `openpyxl` (restitution Excel) — pas d'ORM, pas de framework, pas de service ni d'API :
le contexte d'exécution cible reste un poste local et Termux (téléphone). Python 3.9+ compatible.

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

**Tests** — pas de pytest, pas d'assert : chaque `tests/test_*.py` est un script autonome qui
s'exécute directement, incrémente un compteur local `ok`/`ko` via une fonction `verifier(...)`, et se
termine par `sys.exit(1 si ko else 0)`. Lancer un seul fichier :
```bash
python tests/test_entrepot.py
```
Lancer toute la suite : exécuter chaque `tests/test_*.py` de la même façon (pas de script agrégateur
existant — un agent qui veut un résumé global doit boucler dessus lui-même). `tests/echantillon/`
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
`01_ARCHITECTURE_GLOBALE.md` (vue en couches, décisions D1-D6), `03_SCHEMA_PIVOT.md` (schéma cible),
`06_DECISIONS_SCHEMA.md` (**généré par `schema.py`** depuis les déclarations du code — ne jamais
l'éditer à la main). Lire ces trois avant toute modification structurelle.

**Vue en couches, dépendance strictement descendante** (une couche ne connaît que les couches
inférieures — le domaine ignore FINESS, la restitution ignore le métier, l'acquisition ignore la
taxonomie) :
```
6  RESTITUTION      export_excel · export_tabulaire · export_geo · rapport
5  ANALYSE          vues · indicateurs · qualite
4  DOMAINE          taxonomie · perimetre · dispositifs · capacites · identite
3  RÉFÉRENTIELS     nomenclatures · territoires
2  ENTREPÔT         schema · entrepot · chargement
1  ACQUISITION      contrat_source · flux_json · sources FINESS (finess_structures, finess_activites)
0  SOCLE            config · journal · controles
    ─────────────────────────────────────────────────
    ORCHESTRATION   cli (pipeline à venir)
```
État actuel (POC 1, epic OOM-6, **Done** — milestone 100%) : couches 0-3 posées et branchées sur le
CLI, couche 4 pas encore nécessaire pour ce POC (comptage brut, pas de qualification de périmètre),
couche 5 (`indicateurs.py`, OOM-13) et couche 6 (`export_tabulaire.py`/`restituer`, OOM-14) posées et
vérifiées de bout en bout sur l'extrait réel. Extension "front simple" (epic OOM-22, hors DoD initial
de l'épopée OOM-6) — **Done** : `export_front.py` (OOM-19) résout les libellés via `nomenclatures`/
`territoires` et écrit `etablissements.json`/`indicateur.json`/`meta.json` dans `front/data/`
(gitignored, régénéré à la demande) ; `front/liste.html` (OOM-20, liste filtrable — département,
catégorie, état) et `front/indicateur.html` (OOM-21, tableau croisé département × catégorie triable)
consomment ces fichiers en statique pur (pas de build, pas de serveur autre que
`python -m http.server` local). Les deux ont été vérifiés de bout en bout sur l'échantillon versionné.

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

**Schéma** (`schema.py`, cf. `06_DECISIONS_SCHEMA.md`) : toutes les colonnes sont `TEXT` (la couche 1
émet tout en texte verbatim — des numéros FINESS commencent par `2A`/`2B`) ; `etablissement` porte le
code catégorie, jamais le libellé (le libellé est une jointure) ; `etat_objet`/`date_fermeture` sont
conservés partout — les entités fermées ne sont filtrées qu'à l'analyse, jamais à l'ingestion, ce qui
rend les séries temporelles possibles ; plusieurs rattachements sont polymorphes (`adresse`, `contact`,
`engagement`, `evenement` référencent EJ/ET/GROUPEMENT selon `type_porteur`) et donc **non déclarables
en clé étrangère SQL** — ils sont vérifiés en Python par `controles.VerificateurRelations`
(`cli.py integrite`), pas par SQLite ; aucun index de performance n'est déclaré sans mesure préalable
démontrant un besoin insatisfait.

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
