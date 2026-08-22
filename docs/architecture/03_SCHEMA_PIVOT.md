# SCHEMA_PIVOT.md

**Contrat d'interface entre la couche 1 (acquisition) et les couches suivantes.**

| | |
|---|---|
| Version du contrat | 1.3 |
| Millésime de référence | FINESS 202607 (`schemaVersion` = `v1.0.0`) |
| Sources couvertes | `finess-structures-mensuel`, `finess-activites-mensuel` |
| Révision 1.1 | Effectifs de codes mesurés par le connecteur structures (E3) ; correction 301 → 300 catégories |
| Révision 1.2 | Jeux de clés de `caracteristiquesSpecifiques` établis par nature (E4) ; effectifs de codes du fichier activités |
| Révision 1.3 | Registre des codes observés (E5) : 41 domaines, 7 053 couples ; quatre constats de structure acquittés |
| Établi à partir de | Recensement exhaustif des deux fichiers complets : 183 et 216 chemins JSON distincts, 20 737 253 et 38 098 626 occurrences de clés |

Ce document énumère la totalité des enregistrements produits par la couche
d'acquisition et la totalité de leurs champs. Il est le seul contrat que les
couches supérieures ont le droit de connaître. Aucun module au-dessus de la
couche 1 ne doit lire un chemin JSON.

> **Avertissement sur le nom de ce fichier (2026-08-22, OOM-46).** Malgré son
> nom, ce document ne décrit **pas** un modèle pivot : il décrit le contrat de la
> source FINESS, dont la couche 2 est le miroir. Le pivot — minimal, projeté
> depuis le miroir, indépendant du vocabulaire des sources — est décidé par
> `07_DECISION_PIVOT_HYBRIDE.md` et reste à implémenter. Ce fichier sera renommé
> lorsque le pivot réel existera, pour que deux documents ne portent pas le mot
> « pivot » en désignant deux objets différents.

---

## 1. Conventions

**Nommage.** `snake_case` français. Préfixe `code_` pour toute valeur codifiée
renvoyant à une nomenclature externe ; `num_finess_` pour les numéros FINESS ;
`date_` pour les dates ; suffixe `_id` pour les identifiants techniques FINESS.

**Types.** `TEXTE`, `DATE` (AAAA-MM-JJ), `HORODATAGE` (ISO 8601 avec fuseau),
`ENTIER_TEXTE`. Ce dernier signale un champ numérique par nature mais **émis
verbatim en texte** : l'acquisition ne convertit ni ne normalise rien, la
conversion appartient à l'entrepôt. Aucun champ n'est rogné, complété ou mis en
forme.

**Nuls.** L'absence de valeur est émise comme nul, jamais comme chaîne vide. La
colonne « Nul » indique le nombre de valeurs nulles mesurées sur 202607 ; la
mention **jamais** signale un champ toujours renseigné, sur lequel un contrôle
bloquant peut donc s'appuyer.

**Ordre des champs figé.** L'ordre de déclaration ci-dessous est l'ordre
d'émission. Il ne change pas sans changement de version du contrat.

**Provenance.** Chaque enregistrement porte `id_lot`. En mode diagnostic
uniquement, une colonne supplémentaire `chemin_source` (par exemple
`pmej[1234].ege[3].activitesExercees[2]`) permet de remonter à la position
exacte dans le JSON. Elle est désactivée par défaut : environ 30 octets par
ligne sur 5,2 millions de lignes.

**Aucune donnée calculée.** Pas de libellé résolu, pas de département déduit,
pas d'agrégat, pas de filtrage. L'acquisition transporte, elle n'interprète pas.

---

## 2. Enregistrement `entete`

Un par fichier. Ouvre le flux et définit le lot auquel toutes les lignes
suivantes se rattachent.

| Champ | Type | Nul | Source | Note |
|---|---|---|---|---|
| `id_lot` | TEXTE | jamais | calculé | `{source}:{millesime}:{empreinte[0:8]}` — déterministe, donc rejouable |
| `source` | TEXTE | jamais | fixe | `finess_structures` ou `finess_activites` |
| `millesime` | TEXTE | jamais | nom du fichier | `202607` |
| `schema_version` | TEXTE | jamais | `schemaVersion` | `v1.0.0` |
| `genere_le` | HORODATAGE | jamais | `generatedAt` | |
| `nom_fichier` | TEXTE | jamais | système | |
| `empreinte` | TEXTE | jamais | calculé | SHA-256 du fichier compressé |
| `octets` | ENTIER_TEXTE | jamais | système | |

---

## 3. Enregistrements issus de `finess-structures`

### 3.1 `entite_juridique` — 98 168 lignes

Source : `pmej[]`.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `num_finess_ej` | TEXTE | jamais | `informationsGeneralesPMEJ.numFinessPm` | 9 caractères, unique |
| `pm_smsse_id` | TEXTE | jamais | `informationsGeneralesPMEJ.pmSmsseId` | Identifiant technique, clé des groupements |
| `denomination` | TEXTE | jamais | `informationsGeneralesPMEJ.denominationPm` | ≤ 38 caractères |
| `denomination_longue` | TEXTE | jamais | `informationsGeneralesPMEJ.denominationLonguePmSmsse` | ≤ 98 caractères |
| `siren` | TEXTE | 16 375 | `informationsGeneralesPMEJ.siren` | |
| `code_ape` | TEXTE | 16 375 | `informationsGeneralesPMEJ.codeApe` | **Seul niveau où l'APE existe désormais** |
| `code_statut_juridique` | TEXTE | jamais | `informationsGeneralesPMEJ.statutJuridique` | |
| `code_type_personne_morale` | TEXTE | jamais | `informationsGeneralesPMEJ.typePersonneMorale` | |
| `code_fonction_publique` | TEXTE | 82 602 | `informationsGeneralesPMEJ.fonctionPublique` | |
| `code_type_groupe_gco` | TEXTE | 96 312 | `informationsGeneralesPMEJ.typeGroupeGco` | |
| `complement_adresse` | TEXTE | 92 045 | `informationsGeneralesPMEJ.complementAdressePmSmsse` | |
| `code_categorie` | TEXTE | **98 168** | `informationsGeneralesPMEJ.categorieentiteGeographiqueExercice` | Toujours nul. Conservé pour fidélité au schéma source |
| `date_creation` | DATE | jamais | `informationsGeneralesPMEJ.dateCreation` | |
| `date_fermeture` | DATE | 54 164 | `informationsGeneralesPMEJ.dateFermeture` | |
| `etat_objet` | TEXTE | jamais | `etatObjet` | `A` 56 219 / `I` 41 949 |
| `date_derniere_maj` | HORODATAGE | jamais | `dateDerniereMaj` | |
| `id_lot` | TEXTE | jamais | — | |

### 3.2 `etablissement` — 174 508 lignes

Source : `pmej[].ege[]`. `num_finess_et` est unique sur l'ensemble du fichier
(vérifié : aucun doublon).

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `num_finess_et` | TEXTE | jamais | `informationsGeneralesEGE.numFinessEge` | 9 caractères, unique |
| `ege_id` | TEXTE | jamais | `informationsGeneralesEGE.egeId` | Clé de jointure avec le fichier activités |
| `num_finess_ej` | TEXTE | jamais | parent | Porté par l'imbrication |
| `pm_smsse_id` | TEXTE | jamais | parent | |
| `nom_court` | TEXTE | jamais | `informationsGeneralesEGE.nomEgeCourt` | ≤ 38 caractères |
| `nom_long` | TEXTE | jamais | `informationsGeneralesEGE.nomEgeLong` | ≤ 80 caractères |
| `complement_denomination` | TEXTE | 157 985 | `informationsGeneralesEGE.complementDenominationEg` | |
| `code_categorie` | TEXTE | 5 | `categorieentiteGeographiqueExercice` | 300 codes distincts, 5 établissements sans catégorie |
| `siret` | TEXTE | 35 294 | `informationsGeneralesEGE.siret` | |
| `code_espic` | TEXTE | 153 198 | `informationsGeneralesEGE.espic[0]` | Liste de cardinalité 0 ou 1 sur la totalité du fichier ; aplatie en colonne, avec contrôle bloquant si une cardinalité supérieure apparaît |
| `numero_uai` | TEXTE | 169 948 | `informationsGeneralesEGE.numeroEducationNationale` | |
| `numero_reference_externe` | TEXTE | 151 208 | `informationsGeneralesEGE.numeroReferenceExterne` | |
| `code_mode_fixation_tarifaire` | TEXTE | 5 | `modefixationtarifaire` | Successeur du `code_mft` du CSV |
| `code_type_budget` | TEXTE | 5 | `typeBudget[0]` | Même règle d'aplatissement que `code_espic` |
| `date_ouverture` | DATE | 47 | `informationsGeneralesEGE.dateOuverture` | |
| `date_premiere_autorisation` | DATE | 1 291 | `informationsGeneralesEGE.datePremiereAutorisation` | |
| `date_fermeture` | DATE | 104 822 | `informationsGeneralesEGE.dateFermeture` | |
| `etat_objet` | TEXTE | jamais | `etatObjet` | `A` 104 699 / `I` 69 809 |
| `date_derniere_maj` | HORODATAGE | jamais | `dateDerniereMaj` | |
| `id_lot` | TEXTE | jamais | — | |

### 3.3 `adresse` — 278 615 lignes

Sources : `pmej[].adresse[]` (98 168, cardinalité toujours 1) et
`pmej[].ege[].adresse[]` (180 447, cardinalité 1 à 150).

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `type_porteur` | TEXTE | jamais | — | `EJ` ou `ET` |
| `id_porteur` | TEXTE | jamais | — | `pmSmsseId` ou `egeId` |
| `num_finess_porteur` | TEXTE | jamais | — | Évite une jointure pour les usages courants |
| `rang` | ENTIER_TEXTE | jamais | — | Position dans le tableau `adresse[]` |
| `code_usage_adresse` | TEXTE | jamais | `usageAdresse` | `03` principale, `04`, `06` secondaires |
| `numero_voie` | TEXTE | 63 677 | `numeroVoie` | |
| `code_type_voie` | TEXTE | 71 928 | `typeVoie` | Codifié |
| `libelle_voie` | TEXTE | 19 081 | `libelleVoie` | **Un des deux seuls libellés du jeu de données** |
| `complement_voie` | TEXTE | 270 382 | `complementVoie` | |
| `complement_point_geographique` | TEXTE | 237 642 | `complementPointGeographique` | |
| `lieu_dit` | TEXTE | 252 742 | `lieuDit` | |
| `code_postal` | TEXTE | jamais | `codePostal` | |
| `cog_commune` | TEXTE | jamais | `cogCommune` | Code INSEE 5 caractères. **Seule source territoriale** : le département doit en être dérivé |
| `ligne_acheminement` | TEXTE | 3 781 | `ligneAcheminement` | |
| `ligne_une` … `ligne_six` | TEXTE | variable | `ligneUne` … `ligneSix` | Six colonnes. `ligneTrois` toujours nulle ; `ligneDeux` et `ligneCinq` quasi toujours nulles |
| `coordonnee_x` | TEXTE | 91 682 | `coordonneesGeographique.coordonneeX` | |
| `coordonnee_y` | TEXTE | 91 682 | `coordonneesGeographique.coordonneeY` | |
| `direction_latitude` | TEXTE | 91 682 | `coordonneesGeographique.directionLatitude` | |
| `direction_longitude` | TEXTE | 91 682 | `coordonneesGeographique.directionLongitude` | |
| `cle_interop_ban` | TEXTE | 91 682 | `coordonneesGeographique.cleInInteropBAN` | Point d'accroche IGN / BAN |
| `score_ban` | TEXTE | 91 682 | `coordonneesGeographique.scoreBAN` | Qualité de l'appariement |
| `id_lot` | TEXTE | jamais | — | |

L'objet `coordonneesGeographique` est nul pour 91 682 adresses ; il est aplati
en six colonnes, toutes nulles ensemble ou toutes renseignées ensemble.

### 3.4 `contact` — 222 505 lignes

Sources : `pmej[].contact[]` (76 652) et `pmej[].ege[].contact[]` (145 853).

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `type_porteur` | TEXTE | jamais | — | `EJ` ou `ET` |
| `id_porteur` | TEXTE | jamais | — | |
| `num_finess_porteur` | TEXTE | jamais | — | |
| `rang` | ENTIER_TEXTE | jamais | — | |
| `code_role_contact` | TEXTE | jamais | `typeContact.roleContact` | |
| `telephone` | TEXTE | 410 | `telecom.telephone` | |
| `telecopie` | TEXTE | 126 549 | `telecom.telecopie` | |
| `courriel` | TEXTE | 222 401 | `telecom.courriel` | **104 valeurs renseignées sur 222 505.** Champ inexploitable en l'état |
| `id_lot` | TEXTE | jamais | — | |

### 3.5 `engagement` — 77 487 lignes

Sources : `pmej[].engagement[]` (8), `pmej[].ege[].engagement[]` (77 260),
`pmej[].activitesAutorisees[].engagement[]` (219, fichier activités).
`pmej[].ege[].activitesExercees[].engagement[]` est **toujours vide**.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `engagement_id` | TEXTE | jamais | `engagementId` | |
| `type_porteur` | TEXTE | jamais | — | `EJ`, `ET`, `ACTIVITE_EJ` |
| `id_porteur` | TEXTE | jamais | — | |
| `num_finess_porteur` | TEXTE | variable | — | Nul pour un porteur de type activité |
| `rang` | ENTIER_TEXTE | jamais | — | |
| `code_type_engagement` | TEXTE | 144 | `typeEngagement` | `ARR`, `ASD`, `ASE`, `DISP`, `CPOM`… |
| `code_sous_type_engagement` | TEXTE | 156 | `sousTypeEngagement` | **`DISP`/`DIT` = fonctionnement en dispositif intégré (DITEP)** |
| `nom_engagement` | TEXTE | 77 269 | `nomEngagement` | |
| `identifiant_engagement` | TEXTE | 77 269 | `identifiantEngagement` | |
| `code_motif_arrete` | TEXTE | 77 191 | `motifArrete` | |
| `date_effet` | DATE | 24 | `dateEffetEngagement` | |
| `date_signature` | DATE | 24 | `dateSignatureEngagement` | |
| `date_fin` | DATE | 77 173 | `dateFinEngagement` | |
| `date_notification` | DATE | 77 173 | `dateNotificationEngagement` | |
| `date_caducite` | DATE | 77 474 | `dateCaduciteEngagement` | |
| `id_lot` | TEXTE | jamais | — | |

### 3.6 `engagement_autorite` — 316 lignes

Source : `engagement[].autoriteRegulationEngagement[]`, aux trois niveaux.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `engagement_id` | TEXTE | jamais | parent | |
| `rang` | ENTIER_TEXTE | jamais | — | |
| `code_autorite_regulation` | TEXTE | jamais | `autoriteRegulationid` | `ARS-75`, `CD-59`, `DDETS-68`… |
| `id_lot` | TEXTE | jamais | — | |

### 3.7 `evenement` — 1 961 124 lignes

Sources : `gcc[].evenement[]` (135), `pmej[].evenement[]` (165 102),
`pmej[].ege[].evenement[]` (463 838), `pmej[].activitesAutorisees[].evenement[]`
(474 105), `pmej[].ege[].activitesExercees[].evenement[]` (857 944).
Table la plus volumineuse du pivot.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `evenement_id` | TEXTE | jamais | `evenementId` | |
| `type_porteur` | TEXTE | jamais | — | `EJ`, `ET`, `ACTIVITE_EJ`, `ACTIVITE_ET`, `GROUPEMENT` |
| `id_porteur` | TEXTE | jamais | — | |
| `rang` | ENTIER_TEXTE | jamais | — | |
| `code_evenement` | TEXTE | jamais | `codeEvenement` | |
| `date_evenement` | DATE | jamais | `dateEvenement` | |
| `date_enregistrement` | HORODATAGE | jamais | `dateEnregistrement` | |
| `code_etat_objet_1` | TEXTE | variable | `etatObjet1` | |
| `code_type_objet_1` | TEXTE | jamais | `typeObjet1` | |
| `identifiant_objet_1` | TEXTE | jamais | `identifiantObjet1` | |
| `code_type_objet_2` | TEXTE | quasi toujours | `typeObjet2` | |
| `identifiant_objet_2` | TEXTE | quasi toujours | `identifiantObjet2` | |
| `code_systeme_maitre` | TEXTE | jamais | `systemeMaitre` | |
| `id_lot` | TEXTE | jamais | — | |

### 3.8 `groupement` — 1 991 lignes

Sources : `gco[]` (1 856) et `gcc[]` (135), unifiées par `nature_groupement`.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `nature_groupement` | TEXTE | jamais | — | `GCO` ou `GCC` |
| `groupement_id` | TEXTE | jamais | `pmSmsseId` (GCO) / `gccId` (GCC) | |
| `num_finess_groupement` | TEXTE | 1 856 | `numFinessGcc` | 11 caractères, GCC seulement |
| `nom_groupement` | TEXTE | 1 856 | `nomGcc` | GCC seulement |
| `code_type_groupement` | TEXTE | jamais | `typeGco` / `typeGcc` | GCO : `001` 814, `002` 36, `003` 940, `004` 66 |
| `etat_objet` | TEXTE | 1 856 | `etatObjet` | GCC seulement |
| `date_derniere_maj` | HORODATAGE | 1 856 | `dateDerniereMaj` | GCC seulement |
| `id_lot` | TEXTE | jamais | — | |

### 3.9 `groupement_membre` — 763 lignes

Sources : `pmejDuGco[]` (2), `pmejDuGcc[]` (761). `egeDuGco[]` et `egeDuGcc[]`
sont **toujours vides** sur 202607 ; les champs restent prévus au contrat.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `groupement_id` | TEXTE | jamais | parent | |
| `nature_groupement` | TEXTE | jamais | parent | |
| `type_membre` | TEXTE | jamais | — | `EJ` ou `ET` |
| `id_membre` | TEXTE | jamais | `pmSmsseId` ou identifiant d'EGE | |
| `code_role_membre` | TEXTE | jamais | `typeRoleEntiteGroupe` | |
| `rang` | ENTIER_TEXTE | jamais | — | |
| `id_lot` | TEXTE | jamais | — | |

### 3.10 `relation_etablissement` — 47 474 lignes

Source : `pmej[].ege[].roleEge[]`.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `ege_id` | TEXTE | jamais | parent | Établissement où la relation est déclarée |
| `rang` | ENTIER_TEXTE | jamais | — | |
| `ege_id_porteuse` | TEXTE | jamais | `idEgePorteuse` | |
| `ege_id_non_porteuse` | TEXTE | jamais | `idEgeNonPorteuse` | |
| `code_role_relation` | TEXTE | jamais | `roleRelationEge` | `B` seule valeur observée |
| `id_lot` | TEXTE | jamais | — | |

---

## 4. Enregistrements issus de `finess-activites`

### 4.1 `activite` — 585 746 lignes

Sources : `pmej[].activitesAutorisees[]` (292 873, niveau EJ) et
`pmej[].ege[].activitesExercees[]` (292 873, niveau ET). **Une seule table, avec
un discriminant `niveau`** : les deux niveaux partagent l'essentiel de leurs
champs et sont complémentaires, pas redondants (voir § 6).

**Le jeu de clés de `caracteristiquesSpecifiques` dépend de la nature.** Mesuré
sur les 585 746 activités : chaque nature ne présente qu'une seule forme,
identique aux deux niveaux. Le contrat est donc déclaré par nature, ce qui le
rend plus strict qu'une union de clés.

| Nature | Clés de `caracteristiquesSpecifiques` |
|---|---|
| ASMR, ASOCR | `activiteAeId`, `aaSocialeReguleeId`, le bloc typé, les 4 bornes d'âge |
| ASDR | `activiteAeId`, `aaSanitaireDiverseReguleeId`, le bloc typé |
| AER | `activiteAeId`, le bloc typé — **aucun identifiant de nature** |
| AASA | + `aaAutreActSoinId`, `etatArhgos`, `numDecision`, `resultatVisite`, `dateLimDep`, `dateLimVisiteConformite`, `dateVisite` |
| AMF | `activiteAeId`, `aaSoinAmfId`, le bloc typé |
| AMM | `activiteAeId`, `aaSoinAmmId`, le bloc typé, `appareil` |
| EML | `activiteAeId`, `aaEmlId`, le bloc typé, `marque`, `numeroSerie` |

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `niveau` | TEXTE | jamais | — | `EJ` ou `ET` |
| `activite_ae_id` | TEXTE | jamais | `caracteristiquesGeneriques.activiteAeId` | Clé de rattachement des capacités |
| `num_finess_ej` | TEXTE | jamais | parent | |
| `pm_smsse_id` | TEXTE | jamais | parent | |
| `ege_id` | TEXTE | 292 873 | `caracteristiquesGeneriques.egeId` | Renseigné au niveau ET, toujours nul au niveau EJ |
| `num_finess_et` | TEXTE | 292 873 | parent | Idem |
| `rang` | ENTIER_TEXTE | jamais | — | |
| `code_nature` | TEXTE | jamais | `nature.codeNature` | `ASMR` 226 840, `ASDR` 174 410, `ASOCR` 91 516, `AMM` 62 926, `AMF` 13 744, `AER` 11 790, `AASA` 4 384, `EML` 136 (deux niveaux cumulés) |
| `code_type_activite_smsse` | TEXTE | jamais | `caracteristiquesGeneriques.typeActiviteSMSSE` | |
| `etat_objet` | TEXTE | jamais | `caracteristiquesGeneriques.etatObjet` | |
| `identifiant_autorisation` | TEXTE | 292 873 | `caracteristiquesGeneriques.identifiantAutorisation` | Niveau ET seulement |
| `num_autorisation_arhgos` | TEXTE | 511 400 | `caracteristiquesGeneriques.numAutorisationArhgos` | |
| `date_debut_activite_autorisee` | DATE | 79 161 | `caracteristiquesGeneriques.dateDebutActiviteAutorisee` | |
| `date_fin_activite_autorisee` | DATE | 507 392 | `caracteristiquesGeneriques.dateFinActiviteAutorisee` | |
| `date_fin_effective_activite` | DATE | 585 158 | `caracteristiquesGeneriques.dateFinEffectiveActivite` | |
| `date_caducite_autorisation` | DATE | 584 057 | `caracteristiquesGeneriques.dateCaduciteAutorisation` | |
| `pm_smsse_exploitante_id` | TEXTE | 585 721 | `caracteristiquesGeneriques.pmSmsseExploitanteId` | Niveau EJ seulement, 25 valeurs |
| `ege_exploitante_id` | TEXTE | 585 721 | `caracteristiquesGeneriques.egeExploitanteId` | Niveau ET seulement, 25 valeurs |
| `ege_facturante` | TEXTE | 585 721 | `caracteristiquesGeneriques.egeFacturante` | Niveau ET seulement, 25 valeurs |
| `identifiant_nature` | TEXTE | variable | `aaSocialeReguleeId`, `aaSanitaireDiverseReguleeId`, `aaSoinAmmId`, `aaSoinAmfId`, `aaAutreActSoinId`, `aaEmlId` | **Fente unique** : un seul de ces six champs est renseigné, désigné par `code_nature` |
| `code_activite_regulee` | TEXTE | variable | `typeActiviteAMSR.activiteSocialeRegulee`, `typeActiviteASOCR.activiteSocialeRegulee`, `typeActiviteASDR.activiteSanitaireDiverseRegulee`, `typeActiviteAER.activiteEnseignementRegulee`, `typeActiviteAASA.activiteSanitaireRegulee`, `typeActiviteAMF.activiteAMF`, `typeActiviteAMM.activiteAMM` | **Fente unique.** Successeur de `code_discipline` du CSV. La nomenclature applicable est déterminée par `code_nature` |
| `code_mode_fonctionnement` | TEXTE | 81 190 | `typeActivite{AMSR,ASOCR,ASDR,AER}.modeFonctionnement` | Successeur de `code_fonctionnement` |
| `code_public` | TEXTE | 81 190 | `typeActivite{AMSR,ASOCR,ASDR,AER}.public` | Successeur de `code_clientele` |
| `age_min_autorise` | ENTIER_TEXTE | 550 088 | `ageMinAutorise` | ASMR et ASOCR seulement. **17 829 valeurs par niveau, soit 11,2 % des activités concernées** |
| `age_max_autorise` | ENTIER_TEXTE | 550 080 | `ageMaxAutorise` | 17 833 par niveau. 7 valeurs > 120 ans |
| `age_min_installe` | ENTIER_TEXTE | 549 478 | `ageMinInstalle` | 18 131 (EJ) et 18 137 (ET) |
| `age_max_installe` | ENTIER_TEXTE | 549 478 | `ageMaxInstalle` | 18 131 (EJ) et 18 137 (ET). 9 valeurs > 120 ans, dont une à `2020` |
| `code_forme_activite` | TEXTE | variable | `typeActivite{AASA,AMF}.formeActivite` | |
| `code_modalite_activite` | TEXTE | variable | `typeActivite{AASA,AMF}.modaliteActivite` | |
| `code_modalite_amm` | TEXTE | variable | `typeActiviteAMM.modaliteAMM` | |
| `code_mention_amm` | TEXTE | variable | `typeActiviteAMM.mentionAMM` | |
| `code_pts_amm` | TEXTE | variable | `typeActiviteAMM.ptsAMM` | |
| `code_declaration_amm` | TEXTE | variable | `typeActiviteAMM.declarationAMM` | |
| `type_eml_id` | TEXTE | variable | `typeActiviteEML.typeEmlId` | 68 par niveau |
| `marque` | TEXTE | variable | `marque` | EML, niveau EJ seulement |
| `numero_serie` | TEXTE | variable | `numeroSerie` | EML, niveau EJ seulement, 18 valeurs |
| `code_etat_arhgos` | TEXTE | variable | `etatArhgos` | AASA, niveau ET seulement |
| `num_decision` | TEXTE | variable | `numDecision` | AASA, niveau EJ seulement |
| `date_lim_dep` | DATE | variable | `dateLimDep` | AASA, niveau ET seulement |
| `date_lim_visite_conformite` | DATE | variable | `dateLimVisiteConformite` | AASA, niveau ET seulement |
| `date_visite` | DATE | variable | `dateVisite` | AASA, niveau ET seulement |
| `code_resultat_visite` | TEXTE | toujours | `resultatVisite` | Toujours nul aux deux niveaux |
| `activite_ae_id_specifique` | TEXTE | variable | `caracteristiquesSpecifiques.activiteAeId` | Second identifiant, distinct du précédent |
| `id_lot` | TEXTE | jamais | — | |

Les colonnes propres à une nature sont creuses par construction. En SQLite, une
valeur nulle coûte un octet d'en-tête : une table plate est préférable à une
table clé/valeur, plus simple à interroger et sans perte.

### 4.2 `capacite` — 537 233 lignes

Sources : `activitesAutorisees[].capacite[]` (138 696, niveau EJ) et
`activitesExercees[].capacite[]` (398 537, niveau ET). Même discriminant
`niveau`.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `id_capacite` | TEXTE | jamais | `idCapacite` | |
| `niveau` | TEXTE | jamais | — | `EJ` ou `ET` |
| `activite_ae_id` | TEXTE | jamais | `activiteAeId` | Rattachement à `activite` |
| `rang` | ENTIER_TEXTE | jamais | — | |
| `nombre` | ENTIER_TEXTE | 22 | `nombre` | Maximum observé 7 288, aucune valeur négative ni non numérique |
| `code_statut_capacite` | TEXTE | jamais | `statutCapacite` | `08` 259 841 (ET) — `09` 138 696 (EJ) et 138 696 (ET). Voir § 6 |
| `code_unite_mesure` | TEXTE | jamais | `uniteMesureCapacite` | `02` 393 972, `03` 4 565 au niveau ET |
| `code_habilitation` | TEXTE | 459 941 | `habilitation` | |
| `code_type_logement` | TEXTE | 525 933 | `typeLogement` | |
| `code_genre` | TEXTE | 479 781 | `genre` | |
| `code_mode_financement` | TEXTE | 533 600 | `modeFinancement` | |
| `precision` | TEXTE | toujours | `precision` | Toujours nul aux deux niveaux |
| `variation` | TEXTE | toujours | `variation` | Toujours nul aux deux niveaux |
| `engagement_id` | TEXTE | toujours | `engagementId` | Toujours nul aux deux niveaux |
| `id_lot` | TEXTE | jamais | — | |

### 4.3 `appareil` — 16 096 lignes

Source : `activitesExercees[].nature.caracteristiquesSpecifiques.appareil[]`.
**Niveau ET exclusivement** : au niveau EJ, le tableau existe mais est vide
pour les 31 463 activités AMM.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `activite_ae_id` | TEXTE | jamais | parent | |
| `rang` | ENTIER_TEXTE | jamais | — | |
| `code_type_appareil` | TEXTE | jamais | `typeAppareilAMM` | |
| `nombre_appareil` | ENTIER_TEXTE | jamais | `nombreAppareilAMM` | |
| `code_statut_appareil` | TEXTE | jamais | `statutAppareilAMM` | |
| `id_lot` | TEXTE | jamais | — | |

2 012 activités portent exactement 8 appareils ; les 29 451 autres, aucun.

### 4.4 `zone_intervention` — 8 336 lignes

Source : `activitesAutorisees[].zoneIntervention`. **Niveau EJ exclusivement** :
au niveau ET, le champ est nul pour les 292 873 activités.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `zone_intervention_id` | TEXTE | jamais | `zoneInterventionAutoriseeId` | |
| `activite_ae_id` | TEXTE | jamais | `activiteAeId` | |
| `libelle_zone` | TEXTE | 7 099 | `libelleZI` | **Second et dernier libellé du jeu de données** |
| `id_lot` | TEXTE | jamais | — | |

### 4.5 `zone_intervention_commune` — 1 231 970 lignes

Source : `zoneIntervention.communeZI[]`.

| Champ | Type | Nul | Source JSON | Note |
|---|---|---|---|---|
| `zone_intervention_id` | TEXTE | jamais | parent | |
| `rang` | ENTIER_TEXTE | jamais | — | |
| `cog_commune` | TEXTE | jamais | `commune` | |
| `id_lot` | TEXTE | jamais | — | |

---

## 5. Champs codifiés et domaines de nomenclature

Aucune de ces nomenclatures n'est fournie par FINESS dans ces fichiers. La
couche 3 devra les constituer. Tant qu'un domaine n'est pas alimenté, les
analyses correspondantes restent impossibles.

| Domaine | Champs du pivot | Valeurs distinctes 202607 |
|---|---|---|
| Catégorie d'établissement | `etablissement.code_categorie` | **300** |
| Activité régulée (par nature) | `activite.code_activite_regulee` | **622**, toutes natures confondues |
| Mode de fonctionnement | `activite.code_mode_fonctionnement` | **52** |
| Public / clientèle | `activite.code_public` | **115** |
| Statut de capacité | `capacite.code_statut_capacite` | 2 |
| Unité de mesure de capacité | `capacite.code_unite_mesure` | 2 |
| Habilitation, type de logement, genre, mode de financement | `capacite.code_*` | **1**, **6**, **2**, **5** |
| Nature d'activité, type d'activité SMSSE | `activite.code_nature`, `code_type_activite_smsse` | **8** et **4 760** |
| Forme et modalité d'activité, modalité AMM, état ARHGOS | `activite.code_*` | **18**, **80**, **51**, **3** |
| Type et statut d'appareil | `appareil.code_*` | **4** et **2** |
| Type et sous-type d'engagement | `engagement.code_type_engagement`, `code_sous_type_engagement` | **4** et **35** |
| Autorité de régulation | `engagement_autorite.code_autorite_regulation` | **21** (`ARS-xx`, `CD-xx`, `DDETS-xx`) |
| Mode de fixation tarifaire | `etablissement.code_mode_fixation_tarifaire` | **49** |
| Statut juridique, type de personne morale, fonction publique, ESPIC, type de budget | `entite_juridique.*`, `etablissement.*` | **69**, **1**, **3**, **9**, **2** |
| Type de voie, usage d'adresse | `adresse.code_type_voie`, `code_usage_adresse` | **191** et **4** |
| Codes et types d'événement | `evenement.code_*` | code **12**, état **17**, type d'objet **3**, système maître **3** |
| Rôle de contact, rôle de membre de groupement, rôle de relation, type de groupement, type de groupe GCO, motif d'arrêté, code APE, état d'objet | divers | **1**, **2**, **2**, **4**, **4**, **7**, **538**, **2** |
| Territoires | `adresse.cog_commune`, `zone_intervention_commune.cog_commune` | INSEE — volontairement exclus de l'inventaire des codes |

---

## 6. Points du contrat qui appellent une décision explicite

**Les deux niveaux d'activité ne sont pas redondants.** Le recensement exhaustif
corrige une hypothèse du plan de migration : les effectifs sont identiques
(292 873 de part et d'autre), mais les contenus diffèrent.

| Information | Niveau EJ | Niveau ET |
|---|---|---|
| `zoneIntervention` | 8 336 renseignées | **toujours nul** |
| `appareil[]` | **toujours vide** | 16 096 lignes |
| `engagement[]` | 219 | **toujours vide** |
| `egeId`, `identifiantAutorisation` | toujours nuls | toujours renseignés |
| `marque`, `numeroSerie`, `numDecision` | renseignés | toujours nuls |
| `etatArhgos`, `dateLimDep`, `dateVisite` | toujours nuls | renseignés |
| `aaSoinAmmId`, `aaSoinAmfId`, `aaSanitaireDiverseReguleeId` | toujours nuls | renseignés |
| Capacités | statut `09` seulement | statuts `08` et `09` |

N'ingérer que le niveau ET ferait donc perdre les 8 336 zones d'intervention et
les 219 engagements d'activité. **Les deux niveaux doivent être ingérés.**

**Sémantique des statuts de capacité.** Deux codes, `08` et `09`. Le niveau EJ,
nommé « activités autorisées », ne contient que du `09` ; lorsque les deux
coexistent sur une même activité, `09 ≥ 08` dans 98 % des cas. L'hypothèse de
travail est donc `09` = autorisée et `08` = installée. **Elle reste à confirmer
sur la nomenclature officielle avant toute publication.**

**Les bornes d'âge sont peu renseignées.** Elles ne couvrent, à chaque niveau, que 17 829 à 18 137 activités sur les
159 178 activités sociales et médico-sociales, soit environ 11 %. Elles ne peuvent donc pas servir de critère principal de périmètre
enfance-adolescence ; tout au plus de critère de confirmation. Seize valeurs
dépassent 120 ans, dont une à `2020`.

**Le courriel est inexploitable** : 104 valeurs renseignées sur 222 505 contacts.

**Deux champs ne portent aucune information discriminante** en 202607 :
`contact.code_role_contact` et `capacite.code_habilitation` n'ont qu'une seule
valeur distincte chacun, de même que `entite_juridique.code_type_personne_morale`.

**Quatre constats de structure, relevés par E5 et acquittés.** Chacun est
bloquant tant qu'il n'est pas inscrit dans `CONSTATS_ACQUITTES` avec sa
justification : le mécanisme interrompt plutôt qu'il ne masque, et la levée
exige une décision tracée. Aucun n'affecte la fidélité du pivot ; tous portent
sur la donnée FINESS ou sur ce que la couche 3 devra en faire.

| Constat | Mesure | Décision |
|---|---|---|
| `evenement.code_etat_objet_1` recopie `code_evenement` | Identiques sur 1 890 308 des 1 960 029 évènements, soit 96,4 % : **100 %** dans le fichier activités, **88,7 %** dans le fichier structures. Les 69 721 divergences portent toutes sur `code_evenement = 005`, où le champ prend 004, 100, 101, 102 ou 103 | Champ transporté verbatim. **Inutilisable comme critère d'analyse sans précaution** |
| `code_evenement` : vocabulaires disjoints entre les deux fichiers | 001-007, 016-019, 034-037 côté structures ; 008-015, 021-022, 030-031 côté activités. Aucune valeur commune | Non tranché. Une nomenclature unique partitionnée par type d'objet et deux nomenclatures distinctes sont également compatibles avec l'observation. La couche 3 décidera sur pièce |
| `etat_objet_evenement` : vocabulaires disjoints | Conséquence du premier constat. Seules 004, 100, 101, 102, 103 sont propres à ce champ | Idem |
| `type_voie` : variantes d'écriture | **191 codes observés, 128 après normalisation** : 63 ne sont que des variantes. `AV` se présente en `'AV'` (28 949), `'AV  '` (2 587), `'AV '` (3), `'av'` (3) | L'acquisition émet verbatim. **La couche 3 devra normaliser avant de constituer la nomenclature.** Aucun autre domaine n'est concerné |

**Codes vus une seule fois**, à examiner en priorité par la couche 3 : 15 en
catégorie d'établissement, 24 en type de voie, 12 en autorité de régulation,
3 en sous-type d'engagement, 1 en statut juridique, 182 en code APE.

**`code_type_activite_smsse` est une nomenclature volumineuse** : 4 760 valeurs
distinctes, contre 622 pour l'activité régulée. Le plafond par défaut de
l'inventaire des codes est de 5 000 : il devra être relevé lors de la
constitution des nomenclatures, faute de quoi ce domaine saturera au prochain
millésime.

---

## 7. Volumétrie de référence — millésime 202607

Valeurs à figer comme test de non-régression du module d'acquisition.

| Enregistrement | Lignes |
|---|---|
| `entete` | 2 |
| `entite_juridique` | 98 168 |
| `etablissement` | 174 508 |
| `adresse` | 278 615 |
| `contact` | 222 505 |
| `engagement` | 77 487 |
| `engagement_autorite` | 316 |
| `evenement` | 1 961 124 |
| `groupement` | 1 991 |
| `groupement_membre` | 763 |
| `relation_etablissement` | 47 474 |
| `activite` | 585 746 |
| `capacite` | 537 233 |
| `appareil` | 16 096 |
| `zone_intervention` | 8 336 |
| `zone_intervention_commune` | 1 231 970 |
| **Total** | **5 242 334** |

Invariants bloquants associés : `num_finess_et` unique sur 174 508 ;
`num_finess_ej` unique sur 98 168 ; tout `num_finess_et` du fichier activités
présent dans le fichier structures (139 675 sur 139 675) ; concordance
`ege_id` entre les deux fichiers sur 139 675 lignes ; nombre de capacités de
statut `09` identique aux deux niveaux (138 696).

---

## 8. Règles d'évolution du contrat

1. Toute clé JSON rencontrée mais non déclarée ici déclenche une anomalie
   bloquante. Le contrat ne se découvre pas à l'exécution.
2. Un changement de `schemaVersion` impose la révision de ce document avant
   toute ingestion du nouveau millésime.
3. L'ajout d'un champ incrémente la version mineure du contrat ; la suppression
   ou le changement de type d'un champ existant incrémente la version majeure.
4. Les couches supérieures ne dépendent que des noms déclarés ici. Le jour où
   FINESS renomme un champ, seule la couche 1 change.
5. Les effectifs du § 7 sont des repères du millésime 202607, pas des
   contraintes : ils servent au contrôle d'écart, pas au rejet.
