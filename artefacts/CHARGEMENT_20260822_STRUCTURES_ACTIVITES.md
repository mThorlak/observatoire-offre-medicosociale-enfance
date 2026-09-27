# Premier chargement conjoint Structures + Activités (OOM-44)

Date : 2026-08-22.

## Commande

```
python src/cli.py charger donnees/observatoire.sqlite \
    donnees/finess-structures/finess-structures-20260818.json.gz \
    --activites donnees/finess-activites/finess-activites-20260819.json.gz \
    --creer --controle strict
```

## Fichiers chargés

Récupérés depuis les artefacts GitHub Actions encore vivants (runs 32183858720 et
32286656183), empreintes SHA-1 vérifiées contre le `.metadata.json` produit à
l'acquisition **avant** tout chargement :

| Fichier | Octets | SHA-1 source | Vérifié |
|---|---|---|---|
| `finess-structures-20260818.json.gz` | 50 123 194 | `08e8d642…0e7fb` | oui |
| `finess-activites-20260819.json.gz` | 58 040 380 | `7dead6a6…1b750` | oui |

**Les deux extraits ne sont pas du même jour** — ce point est la cause du résultat
ci-dessous, et non un détail de circonstance.

## Résultat

| Passe | Statut | Durée | Débit | RSS max | Lignes |
|---|---|---|---|---|---|
| Structures | **SUCCÈS** | 31,0 s | 49 kl/s | 53,0 Mio | 1 532 307 |
| Activités | **ÉCHEC** | 72,7 s | 51 kl/s | 90,6 Mio | 3 724 027 |

Base finale : **665,7 Mio**, 5 256 334 lignes, 16 tables peuplées, schéma conforme.
Millésime `202608`, sources `finess_structures` + `finess_activites`.

RSS bornée à 90,6 Mio pour 3,7 M lignes insérées : conforme au principe de flux borné
(D1), aucune dérive proportionnelle au volume.

### Lignes par table

| Table | Lignes |
|---|---|
| evenement | 1 968 572 |
| zone_intervention_commune | 1 234 675 |
| activite | 587 379 |
| capacite | 537 687 |
| adresse | 278 724 |
| contact | 222 549 |
| etablissement | 174 564 |
| entite_juridique | 98 181 |
| engagement | 78 184 |
| relation_etablissement | 47 506 |
| appareil | 16 160 |
| zone_intervention | 8 356 |
| groupement | 1 993 |
| engagement_autorite | 1 036 |
| groupement_membre | 766 |
| entete | 2 |

## Anomalie : 6 violations de clé étrangère

Trois lignes de `activite`, chacune violant deux clés étrangères
(`ege_id` et `num_finess_et`, toutes deux vers `etablissement`) :

| `activite_ae_id` | `num_finess_et` | `ege_id` | `code_nature` | `niveau` |
|---|---|---|---|---|
| 889098 | 550008684 | 174590 | ASMR | ET |
| 889090 | 770817211 | 174589 | AER | ET |
| 889094 | 920816915 | 174591 | AER | ET |

### Diagnostic — décalage de millésime, pas défaut de schéma

Le `ege_id` maximal présent dans `etablissement` est **174588**. Les trois orphelins
sont **174589, 174590 et 174591** : les trois identifiants immédiatement suivants. Les
derniers établissements de l'extrait Structures ont une date d'ouverture au 2026-08-17.

Trois établissements ont donc été créés dans FINESS entre la publication de l'extrait
Structures (18/08, 02:17 UTC) et celle de l'extrait Activités (19/08, 02:14 UTC). Leurs
activités figurent dans le second extrait ; eux-mêmes n'existent pas encore dans le
premier.

Aucune des trois lignes n'est malformée, et la déclaration de clé étrangère est correcte.
Ce qui est faux, c'est de charger comme un millésime cohérent deux extraits acquis à des
dates différentes — et l'`id_lot` porte `202608` pour les deux, ce qui masque l'écart.

### Confirmation par un second chemin indépendant

`cli.py integrite` (66,5 s, RSS 74,3 Mio, 6 788 641 lignes sur trois passes) constate
**exactement les mêmes 3 lignes et 6 références orphelines**, et zéro anomalie sur les
douze autres relations vérifiées :

```
activite.ege_id        -> etablissement.ege_id           293 688 vérifiées ·  3 orphelines
activite.num_finess_et -> etablissement.num_finess_et    293 688 vérifiées ·  3 orphelines
activite.num_finess_ej -> entite_juridique.num_finess_ej 587 379 vérifiées ·  0
activite.pm_smsse_id   -> entite_juridique.pm_smsse_id   587 379 vérifiées ·  0
capacite.activite_ae_id            -> activite            537 687 vérifiées ·  0
zone_intervention_commune.…        -> zone_intervention  1 234 675 vérifiées ·  0
appareil / zone_intervention / relation_etablissement / groupement_membre / engagement_autorite : 0
```

Les 293 691 références « non renseignées » sur les deux relations vers `etablissement`
correspondent aux activités de niveau `EJ`, qui ne portent pas de `num_finess_et` — la
répartition ET/EJ des 587 379 activités est donc quasi exactement 50/50.

Le contrôle des relations polymorphes, jamais exercé à cette échelle jusqu'ici, passe
sans anomalie, y compris pour `type_porteur = 'ACTIVITE_EJ'`.

## Écart aux cardinalités déclarées dans `schema.py`

Les contraintes Activités de `schema.py` ont été déclarées sur des cardinalités mesurées
par `recensement.py` sur un millésime antérieur. Confrontation aux lignes réellement
insérées :

| Table | Déclaré | Inséré | Écart |
|---|---|---|---|
| activite | 585 746 | 587 379 | +1 633 |
| capacite | 537 233 | 537 687 | +454 |
| appareil | 16 096 | 16 160 | +64 |
| zone_intervention | 8 336 | 8 356 | +20 |

Tous les écarts sont positifs et de faible amplitude (+0,1 % à +0,4 %) : croissance
normale du référentiel entre deux millésimes. **Aucune contrainte d'unicité n'a été mise
en défaut** — les clés primaires `activite_ae_id`, `id_capacite`,
`(activite_ae_id, rang)` et `zone_intervention_id` tiennent toutes à l'échelle réelle,
ce qui était la question ouverte que ce chargement devait trancher.

## Conclusion

La moitié Activités du schéma est validée contre des données réelles complètes : toutes
ses clés primaires et ses clés étrangères internes tiennent, sur 3,7 M lignes.

Le seul échec provient de l'appariement inter-sources, et il est entièrement expliqué par
l'écart d'un jour entre les deux extraits. Conformément à D6, il est constaté et écrit
plutôt que contourné : **la contrainte n'a pas été assouplie**.

### Ce que ce chargement ouvre

1. **Contrainte d'acquisition** : Structures et Activités doivent être appariés par date
   d'extraction, ou le pipeline doit assumer explicitement une tolérance au décalage
   référentiel. À porter dans OOM-45 (reconstruction reproductible) et dans les workflows.
2. **Le millésime `202608` est trop grossier** pour distinguer deux extraits à un jour
   d'écart, alors que D5 exige une provenance exacte par ligne. La granularité de
   l'`id_lot` est à revoir.
3. **Élément pour OOM-46** : à une source, l'intégrité référentielle est une propriété du
   fichier. À deux sources acquises indépendamment, elle devient une propriété de
   l'appariement — et ce cas s'est produit dès la deuxième source, sur trois lignes, un
   jour d'écart. C'est un argument mesuré pour la décision pivot, pas une conjecture.
