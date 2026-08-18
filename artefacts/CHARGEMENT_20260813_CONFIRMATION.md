# Chargement de l'extrait Structures réel dans l'entrepôt (OOM-10)

## Commande

```
python src/cli.py charger donnees/observatoire.sqlite donnees/finess-structures/finess-structures-20260813.json.gz --creer --controle strict
```

## Fichier chargé

* `donnees/finess-structures/finess-structures-20260813.json.gz` (50 106 502 octets)
* Empreinte SHA-256 interne : `68187201da33ca3f12cc1ea66a24a525f642ff196b76aaae35d97ae5392f0f5b`
* Lot : `finess_structures:202608:68187201`

## Résultat

* Statut : SUCCES · 35,3 s · 43 kl/s · RSS max 55,7 Mio · lots de 2000
* Violations de clé étrangère : 0
* Contrôles après chargement (contrôle strict) : 5 exécutés, 0 anomalie
* Taille de la base produite : 237,0 Mio

## Lignes par table (1 531 877 au total)

| Table | Lignes |
|---|---|
| evenement | 629 894 |
| adresse | 278 685 |
| contact | 222 543 |
| etablissement | 174 556 |
| entite_juridique | 98 180 |
| engagement | 77 465 |
| relation_etablissement | 47 494 |
| groupement | 1 993 |
| groupement_membre | 766 |
| engagement_autorite | 300 |
| entete | 1 |
| activite / capacite / appareil / zone_intervention* | 0 (Activités hors périmètre POC 1) |

## Vérification indépendante post-chargement

```python
Entrepot('donnees/observatoire.sqlite').verifier_integrite()
# {'integrite': ['ok'], 'integrite_ok': True, 'violations_cles_etrangeres': [], 'duree_s': 2.35}
```

**Conclusion : l'entrepôt SQLite contient l'extrait Structures réel complet, intégrité vérifiée par deux chemins indépendants (contrôles du chargement + `verifier_integrite()` après coup).** Durée et RSS cohérents avec le volume (1,5 M lignes en 35 s, RSS bornée à 55,7 Mio — pas de dérive mémoire proportionnelle au volume, conforme au principe de flux borné du projet).

`donnees/observatoire.sqlite` n'est pas committé (gitignore, résultat local reproductible depuis le dépôt + l'extrait FINESS).

Date : 2026-08-18.
