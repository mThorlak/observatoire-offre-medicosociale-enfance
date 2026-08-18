"""
inventaire_codes.py — Couche 1 (acquisition), étape E5.

Produit le registre exhaustif des codes réellement observés dans les deux
fichiers FINESS, et les contrôles qui vont avec.

Ce module ne construit **aucune** nomenclature. Les libellés n'existent nulle
part dans les fichiers sources : les seuls champs textuels du jeu de données
sont `libelleVoie` et `libelleZI`. Ce que produit E5 est donc un *registre des
codes à documenter*, destiné à la couche 3, et non une table code → libellé.
Toute valeur du registre provient d'une observation ; aucune n'est déduite,
complétée ou inventée.

Quatre familles de contrôles, toutes bloquantes :

1. **Complétude** — deux recensements indépendants des codes sont menés dans la
   même passe : l'un par le mécanisme déclaratif de `contrat_source`, l'autre
   par relevé direct des colonnes émises. Tout écart entre les deux, sur
   l'ensemble des couples (domaine, code) comme sur leurs effectifs, est
   bloquant.
2. **Couverture** — pour chaque domaine, la somme des occurrences doit égaler
   le nombre de valeurs non nulles des colonnes qui le portent.
3. **Unicité** — chaque couple (domaine, code) figure une fois et une seule
   dans le registre produit.
4. **Constats de structure** — vocabulaires disjoints entre sources, colonnes
   codifiées redondantes, codes ne différant que par la casse ou les espaces.
   Chacun est bloquant tant qu'il n'a pas été examiné et acquitté.

Les contrôles d'intégrité référentielle **ne relèvent pas de cette étape** :
ils portent sur les rattachements entre tables, non sur les codes, et exigeaient
de retenir 545 352 identifiants, ce qui portait la passe à 153 Mio. Ils sont
traités en E6.

Sont également relevés en avertissement : les domaines
déclarés mais jamais alimentés, les colonnes codifiées toujours nulles, les
codes vus une seule fois, et les domaines saturés.

Note d'architecture : ce fichier est l'étape E5 sous forme exécutable. Il a
vocation à devenir une commande de `cli` en E6, non à rester un module autonome.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from mesure_rss import rss_max_mio

from contrat_source import (AVERTISSEMENT, BLOQUANT, CONTROLE_MINIMAL, InventaireCodes,
                            Lot, RapportIngestion, RegistreAnomalies, TypeEnregistrement,
                            parcourir_source)
import finess_commun as fc
from finess_structures import SourceFinessStructures
from finess_activites import SourceFinessActivites

__all__ = ["Inventaire", "executer"]

# Plafond de l'inventaire pendant la passe E5 uniquement. Le plafond par défaut
# de contrat_source (5 000) reste inchangé : c'est un garde-fou contre un
# connecteur qui déclarerait par erreur un identifiant comme domaine codifié.
# `code_type_activite_smsse` compte 4 760 valeurs distinctes en 202607 et
# saturerait au plafond par défaut ; il est donc relevé ici, et ici seulement.
PLAFOND_E5 = 50_000

# Seuils du contrôle de redondance entre colonnes codifiées.
SEUIL_REDONDANCE = 0.95
MINIMUM_COMPARAISONS = 1_000
ELAGAGE_APRES = 200          # une paire manifestement non redondante est abandonnée
ELAGAGE_SOUS = 0.5

# --- Constats acquittés -----------------------------------------------------
# Un constat de structure — vocabulaires disjoints, colonnes redondantes — est
# BLOQUANT tant qu'il n'a pas été examiné et inscrit ici avec sa justification.
# C'est le mécanisme demandé : interrompre plutôt que masquer, avec une levée
# qui exige une décision humaine tracée au contrat. Retirer une entrée de cette
# table fait de nouveau échouer E5.
CONSTATS_ACQUITTES: Dict[Tuple[str, str], str] = {
    ("vocabulaires_disjoints", "code_evenement"):
        "Constat mesuré, volontairement non tranché. Les codes 001-007, 016-019 et "
        "034-037 n'apparaissent que sur les évènements de structure ; les codes "
        "008-015, 021-022 et 030-031 que sur les évènements d'activité. Une "
        "nomenclature unique partitionnée par type d'objet et deux nomenclatures "
        "distinctes sont l'une comme l'autre compatibles avec l'observation. "
        "Trancher sans la nomenclature officielle serait une hypothèse : la "
        "couche 3 décidera sur pièce. SCHEMA_PIVOT 1.3 § 6.",
    ("vocabulaires_disjoints", "etat_objet_evenement"):
        "Conséquence directe de la redondance ci-dessous : etatObjet1 recopiant "
        "codeEvenement, il en hérite la partition des vocabulaires. Les valeurs "
        "004, 100, 101, 102 et 103 sont les seules propres à ce champ, et "
        "n'apparaissent que dans le fichier structures. SCHEMA_PIVOT 1.3 § 6.",
    ("variantes_ecriture", "type_voie"):
        "Défaut de la donnée FINESS, non du pivot, et confiné à ce seul domaine. "
        "191 codes observés, 128 seulement après suppression des espaces et "
        "harmonisation de la casse : 63 codes ne sont que des variantes "
        "d'écriture. « AV » se présente sous les formes 'AV' (28 949), 'AV  ' "
        "(2 587), 'AV ' (3) et 'av' (3). L'acquisition émet verbatim et ne "
        "normalise rien ; la couche 3 devra normaliser avant de constituer la "
        "nomenclature des types de voie. SCHEMA_PIVOT 1.3 § 6.",
    ("colonnes_redondantes", "evenement.code_evenement~code_etat_objet_1"):
        "Défaut de la donnée FINESS, non du pivot. etatObjet1 recopie "
        "codeEvenement sur la totalité des 1 332 049 évènements du fichier "
        "activités et sur 88,7 % de ceux du fichier structures. Les 69 721 "
        "divergences portent toutes sur codeEvenement=005, où etatObjet1 prend "
        "004, 100, 101, 102 ou 103. Le champ est transporté verbatim, sans perte ; "
        "il ne peut pas servir de critère d'analyse sans précaution. "
        "SCHEMA_PIVOT 1.3 § 6.",
}


class Inventaire:
    """Résultat consolidé d'une passe E5."""

    def __init__(self) -> None:
        # Recensement A : mécanisme déclaratif de contrat_source
        self.par_domaine_a: Dict[str, Dict[str, int]] = {}
        # Recensement B : relevé direct des colonnes émises
        self.par_colonne: Dict[Tuple[str, str, str], Dict[str, int]] = {}
        self.paires_redondantes: Dict[Tuple[str, str, str], Tuple[int, int]] = {}
        self.non_nuls: Dict[Tuple[str, str], int] = {}
        self.lignes: Dict[str, int] = {}
        self.sources_du_domaine: Dict[str, Set[str]] = {}
        self.colonnes_du_domaine: Dict[str, Set[str]] = {}
        self.satures: Set[str] = set()
        self.registres: List[RegistreAnomalies] = []
        self.duree_s = 0.0
        self.rss_max_mio = 0.0

    # -- recensement B, consolidé par domaine ------------------------------

    def par_domaine_b(self) -> Dict[str, Dict[str, int]]:
        consolide: Dict[str, Dict[str, int]] = {}
        for (_source, nom_type, colonne), valeurs in self.par_colonne.items():
            domaine = DOMAINE_DE_COLONNE[(nom_type, colonne)]
            cible = consolide.setdefault(domaine, {})
            for code, n in valeurs.items():
                cible[code] = cible.get(code, 0) + n
        return consolide

    def valeurs_par_source(self, domaine: str) -> Dict[str, Set[str]]:
        """Ensemble des valeurs observées pour un domaine, source par source."""
        resultat: Dict[str, Set[str]] = {}
        for (source, nom_type, colonne), valeurs in self.par_colonne.items():
            if DOMAINE_DE_COLONNE[(nom_type, colonne)] == domaine:
                resultat.setdefault(source, set()).update(valeurs)
        return resultat

    def distincts_par_colonne(self) -> Dict[Tuple[str, str], int]:
        """Nombre de valeurs distinctes par colonne, toutes sources confondues."""
        cumul: Dict[Tuple[str, str], Set[str]] = {}
        for (_source, nom_type, colonne), valeurs in self.par_colonne.items():
            cumul.setdefault((nom_type, colonne), set()).update(valeurs)
        return {cle: len(v) for cle, v in cumul.items()}

    def couverture(self, domaine: str) -> Tuple[int, int]:
        """(occurrences inventoriées, valeurs non nulles des colonnes porteuses)."""
        occurrences = sum(self.par_domaine_a.get(domaine, {}).values())
        attendu = sum(n for (t, c), n in self.non_nuls.items()
                      if DOMAINE_DE_COLONNE.get((t, c)) == domaine)
        return occurrences, attendu


# --- table colonne -> domaine, dérivée des déclarations du schéma ----------

DOMAINE_DE_COLONNE: Dict[Tuple[str, str], str] = {
    (type_enr.nom, champ.nom): champ.domaine
    for type_enr in fc.TOUS_LES_TYPES
    for champ in type_enr.champs
    if champ.domaine
}
DOMAINES_DECLARES: Set[str] = set(DOMAINE_DE_COLONNE.values())

def _signaler(registre: RegistreAnomalies, code: str, gravite: str, **details: str) -> None:
    registre.signaler(code, gravite, **details)


def _passer(source, chemin: Path, inventaire: Inventaire,
            plafond: int) -> RapportIngestion:
    """Parcourt un fichier une fois, en alimentant tous les recensements."""
    rapport = RapportIngestion(Lot("", "", "", "", 0), RegistreAnomalies(),
                               InventaireCodes(), CONTROLE_MINIMAL)
    types = {t.nom: t for t in source.types_enregistrements()}
    positions = {nom: {c: i for i, c in enumerate(t.noms)} for nom, t in types.items()}
    registre = RegistreAnomalies(max_exemples=10)
    inventaire.registres.append(registre)

    # Colonnes à relever pour le recensement B, par type d'enregistrement.
    colonnes_codifiees = {
        nom: tuple((positions[nom][c], c) for (t, c) in DOMAINE_DE_COLONNE if t == nom)
        for nom in types
    }
    # Paires de colonnes codifiées à comparer, par type. Une paire dont le taux
    # d'égalité s'effondre est abandonnée après ELAGAGE_APRES comparaisons :
    # le contrôle reste donc exact sur les paires survivantes, pour un coût
    # négligeable sur les autres.
    paires = {}
    for nom, colonnes in colonnes_codifiees.items():
        liste = list(colonnes)
        paires[nom] = [[i, ci, j, cj, 0, 0, True]
                       for k, (i, ci) in enumerate(liste)
                       for (j, cj) in liste[k + 1:]]

    for nom_type, ligne in parcourir_source(source, chemin, controle=CONTROLE_MINIMAL,
                                            rapport=rapport, inventorier_codes=True,
                                            max_codes_par_domaine=plafond):
        inventaire.lignes[nom_type] = inventaire.lignes.get(nom_type, 0) + 1
        pos = positions[nom_type]

        # Recensement B et comptage des valeurs non nulles
        for indice, colonne in colonnes_codifiees[nom_type]:
            valeur = ligne[indice]
            if valeur is None:
                continue
            cle = (source.nom, nom_type, colonne)
            compte_cle = (nom_type, colonne)
            inventaire.non_nuls[compte_cle] = inventaire.non_nuls.get(compte_cle, 0) + 1
            valeurs = inventaire.par_colonne.setdefault(cle, {})
            valeurs[valeur] = valeurs.get(valeur, 0) + 1
            domaine = DOMAINE_DE_COLONNE[compte_cle]
            inventaire.sources_du_domaine.setdefault(domaine, set()).add(source.nom)
            inventaire.colonnes_du_domaine.setdefault(domaine, set()).add(
                f"{nom_type}.{colonne}")

        # Redondance entre colonnes codifiées d'un même enregistrement
        for paire in paires[nom_type]:
            if not paire[6]:
                continue
            gauche, droite = ligne[paire[0]], ligne[paire[2]]
            if gauche is None or droite is None:
                continue
            paire[4] += 1
            if gauche == droite:
                paire[5] += 1
            elif paire[4] >= ELAGAGE_APRES and paire[5] / paire[4] < ELAGAGE_SOUS:
                paire[6] = False


    for nom_type, liste in paires.items():
        for i, ci, j, cj, compare, egaux, vivante in liste:
            if not vivante or compare < MINIMUM_COMPARAISONS:
                continue
            cle = (nom_type, ci, cj)
            ancien = inventaire.paires_redondantes.get(cle, (0, 0))
            inventaire.paires_redondantes[cle] = (ancien[0] + compare, ancien[1] + egaux)

    # Report du recensement A et des saturations
    for domaine in rapport.inventaire.domaines():
        cible = inventaire.par_domaine_a.setdefault(domaine, {})
        for code, n in rapport.inventaire.valeurs(domaine).items():
            cible[code] = cible.get(code, 0) + n
        if rapport.inventaire.sature(domaine):
            inventaire.satures.add(domaine)

    if rapport.statut != "SUCCES":
        _signaler(registre, "ingestion_en_echec", BLOQUANT,
                  type_enregistrement=source.nom,
                  detail=str(rapport.registre.par_code()))
    for code, gravite, type_enr, champ, n in rapport.registre.detail():
        registre.signaler(code, gravite, type_enregistrement=type_enr, champ=champ,
                          detail=f"{n} occurrences reportées du connecteur")
    return rapport


def executer(chemin_structures: Path, chemin_activites: Path,
             sortie_csv: Optional[Path] = None,
             plafond: int = PLAFOND_E5) -> Tuple[Inventaire, int]:
    """Réalise la passe E5. Retourne (inventaire, code de retour)."""
    inventaire = Inventaire()
    depart = time.time()
    registre = RegistreAnomalies(max_exemples=10)
    inventaire.registres.append(registre)

    _passer(SourceFinessStructures(), chemin_structures, inventaire, plafond)
    _passer(SourceFinessActivites(), chemin_activites, inventaire, plafond)

    # --- 1. Complétude : les deux recensements doivent coïncider -----------
    a = inventaire.par_domaine_a
    b = inventaire.par_domaine_b()
    domaines = set(a) | set(b)
    for domaine in sorted(domaines):
        va, vb = a.get(domaine, {}), b.get(domaine, {})
        if set(va) != set(vb):
            for code in sorted(set(va) ^ set(vb)):
                _signaler(registre, "recensements_discordants", BLOQUANT,
                          type_enregistrement=domaine, champ=code,
                          detail=f"A={va.get(code, 0)} B={vb.get(code, 0)}")
        for code in sorted(set(va) & set(vb)):
            if va[code] != vb[code]:
                _signaler(registre, "effectifs_discordants", BLOQUANT,
                          type_enregistrement=domaine, champ=code,
                          detail=f"A={va[code]} B={vb[code]}")

    # --- 2. Couverture ------------------------------------------------------
    for domaine in sorted(domaines):
        occurrences, attendu = inventaire.couverture(domaine)
        if occurrences != attendu:
            _signaler(registre, "couverture_incomplete", BLOQUANT,
                      type_enregistrement=domaine,
                      detail=f"{occurrences} inventoriées pour {attendu} valeurs non nulles")

    # --- 3. Domaines déclarés jamais alimentés, colonnes toujours nulles ----
    for domaine in sorted(DOMAINES_DECLARES - domaines):
        _signaler(registre, "domaine_jamais_alimente", AVERTISSEMENT,
                  type_enregistrement=domaine)
    for (nom_type, colonne) in sorted(DOMAINE_DE_COLONNE):
        if nom_type in inventaire.lignes and (nom_type, colonne) not in inventaire.non_nuls:
            _signaler(registre, "colonne_codifiee_toujours_nulle", AVERTISSEMENT,
                      type_enregistrement=nom_type, champ=colonne)

    # --- 4. Constats de structure : bloquants sauf acquittement -----------
    for domaine in sorted(domaines):
        par_source = inventaire.valeurs_par_source(domaine)
        if len(par_source) < 2:
            continue
        commun = set.intersection(*par_source.values())
        if commun:
            continue
        detail = " | ".join(f"{s_.replace('finess_', '')}={len(v)}"
                            for s_, v in sorted(par_source.items()))
        justification = CONSTATS_ACQUITTES.get(("vocabulaires_disjoints", domaine))
        _signaler(registre, "vocabulaires_disjoints",
                  AVERTISSEMENT if justification else BLOQUANT,
                  type_enregistrement=domaine,
                  detail=(justification or f"aucune valeur commune : {detail}"))

    distincts = inventaire.distincts_par_colonne()
    # Codes qui ne diffèrent que par la casse ou les espaces. La normalisation
    # ne sert qu'à la détection : l'acquisition émet verbatim, et rien n'est
    # transformé. Une nomenclature bâtie sur les valeurs brutes compterait
    # plusieurs entrées pour un même code.
    for domaine in sorted(domaines):
        groupes: Dict[str, List[str]] = {}
        for code in a.get(domaine, {}):
            groupes.setdefault(code.strip().upper(), []).append(code)
        variantes = {racine: sorted(v) for racine, v in groupes.items() if len(v) > 1}
        if not variantes:
            continue
        surplus = sum(len(v) - 1 for v in variantes.values())
        apercu = "; ".join(
            f"{racine}={v}" for racine, v in sorted(variantes.items())[:3])
        justification = CONSTATS_ACQUITTES.get(("variantes_ecriture", domaine))
        _signaler(registre, "variantes_ecriture",
                  AVERTISSEMENT if justification else BLOQUANT,
                  type_enregistrement=domaine,
                  detail=(justification or
                          f"{len(a[domaine])} codes dont {surplus} simples variantes "
                          f"d'écriture ({len(groupes)} après normalisation) : {apercu}"))

    for (nom_type, gauche, droite), (compare, egaux) in sorted(
            inventaire.paires_redondantes.items()):
        taux = egaux / compare
        if taux < SEUIL_REDONDANCE:
            continue
        # Une colonne constante coïncide mécaniquement avec toute colonne
        # partageant sa valeur : ce n'est pas une redondance d'information.
        # Mesuré : capacite.code_habilitation ne prend qu'une valeur, « 02 »,
        # qui est aussi l'unité de mesure dominante. Écarté à ce titre.
        if min(distincts.get((nom_type, gauche), 0),
               distincts.get((nom_type, droite), 0)) < 2:
            _signaler(registre, "paire_non_discriminante", AVERTISSEMENT,
                      type_enregistrement=f"{nom_type}.{gauche}~{droite}",
                      detail="colonne constante, coïncidence écartée")
            continue
        cible = f"{nom_type}.{gauche}~{droite}"
        justification = CONSTATS_ACQUITTES.get(("colonnes_redondantes", cible))
        _signaler(registre, "colonnes_redondantes",
                  AVERTISSEMENT if justification else BLOQUANT,
                  type_enregistrement=cible,
                  detail=(justification or
                          f"identiques sur {egaux}/{compare} lignes ({taux:.1%})"))

    # --- 5. Saturation ------------------------------------------------------
    for domaine in sorted(inventaire.satures):
        _signaler(registre, "domaine_sature", BLOQUANT, type_enregistrement=domaine,
                  detail=f"plafond {plafond} atteint : le registre est incomplet")

    # --- 6. Écriture du registre, avec contrôle d'unicité -------------------
    if sortie_csv is not None:
        vus: Set[Tuple[str, str]] = set()
        sortie_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(sortie_csv, "w", encoding="utf-8", newline="") as f:
            graveur = csv.writer(f, delimiter=";")
            graveur.writerow(["domaine", "code", "occurrences", "colonnes", "sources"])
            for domaine in sorted(a):
                for code, n in sorted(a[domaine].items(), key=lambda x: (-x[1], x[0])):
                    if (domaine, code) in vus:
                        _signaler(registre, "doublon_registre", BLOQUANT,
                                  type_enregistrement=domaine, champ=code)
                        continue
                    vus.add((domaine, code))
                    graveur.writerow([
                        domaine, code, n,
                        "|".join(sorted(inventaire.colonnes_du_domaine.get(domaine, ()))),
                        "|".join(sorted(inventaire.sources_du_domaine.get(domaine, ()))),
                    ])
        total_couples = sum(len(v) for v in a.values())
        if len(vus) != total_couples:
            _signaler(registre, "registre_incomplet", BLOQUANT,
                      detail=f"{len(vus)} couples écrits pour {total_couples} observés")

    inventaire.duree_s = time.time() - depart
    inventaire.rss_max_mio = rss_max_mio()
    bloquantes = sum(r.bloquantes for r in inventaire.registres)
    return inventaire, (1 if bloquantes else 0)


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def rapport_texte(inventaire: Inventaire, plafond: int) -> str:
    a = inventaire.par_domaine_a
    lignes = [
        "=== Inventaire des codes observés ===",
        f"Durée         : {inventaire.duree_s:.1f} s · RSS max {inventaire.rss_max_mio:.1f} Mio",
        f"Lignes lues   : {sum(inventaire.lignes.values())}",
        f"Domaines      : {len(a)} alimentés sur {len(DOMAINES_DECLARES)} déclarés",
        f"Couples (domaine, code) : {sum(len(v) for v in a.values())}",
        "",
        f"{'DOMAINE':<32}{'CODES':>7}{'OCCURRENCES':>13}{'HAPAX':>7}{'PART DU 1er':>12}  SOURCES",
    ]
    for domaine in sorted(a, key=lambda d: -len(a[d])):
        valeurs = a[domaine]
        occurrences = sum(valeurs.values())
        hapax = sum(1 for n in valeurs.values() if n == 1)
        premier = max(valeurs.values())
        sources = ",".join(s.replace("finess_", "") for s in
                           sorted(inventaire.sources_du_domaine.get(domaine, ())))
        marque = " SATURÉ" if domaine in inventaire.satures else ""
        lignes.append(f"{domaine:<32}{len(valeurs):>7}{occurrences:>13}{hapax:>7}"
                      f"{premier / occurrences:>11.1%}  {sources}{marque}")

    total = sum(r.total() for r in inventaire.registres)
    bloquantes = sum(r.bloquantes for r in inventaire.registres)
    lignes += ["", f"Anomalies : {total} dont {bloquantes} bloquantes"]
    agrege: Dict[Tuple[str, str], int] = {}
    for r in inventaire.registres:
        for code, gravite, type_enr, champ, n in r.detail():
            agrege[(code, gravite)] = agrege.get((code, gravite), 0) + n
    for (code, gravite), n in sorted(agrege.items(), key=lambda x: -x[1]):
        lignes.append(f"    [{gravite}] {code:<40} {n:>8}")
    for r in inventaire.registres:
        for code in r.par_code():
            for exemple in r.exemples(code)[:3]:
                lignes.append(f"        {exemple}")
    return "\n".join(lignes)


if __name__ == "__main__":
    import argparse

    analyseur = argparse.ArgumentParser(
        description="Inventaire des codes observés dans les deux fichiers FINESS.")
    analyseur.add_argument("structures", type=Path)
    analyseur.add_argument("activites", type=Path)
    analyseur.add_argument("--sortie", type=Path,
                           default=Path("inventaire_codes.csv"))
    analyseur.add_argument("--plafond", type=int, default=PLAFOND_E5)
    arguments = analyseur.parse_args()

    resultat, code_retour = executer(arguments.structures, arguments.activites,
                                     arguments.sortie, arguments.plafond)
    print(rapport_texte(resultat, arguments.plafond))
    print(f"\nRegistre écrit : {arguments.sortie}")
    if code_retour:
        print("\nINGESTION INTERROMPUE : anomalies bloquantes ci-dessus.")
    sys.exit(code_retour)
