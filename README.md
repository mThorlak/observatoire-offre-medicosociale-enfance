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

**Essayer le front sans rien installer** (aperçu figé sur l'échantillon FINESS versionné,
millésime 202607 — pas des données de production) :

- 🗂️ **[Tester le front — liste des établissements](https://claude.ai/code/artifact/ee0f46dc-70b0-4582-ba27-0cc1bcc76839)**
  (OOM-20/28) : recherche, filtres département/catégorie/état, panneau d'activités au clic.
- 📊 **[Front d'analyse — indicateur département × catégorie](https://claude.ai/code/artifact/fe8004fc-823d-4682-afdb-b34d57d345a2)**
  (OOM-21) : tableau croisé triable, mêmes chiffres que l'export CSV d'OOM-14.

Contre un extrait réel : `python src/export_front.py <base.sqlite> --sortie front/data` puis
`python -m http.server` depuis `front/`.

## Sources de données

Recensées et documentées dans [`docs/08_SOURCES_DONNEES.md`](docs/08_SOURCES_DONNEES.md) : rôle,
licence, fréquence de mise à jour, niveau d'intégration et procédure d'acquisition automatisée
pour chacune.
