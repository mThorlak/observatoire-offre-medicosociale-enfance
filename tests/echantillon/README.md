# Échantillon de test versionné

Ces deux fichiers sont un sous-ensemble strict et référentiellement clos
d'extraits FINESS réels — voir l'en-tête de `scripts/construire_echantillon.py`
pour le principe (fermeture transitive à partir de graines choisies pour
couvrir des cas limites connus).

## Provenance (régénéré le 18/08/2026)

* `finess-structures-mensuel-202607-echantillon_json.gz` — construit à partir de
  `finess-structures-journalier-20260813.json.gz` (empreinte SHA-1 publiée :
  `62bb7df1b7d7b619b00a57553c2c052619a206c6`, obtenu via le run réel du
  workflow OOM-16/17).
* `finess-activites-mensuel-202607-echantillon_json.gz` — construit à partir de
  `finess-activites-journalier-20260818.json.gz` (empreinte SHA-1 publiée :
  `67c0c077958839d3e61363d8ece554177059a217`, téléchargement ponctuel manuel —
  aucun workflow automatisé n'existe pour Activités, hors périmètre du POC 1).

Le nom des fichiers (`mensuel-202607`) est un **label hérité**, conservé tel
quel car `tests/test_chargement.py` le recherche littéralement — il ne
reflète pas le millésime réel des sources ci-dessus.

## Régénération

À rejouer si `scripts/recensement.py` (OOM-8) révèle une dérive de schéma sur
un nouveau millésime, ou si le comportement testé par `test_chargement.py`
doit être exercé sur un cas non couvert par les graines actuelles :

```
python scripts/construire_echantillon.py <structures.json.gz> <activites.json.gz> <dossier_sortie>
```

Puis déplacer les deux fichiers produits ici. **Attention** : si le résultat
change de volumétrie, les comptes exacts codés en dur dans
`tests/test_chargement.py` (recherchez `sum(...) ==`) doivent être mis à jour
en conséquence — ils ne se recalculent pas seuls.
