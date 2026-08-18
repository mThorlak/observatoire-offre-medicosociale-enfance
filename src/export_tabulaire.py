"""
export_tabulaire.py — Restitution du POC #1 : export CSV + rapport (OOM-14).

Dernière étape du POC #1 : rendre l'indicateur département × catégorie
exploitable en dehors de la base SQLite, et produire le rapport de synthèse
qui clôture la démonstration de bout en bout (couche 6, `docs/architecture/
01_ARCHITECTURE_GLOBALE.md` §3 : `export_tabulaire`, `rapport`).

S'appuie sur `indicateurs.indicateur_departement_categorie` (couche 5,
OOM-13) pour le calcul lui-même — établissements actifs par département ×
catégorie, définition d'« actif » et résolution des libellés documentées
dans ce module. `export_tabulaire.py` ne fait qu'écrire son résultat en CSV
et composer le rapport de synthèse.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Dict

from entrepot import Entrepot
from indicateurs import ErreurIndicateurs, Resultat, indicateur_departement_categorie

__all__ = ["ErreurExportTabulaire", "ecrire_csv", "rapport_texte", "restituer"]


class ErreurExportTabulaire(Exception):
    """Entrepôt non ouvert, ou export impossible."""


# ---------------------------------------------------------------------------
# Export CSV
# ---------------------------------------------------------------------------

def ecrire_csv(resultat: Resultat, chemin: Path) -> None:
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        graveur = csv.writer(f, delimiter=";")
        graveur.writerow(["code_departement", "libelle_categorie", "effectif"])
        for departement, categorie, nombre in resultat.lignes_triees():
            graveur.writerow([departement, categorie, nombre])


# ---------------------------------------------------------------------------
# Rapport de synthèse
# ---------------------------------------------------------------------------

def rapport_texte(entrepot: Entrepot, resultat: Resultat, chemin_csv: Path,
                  duree_s: float) -> str:
    """Volumétrie chargée, invariants vérifiés, résultat produit — dans
    l'esprit du rapport déjà produit par `cli.commande_integrite`."""
    integrite = entrepot.verifier_integrite()
    parties = [
        "=== Restitution du POC #1 — export CSV + rapport ===",
        f"Durée      : {duree_s:.1f} s",
        "",
        "-- Volumétrie chargée --",
        entrepot.rapport(),
        "",
        "-- Invariants vérifiés --",
        f"Intégrité SQLite         : {'ok' if integrite['integrite_ok'] else integrite['integrite']}",
        f"Violations clé étrangère : {len(integrite['violations_cles_etrangeres'])}",
        f"Indicateur département×catégorie, total vérifié "
        f"(tableau + exclusions = actifs) : {resultat.verifier_total()}",
        "",
        "-- Résultat produit --",
        f"CSV                      : {chemin_csv}",
        "",
        resultat.rapport(),
    ]
    return "\n".join(parties)


# ---------------------------------------------------------------------------
# Orchestration — une seule fonction pour la commande CLI
# ---------------------------------------------------------------------------

def restituer(entrepot: Entrepot, dossier_sortie: Path) -> Dict[str, object]:
    """Enchaîne calcul de l'indicateur, export CSV et rapport de synthèse.

    Écrit `departement_categorie.csv` et `rapport.txt` dans `dossier_sortie`.
    Retourne un résumé (texte du rapport inclus) pour affichage par la CLI.
    """
    debut = time.time()
    dossier_sortie = Path(dossier_sortie)
    try:
        resultat = indicateur_departement_categorie(entrepot)
    except ErreurIndicateurs as erreur:
        raise ErreurExportTabulaire(str(erreur)) from erreur

    chemin_csv = dossier_sortie / "departement_categorie.csv"
    ecrire_csv(resultat, chemin_csv)

    duree_s = time.time() - debut
    texte = rapport_texte(entrepot, resultat, chemin_csv, duree_s)
    chemin_rapport = dossier_sortie / "rapport.txt"
    chemin_rapport.write_text(texte, encoding="utf-8")

    return {
        "chemin_csv": chemin_csv,
        "chemin_rapport": chemin_rapport,
        "resultat": resultat,
        "texte_rapport": texte,
    }


if __name__ == "__main__":
    import argparse

    analyseur = argparse.ArgumentParser(
        description="Restitution du POC #1 : export CSV + rapport (OOM-14).")
    analyseur.add_argument("base", type=Path, help="fichier de l'entrepôt SQLite, déjà chargé")
    analyseur.add_argument("--sortie", type=Path, default=Path("restitution"))
    arguments = analyseur.parse_args()

    with Entrepot(arguments.base) as entrepot:
        resultat = restituer(entrepot, arguments.sortie)
    print(resultat["texte_rapport"])
