"""
cli.py — Orchestration, étape E6.

Point d'entrée unique de la chaîne d'acquisition. Six commandes :

    inspecter   volumétrie, en-tête, anomalies et échantillon d'un fichier
    inventaire  registre des codes observés (étape E5)
    integrite   contrôles de rattachement entre tables (migrés d'E5)
    tout        les trois précédentes, dans l'ordre
    charger     écrit structures (et activités) dans l'entrepôt SQLite (couche 2)
    restituer   export CSV département × catégorie + rapport (couche 6, OOM-14)

La commande `integrite` accueille les contrôles retirés de l'inventaire : ils
portent sur les rattachements, non sur les codes, et n'avaient pas leur place
dans une passe dédiée aux nomenclatures. Le coût mémoire des index a été ramené
de 49 à 4,4 Mio par l'encodage entier de `controles.IndexIdentifiants`.

La commande `charger` ne fait qu'exposer `entrepot`/`chargement` (couche 2,
déjà écrite et testée) depuis ce point d'entrée unique : jusqu'ici, charger
dans l'entrepôt exigeait de connaître et lancer `chargement.py` directement.
Elle n'est volontairement pas enchaînée dans `tout` pour l'instant — seul le
premier POC (structures obligatoire, activités optionnel) en a besoin.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from mesure_rss import rss_max_mio

from contrat_source import (BLOQUANT, CONTROLE_ECHANTILLON, CONTROLE_MINIMAL,
                            CONTROLE_STRICT, InventaireCodes, Lot, RapportIngestion,
                            RegistreAnomalies, parcourir_source)
from controles import VerificateurRelations
import finess_commun as fc
import inventaire_codes as ic
from finess_activites import SourceFinessActivites
from finess_structures import SourceFinessStructures
from entrepot import Entrepot, ErreurEntrepot
from chargement import charger, ErreurChargement, REFUSER, REMPLACER, LOT_DEFAUT
import export_tabulaire as et

SOURCES = {
    "structures": SourceFinessStructures,
    "activites": SourceFinessActivites,
}


def rss_mio() -> float:
    return rss_max_mio()


def _source_du_fichier(chemin: Path, force: Optional[str] = None):
    """Détermine le connecteur à employer, sans deviner en silence."""
    if force:
        return SOURCES[force]()
    nom = chemin.name.lower()
    candidats = [cle for cle in SOURCES if cle in nom]
    if len(candidats) != 1:
        raise SystemExit(
            f"Impossible de déterminer le connecteur pour {chemin.name!r}. "
            f"Précisez --source parmi {sorted(SOURCES)}.")
    return SOURCES[candidats[0]]()


def _positions() -> Dict[str, Dict[str, int]]:
    return {t.nom: {c: i for i, c in enumerate(t.noms)} for t in fc.TOUS_LES_TYPES}


# ---------------------------------------------------------------------------
# inspecter
# ---------------------------------------------------------------------------

def commande_inspecter(arguments) -> int:
    source = _source_du_fichier(arguments.fichier, arguments.source)
    rapport = RapportIngestion(Lot("", "", "", "", 0), RegistreAnomalies(),
                               InventaireCodes(), arguments.controle)
    echantillons: Dict[str, Tuple] = {}
    for nom_type, ligne in parcourir_source(source, arguments.fichier,
                                            controle=arguments.controle,
                                            rapport=rapport):
        if arguments.echantillon and nom_type not in echantillons:
            echantillons[nom_type] = ligne

    print(rapport.texte())
    print(f"RSS max    : {rss_mio():.1f} Mio")
    if arguments.echantillon:
        types = {t.nom: t for t in source.types_enregistrements()}
        print("\nÉchantillon — première ligne de chaque type :")
        for nom_type in sorted(echantillons):
            print(f"\n  [{nom_type}]")
            for champ, valeur in zip(types[nom_type].noms, echantillons[nom_type]):
                print(f"      {champ:<32} {valeur!r}")
    return 1 if rapport.statut != "SUCCES" else 0


# ---------------------------------------------------------------------------
# inventaire
# ---------------------------------------------------------------------------

def commande_inventaire(arguments) -> int:
    resultat, retour = ic.executer(arguments.structures, arguments.activites,
                                   arguments.sortie, arguments.plafond)
    print(ic.rapport_texte(resultat, arguments.plafond))
    print(f"\nRegistre écrit : {arguments.sortie}")
    if retour:
        print("\nINTERROMPU : anomalies bloquantes ci-dessus.")
    return retour


# ---------------------------------------------------------------------------
# integrite
# ---------------------------------------------------------------------------

def commande_integrite(arguments) -> int:
    """Trois passes : indexation, contrôle des structures, contrôle des activités."""
    registre = RegistreAnomalies(max_exemples=arguments.exemples)
    verificateur = VerificateurRelations(fc.RELATIONS_PIVOT, _positions(), registre)
    depart = time.time()
    lignes = 0

    def parcours(source, chemin, action):
        nonlocal lignes
        rapport = RapportIngestion(Lot("", "", "", "", 0), RegistreAnomalies(),
                                   InventaireCodes(), CONTROLE_MINIMAL)
        for nom_type, ligne in parcourir_source(source, chemin,
                                                controle=CONTROLE_MINIMAL,
                                                rapport=rapport,
                                                inventorier_codes=False):
            lignes += 1
            action(nom_type, ligne)
        if rapport.statut != "SUCCES":
            registre.signaler("ingestion_en_echec", BLOQUANT,
                              type_enregistrement=source.nom,
                              detail=str(rapport.registre.par_code()))
        return rapport

    # 1. Indexation des parents des relations différées
    parcours(SourceFinessStructures(), arguments.structures, verificateur.indexer)
    verificateur.figer()
    # 2. Contrôle du fichier structures
    parcours(SourceFinessStructures(), arguments.structures, verificateur.controler)
    # 3. Contrôle du fichier activités
    parcours(SourceFinessActivites(), arguments.activites, verificateur.controler)

    duree = time.time() - depart
    print("=== Intégrité des rattachements ===")
    print(f"Durée      : {duree:.1f} s · RSS max {rss_mio():.1f} Mio · "
          f"{lignes} lignes parcourues sur trois passes")
    print()
    print(verificateur.texte())
    total = sum(verificateur.orphelines.values())
    print(f"\nRéférences orphelines : {total}")
    if total:
        for code in registre.par_code():
            for exemple in registre.exemples(code)[:5]:
                print(f"    {exemple}")
    return 1 if registre.bloquantes else 0


# ---------------------------------------------------------------------------
# charger
# ---------------------------------------------------------------------------

def commande_charger(arguments) -> int:
    """Charge structures (et activités si fournies) dans l'entrepôt SQLite.

    Porte dans le point d'entrée unique ce que `chargement.py` exposait déjà
    en exécution directe (`python chargement.py ...`) : mêmes fonctions
    (`entrepot.Entrepot`, `chargement.charger`), même politique de doublon,
    aucune logique nouvelle. `--creer` recrée le schéma (écrase toute base
    existante), à l'identique de `entrepot.creer(ecraser=True)`.

    Portée du premier POC : structures obligatoire, activités optionnel via
    `--activites`. Les deux sont chargées dans cet ordre quand les deux sont
    fournies, comme le fait déjà `commande_tout` pour inventaire/integrite.
    """
    fichiers = [("structures", arguments.structures)]
    if arguments.activites is not None:
        fichiers.append(("activites", arguments.activites))

    retour = 0
    with Entrepot(arguments.base) as entrepot:
        if arguments.creer:
            entrepot.creer(ecraser=True)
        for cle, chemin in fichiers:
            source = SOURCES[cle]()
            try:
                rapport = charger(entrepot, source, chemin,
                                  taille_lot=arguments.lot,
                                  controle=arguments.controle,
                                  doublon=REMPLACER if arguments.remplacer else REFUSER)
            except (ErreurChargement, ErreurEntrepot) as erreur:
                print(f"ÉCHEC — {chemin.name} : {erreur}")
                retour = 1
                continue
            print(rapport.texte())
            print()
            retour |= 0 if rapport.statut == "SUCCES" else 1
        print(entrepot.rapport())
    return retour


# ---------------------------------------------------------------------------
# restituer
# ---------------------------------------------------------------------------

def commande_restituer(arguments) -> int:
    """Ouvre l'entrepôt déjà chargé, calcule l'indicateur, exporte le CSV et
    le rapport de synthèse. Rejouable en une seule commande après `charger`.

    S'appuie sur `export_tabulaire.restituer` (couche 6, OOM-14), qui recourt
    pour l'instant à un stub en attendant l'indicateur réel d'OOM-13 — voir
    le docstring de ce module.
    """
    with Entrepot(arguments.base) as entrepot:
        resultat = et.restituer(entrepot, arguments.sortie)
    print(resultat["texte_rapport"])
    return 0


# ---------------------------------------------------------------------------

def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="observatoire",
        description="Chaîne d'acquisition FINESS — couche 1.")
    commandes = analyseur.add_subparsers(dest="commande", required=True)

    inspecter = commandes.add_parser("inspecter", help="volumétrie et anomalies d'un fichier")
    inspecter.add_argument("fichier", type=Path)
    inspecter.add_argument("--source", choices=sorted(SOURCES))
    inspecter.add_argument("--controle", default=CONTROLE_ECHANTILLON,
                           choices=[CONTROLE_MINIMAL, CONTROLE_ECHANTILLON, CONTROLE_STRICT])
    inspecter.add_argument("--echantillon", action="store_true",
                           help="afficher la première ligne de chaque type")
    inspecter.set_defaults(fonction=commande_inspecter)

    inventaire = commandes.add_parser("inventaire", help="registre des codes observés")
    inventaire.add_argument("structures", type=Path)
    inventaire.add_argument("activites", type=Path)
    inventaire.add_argument("--sortie", type=Path, default=Path("inventaire_codes.csv"))
    inventaire.add_argument("--plafond", type=int, default=ic.PLAFOND_E5)
    inventaire.set_defaults(fonction=commande_inventaire)

    integrite = commandes.add_parser("integrite", help="rattachements entre tables")
    integrite.add_argument("structures", type=Path)
    integrite.add_argument("activites", type=Path)
    integrite.add_argument("--exemples", type=int, default=10)
    integrite.set_defaults(fonction=commande_integrite)

    tout = commandes.add_parser("tout", help="inspection, inventaire et intégrité")
    tout.add_argument("structures", type=Path)
    tout.add_argument("activites", type=Path)
    tout.add_argument("--sortie", type=Path, default=Path("inventaire_codes.csv"))
    tout.add_argument("--plafond", type=int, default=ic.PLAFOND_E5)
    tout.add_argument("--controle", default=CONTROLE_ECHANTILLON,
                      choices=[CONTROLE_MINIMAL, CONTROLE_ECHANTILLON, CONTROLE_STRICT])
    tout.add_argument("--exemples", type=int, default=10)
    tout.set_defaults(fonction=commande_tout)

    charger_cmd = commandes.add_parser(
        "charger", help="écrit structures (et activités) dans l'entrepôt SQLite")
    charger_cmd.add_argument("base", type=Path, help="fichier de l'entrepôt SQLite")
    charger_cmd.add_argument("structures", type=Path)
    charger_cmd.add_argument("--activites", type=Path, default=None,
                             help="optionnel pour ce POC — structures seul suffit")
    charger_cmd.add_argument("--creer", action="store_true",
                             help="(re)crée le schéma ; écrase toute base existante")
    charger_cmd.add_argument("--lot", type=int, default=LOT_DEFAUT)
    charger_cmd.add_argument("--controle", default=CONTROLE_ECHANTILLON,
                             choices=[CONTROLE_MINIMAL, CONTROLE_ECHANTILLON, CONTROLE_STRICT])
    charger_cmd.add_argument("--remplacer", action="store_true",
                             help="remplace un lot déjà chargé pour la même source")
    charger_cmd.set_defaults(fonction=commande_charger)

    restituer_cmd = commandes.add_parser(
        "restituer", help="export CSV département × catégorie + rapport (OOM-14)")
    restituer_cmd.add_argument("base", type=Path, help="fichier de l'entrepôt SQLite, déjà chargé")
    restituer_cmd.add_argument("--sortie", type=Path, default=Path("restitution"))
    restituer_cmd.set_defaults(fonction=commande_restituer)
    return analyseur


def commande_tout(arguments) -> int:
    retour = 0
    for chemin, source in ((arguments.structures, "structures"),
                           (arguments.activites, "activites")):
        sous = argparse.Namespace(fichier=chemin, source=source,
                                  controle=arguments.controle, echantillon=False)
        print(f"\n########## inspecter {chemin.name} ##########")
        retour |= commande_inspecter(sous)
    print("\n########## inventaire ##########")
    retour |= commande_inventaire(arguments)
    print("\n########## integrite ##########")
    retour |= commande_integrite(arguments)
    return retour


def main(arguments=None) -> int:
    analyse = construire_analyseur().parse_args(arguments)
    return analyse.fonction(analyse)


if __name__ == "__main__":
    sys.exit(main())
