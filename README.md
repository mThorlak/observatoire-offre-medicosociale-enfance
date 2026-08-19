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

## Démarrer

```bash
export PYTHONPATH=src
export PYTHONIOENCODING=utf-8   # sinon UnicodeEncodeError sur les → et accents (console Windows cp1252)

python src/cli.py tout structures.json.gz activites.json.gz
python src/cli.py charger base.sqlite structures.json.gz --activites activites.json.gz --creer
python src/cli.py restituer base.sqlite --sortie restitution/
```

Le détail des cinq commandes CLI, de l'architecture en couches et des principes non négociables
(D1-D6) vit dans [`CLAUDE.md`](CLAUDE.md) et [`docs/architecture/`](docs/architecture/) — c'est la
référence normative, tenue à jour au fil de l'eau.

## État

POC 1 (pipeline FINESS bout-en-bout) et l'acquisition automatisée FINESS-Activités sont **Done**.
Un front simple, statique pur (`front/liste.html`, `front/indicateur.html`), consulte les données
produites sans build ni serveur autre que `python -m http.server`. Suivi du projet sur Linear,
équipe **OOM**, projet **OOMS**.

## Sources de données

Recensées et documentées dans [`docs/08_SOURCES_DONNEES.md`](docs/08_SOURCES_DONNEES.md) : rôle,
licence, fréquence de mise à jour, niveau d'intégration et procédure d'acquisition automatisée
pour chacune.
