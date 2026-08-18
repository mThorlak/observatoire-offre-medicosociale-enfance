# Recensement FINESS-Structures — confirmation (OOM-8)

## Extrait recensé

* Fichier : `donnees/finess-structures/finess-structures-20260813.json.gz`
* Source : `finess-structures-journalier-20260813.json.gz`, obtenu via le run #1 du workflow `finess-structures-quotidien.yml` (OOM-16/17)
* Taille : 50 106 502 octets
* SHA-1 publié par data.gouv.fr : `62bb7df1b7d7b619b00a57553c2c052619a206c6` — vérifié conforme
* Empreinte SHA-256 interne (`contrat_source.empreinte_fichier`) : `68187201da33ca3f12cc1ea66a24a525f642ff196b76aaae35d97ae5392f0f5b`
* Recensement produit : `artefacts/RECENS_STRUCTURES_20260813_courant.txt` (34 s, 183 chemins distincts)

## Comparaison à l'artefact versionné

Référence : `artefacts/02_RECENS_STRUCTURES.txt` (millésime 2026-07, root `{gco: 1856, gcc: 135, pmej: 98168}`).

* **Chemins JSON** : 183 chemins dans les deux recensements, ensembles identiques (aucun chemin apparu ni disparu).
* **Types par chemin** : aucun changement de jeu de types sur les 183 chemins communs (comparaison faite sur la colonne TYPES, hors comptages).
* **Cardinalités** : croissance homogène et attendue (+0,1 à +0,3 % selon les tables — ex. `gco` 1856→1858, `pmej` 98168→98180), cohérente avec un mois d'écart entre les deux millésimes.

**Conclusion : aucune dérive de schéma détectée.** Le chargement (OOM-10) peut procéder sur cet extrait sans mise à jour préalable de `docs/architecture/03_SCHEMA_PIVOT.md`.

## Correctif appliqué en cours de route

Les artefacts versionnés `artefacts/02_RECENS_STRUCTURES.txt` et `artefacts/03_RECENS_ACTIVITES.txt` avaient un **contenu inversé par rapport à leur nom** : le fichier nommé "STRUCTURES" contenait en réalité le recensement d'Activités (root `pmej` seul, 45 656 occurrences) et inversement. Confirmé par l'en-tête interne de chaque fichier (`# Recensement : .../finess-activites-...` dans le fichier nommé STRUCTURES) et par la comparaison des clés racines avec le recensement réel produit ici. Corrigé par renommage croisé des deux fichiers (contenu inchangé, uniquement les noms de fichiers échangés) — sans ce correctif, toute comparaison future contre "02_RECENS_STRUCTURES.txt" aurait en fait comparé contre un recensement d'Activités.

Date : 2026-08-18.
