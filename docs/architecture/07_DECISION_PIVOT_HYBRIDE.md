# 07 — Décision : miroir par source + pivot minimal projeté

| | |
|---|---|
| Statut | **Adoptée** — 2026-08-22 |
| Ticket | OOM-46 (épopée OOM-30, intégration multi-sources) |
| Porte sur | D2 « modèle pivot indépendant des sources » |
| Remplace | Rien. Précise D2 et en corrige la lecture littérale |
| Décide pour | OOM-31 à OOM-37 (socle et connecteurs), OOM-39 (entrepôt multi-fichiers) |

## 1. Le constat qui a ouvert la question

D2 énonce que « les sources s'adaptent au pivot, jamais l'inverse ». Le code fait
l'inverse, et le documente — `src/schema.py`, l. 3-7 :

> *Définition déclarative du schéma SQLite, dérivée des types d'enregistrements de la
> couche 1. Les colonnes ne sont pas recopiées : elles proviennent de
> `finess_commun.TOUS_LES_TYPES`. Le jour où le contrat de la couche 1 change, le schéma
> suit sans intervention.*

Les 16 tables de l'entrepôt sont les types FINESS, avec les colonnes FINESS et le
vocabulaire FINESS. L'entrepôt est un miroir relationnel de FINESS.

Le document `03_SCHEMA_PIVOT.md` ne dit d'ailleurs pas autre chose une fois ouvert :
il se présente comme le « contrat d'interface entre la couche 1 (acquisition) et les
couches suivantes », énumérant « la totalité des enregistrements produits par la couche
d'acquisition ». C'est un contrat de source. Seul son nom de fichier promettait un pivot.

Autrement dit : le pivot n'a jamais existé. Ce n'était pas visible à une source.

## 2. Ce que la mesure a montré

### 2.1 La surface réellement consommée est de 10 %

L'entrepôt chargé (millésime 202608, cf.
`artefacts/CHARGEMENT_20260822_STRUCTURES_ACTIVITES.md`) compte **209 colonnes sur
16 tables**. L'ensemble des couches 5 et 6 — `indicateurs.py`, `export_front.py`,
`export_tabulaire.py` — en lit **22, réparties sur 4 tables** :

| Table | Lues / total | Colonnes lues |
|---|---|---|
| `etablissement` | 6 / 20 | `num_finess_et`, `nom_court`, `nom_long`, `code_categorie`, `etat_objet`, `ege_id` |
| `adresse` | 6 / 27 | `cog_commune`, `code_postal`, + `type_porteur`, `id_porteur`, `code_usage_adresse`, `rang` (jointure) |
| `activite` | 6 / 44 | `activite_ae_id`, `num_finess_et`, `code_nature`, `code_type_activite_smsse`, `etat_objet`, `niveau` |
| `capacite` | 4 / 15 | `activite_ae_id`, `nombre`, `code_unite_mesure`, `code_statut_capacite` |

Les deux plus grosses tables — `evenement` (1 968 572 lignes) et
`zone_intervention_commune` (1 234 675 lignes), soit l'essentiel des 665,7 Mio de la
base — ne sont lues par aucun consommateur.

### 2.2 La duplication de jointure est déjà là

Ce bloc figure **à l'identique** dans `indicateurs.py:146-155` et
`export_front.py:118-127` :

```sql
LEFT JOIN adresse a
    ON a.type_porteur = 'ET' AND a.id_porteur = e.ege_id
   AND a.code_usage_adresse = ?
   AND a.rang = (SELECT MIN(a2.rang) FROM adresse a2
                 WHERE a2.type_porteur = 'ET' AND a2.id_porteur = e.ege_id
                   AND a2.code_usage_adresse = ?)
```

Neuf lignes recopiées pour répondre à « quelle est l'adresse de cet établissement ».
Le rattachement d'`adresse` est polymorphe, donc non déclarable en clé étrangère : chaque
consommateur re-dérive la résolution. À deux consommateurs et une source, la duplication
existe déjà. Six sources la multiplieraient.

### 2.3 L'intégrité référentielle change de nature dès la deuxième source

Le chargement conjoint du 2026-08-22 a produit 6 violations de clé étrangère sur 3 lignes
d'`activite`, causées par un écart d'un jour entre les deux extraits (Structures 18/08,
Activités 19/08) : trois établissements créés dans l'intervalle, `ege_id` 174589-174591,
immédiatement après le maximum 174588 présent dans `etablissement`.

Le fait structurant n'est pas l'anomalie — trois lignes — mais ce qu'elle révèle : **à une
source, l'intégrité référentielle est une propriété du fichier ; à deux sources acquises
indépendamment, elle devient une propriété de l'appariement.** Un schéma dérivé d'une
source ne sait pas exprimer cette contrainte-là, puisqu'il suppose la cohérence acquise.

## 3. La décision

**Le miroir par source est conservé et assumé. Un pivot minimal est posé au-dessus, en
tant que donnée calculée.**

```
MIROIR (lu · verbatim · immuable)        PIVOT (calculé · recalculable)

  finess.etablissement    ──┐
  finess.adresse          ──┼──────────►   entite_localisee
  finess.activite         ──┤                num_finess_et, nom,
  finess.capacite         ──┘                code_categorie, etat_objet,
  insee.unite_legale      ──►                cog_commune, code_postal
  ign.commune             ──►
                                           capacite_pivot
                                             entite, nature, nombre,
                                             code_unite_mesure, statut

                                           identifiant_externe
                                             entite ─► systeme, valeur,
                                             methode, confiance
```

### 3.1 Ce que cela signifie couche par couche

- **Couches 1 et 2, inchangées.** Chaque source garde ses tables, son vocabulaire et sa
  fidélité verbatim. `schema.py` continue de dériver le miroir FINESS de
  `finess_commun` ; les connecteurs futurs dérivent le leur de leur propre contrat. Aucun
  connecteur ne traduit quoi que ce soit à l'ingestion.
- **Nouveau : les tables pivot**, alimentées par projection depuis le miroir. Elles sont
  du **calculé** au sens de D3 : intégralement reconstructibles sans réingestion,
  jamais écrites par un connecteur.
- **Couches 5 et 6** ne lisent plus que le pivot. La jointure polymorphe est résolue une
  fois, à la projection, au lieu d'être recopiée par consommateur.
- **`identifiant_externe`** (OOM-31) s'accroche à `entite_localisee`, qui lui fournit
  enfin l'entité pivot stable que sa définition suppose.

### 3.2 Pourquoi pas les deux autres options

**Pivot complet** — traduire les 209 colonnes dont ~90 % ne sont lues par personne, et
maintenir cette traduction pour chacune des six sources à venir. Le coût est réel et
immédiat ; le bénéfice ne porte que sur la fraction déjà couverte par l'hybride.

**Miroir seul, pivot en vues** — laisse la duplication de §2.2 croître avec les sources
et les consommateurs, et laisse `identifiant_externe` sans point d'accroche. C'est l'état
actuel prolongé, dont §2.3 montre qu'il cesse d'être tenable à la deuxième source.

## 4. Lecture corrigée de D2

D2 reste valide, mais sa lecture littérale — « le schéma d'entrepôt ne décalque aucune
source » — est abandonnée au profit de : **aucune couche au-dessus du pivot ne connaît de
vocabulaire de source.** Le décalque existe et est assumé, confiné à la couche 2 et
séparé du pivot par la frontière lu/calculé de D3.

Le test de validité de l'architecture est inchangé et devient vérifiable : ajouter une
source coûte un connecteur, ses tables miroir, et une règle de projection vers le pivot.
Rien d'autre ne bouge — en particulier, aucune couche 5 ou 6 n'est touchée.

## 5. Contraintes que la mise en œuvre doit respecter

- **Fidélité verbatim de la couche 2.** Aucune normalisation à l'ingestion. La projection
  vers le pivot est le seul endroit où une valeur peut être transformée, et elle est
  recalculable.
- **Aucune déclaration sans justification.** Chaque table et chaque colonne du pivot porte
  une justification `ARTEFACT` / `MESURE` / `BESOIN`, faute de quoi la construction du
  schéma échoue. La règle vaut pour le pivot comme pour le miroir.
- **`06_DECISIONS_SCHEMA.md` reste engendré depuis le code**, jamais rédigé à la main.
- **D5.** Une ligne de pivot porte la provenance des lignes miroir dont elle est projetée.
  Le chargement du 2026-08-22 a montré que l'`id_lot` au millésime (`202608`) ne
  distingue pas deux extraits à un jour d'écart : la granularité est à revoir dans le même
  mouvement.
- **D6.** Une projection qui ne peut pas résoudre un rattachement se signale ; elle ne
  produit pas une ligne pivot silencieusement incomplète.

## 6. Conséquences documentaires

- `01_ARCHITECTURE_GLOBALE.md` : D2 renvoie désormais à ce document.
- `03_SCHEMA_PIVOT.md` : le titre est trompeur, le contenu ne l'est pas. Ce fichier
  documente le contrat de la source FINESS et devrait être renommé en conséquence lorsque
  le pivot réel existera — sans quoi deux documents porteront le mot « pivot » pour deux
  objets différents.
- OOM-31 (`identifiant_externe`) est à réévaluer : sa cible d'accroche est désormais
  `entite_localisee`, et non une ligne FINESS.

## 7. Hors périmètre de cette décision

L'implémentation du pivot — définition exacte des colonnes, module de projection,
migration des couches 5 et 6 — fait l'objet de tickets distincts. Ce document produit une
décision, pas du code.
