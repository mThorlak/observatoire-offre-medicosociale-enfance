# Observatoire médico-social enfance/adolescents

Observatoire national **libre** de l'offre médico-sociale enfance/adolescents, construit à
partir de données publiques (FINESS aujourd'hui ; à terme INSEE, CNSA, ROR, IGN, OpenStreetMap).
Double finalité : un logiciel réutilisable et reproductible, et des travaux scientifiques
exploitant les données qu'il produit.

📄 **[Présentation détaillée du projet](https://claude.ai/code/artifact/d876fa49-9132-4945-9c84-26f1672fbaab)**
— objectif, architecture en couches, sources de données, journal d'avancement, prise en main.

## Contraintes

Bibliothèque standard uniquement, plus `openpyxl` pour la restitution Excel — pas d'ORM, pas de
framework, pas de service ni d'API. Le contexte d'exécution cible reste un poste local et Termux
(téléphone). Python 3.9+.

Deux fichiers de dépendances, deux usages :

- [`requirements.txt`](requirements.txt) — **exécution** : `openpyxl` seul. C'est tout ce qu'il
  faut pour faire tourner le pipeline.
- [`requirements-dev.txt`](requirements-dev.txt) — **développement** : `pytest`, `black`. Utile
  pour écrire et tester le code, jamais importé par `src/`, inutile pour lancer le pipeline.

## Démarrer

Lancer le pipeline n'exige **que** les dépendances d'exécution — pas besoin d'installer
`requirements-dev.txt` :

```bash
python -m pip install -r requirements.txt   # openpyxl seul (restitution Excel)
export PYTHONPATH=src
export PYTHONIOENCODING=utf-8   # sinon UnicodeEncodeError sur les → et accents (console Windows cp1252)

python src/cli.py tout structures.json.gz activites.json.gz
python src/cli.py charger base.sqlite structures.json.gz --activites activites.json.gz --creer
python src/cli.py restituer base.sqlite --sortie restitution/
```

Pour développer (tests, formatage) : `python -m pip install -r requirements.txt -r requirements-dev.txt`.

Le détail des cinq commandes CLI, de l'architecture en couches et des principes non négociables
(D1-D6) vit dans [`CLAUDE.md`](CLAUDE.md) et [`docs/architecture/`](docs/architecture/) — c'est la
référence normative, tenue à jour au fil de l'eau.

## État

POC 1 (pipeline FINESS bout-en-bout) et l'acquisition automatisée FINESS-Activités sont **Done**.
Le site statique est une restitution de la couche 6 : `src/export_html.py` rend depuis l'entrepôt,
par les gabarits de [`front/gabarits/`](front/gabarits/), une page d'accueil (avec la mention de
périmètre : comptage brut, qualification enfance/adolescents pas encore appliquée), la liste des
établissements et leurs activités, et le tableau département × catégorie. Tout le contenu est dans le
HTML ; le JavaScript (`front/actifs/filtres.js`) n'ajoute que tri et filtres. Suivi du projet sur
Linear, équipe **OOM**, projet **OOMS**.

```bash
python src/cli.py charger base.sqlite structures.json.gz --activites activites.json.gz --creer
python src/export_html.py base.sqlite --sortie site/
python -m http.server -d site     # puis http://localhost:8000/
```

`site/` n'est jamais versionné (D8) : il se régénère par cette commande. Pour essayer sans extrait
complet, charger l'échantillon versionné de [`tests/echantillon/`](tests/echantillon/).

## Sources de données

Recensées et documentées dans [`docs/08_SOURCES_DONNEES.md`](docs/08_SOURCES_DONNEES.md) : rôle,
licence, fréquence de mise à jour, niveau d'intégration et procédure d'acquisition automatisée
pour chacune.
