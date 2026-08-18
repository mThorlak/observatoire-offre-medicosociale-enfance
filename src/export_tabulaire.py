"""
export_tabulaire.py — Restitution du POC #1 : export CSV + rapport (OOM-14).

Dernière étape du POC #1 : rendre l'indicateur département × catégorie
exploitable en dehors de la base SQLite, et produire le rapport de synthèse
qui clôture la démonstration de bout en bout (couche 6, `docs/architecture/
01_ARCHITECTURE_GLOBALE.md` §3 : `export_tabulaire`, `rapport`).

STUB TEMPORAIRE — EN ATTENTE D'OOM-13
---------------------------------------
OOM-13 (couche 5, `indicateurs.py` : établissements actifs par département ×
catégorie) n'existe pas encore sur la branche parente
`thomasfoch/oom-6-poc-1-pipeline-finess-bout-en-bout-minimal` au moment où ce
module est écrit. `_tableau_departement_categorie_stub` ci-dessous recalcule
le même résultat directement depuis l'entrepôt, en attendant.

**À faire quand OOM-13 aura atterri** : remplacer l'appel à
`_tableau_departement_categorie_stub` dans `tableau_departement_categorie`
par un import de la fonction réelle d'`indicateurs.py`, et supprimer le
stub. Rien d'autre dans ce module n'a besoin de changer : la forme du
résultat (une liste de `LigneTableau`, plus un dict de diagnostics) est le
contrat que la fonction réelle devra respecter. Tant que ce remplacement
n'est pas fait, ce module ne restitue pas l'indicateur « officiel » d'OOM-13
et OOM-14 ne doit pas être marqué terminé sur Linear.

Définition d'« actif » retenue par ce stub (à réconcilier avec celle
qu'OOM-13 documentera pour de bon) : `etablissement.etat_objet = 'A'`, seule
valeur désignant un objet en service — cf. `export_front.py` et
`docs/architecture/03_SCHEMA_PIVOT.md`.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from entrepot import Entrepot
from nomenclatures import CodeCategorieInconnu, resoudre_categorie
from territoires import ErreurTerritoires, departement_depuis_cog

__all__ = [
    "ETAT_ACTIF", "LigneTableau", "Diagnostics", "ErreurExportTabulaire",
    "tableau_departement_categorie", "ecrire_csv", "rapport_texte", "restituer",
]

# Cf. export_front.ETAT_OBJET_LIBELLES : deux valeurs seulement, 'A' est la
# seule qui désigne un objet en service (etat_objet, docs/architecture/
# 03_SCHEMA_PIVOT.md). C'est la définition d'« actif » utilisée ici.
ETAT_ACTIF = "A"

# '03' = adresse principale, comme dans export_front.py.
USAGE_ADRESSE_PRINCIPALE = "03"

LIBELLE_CATEGORIE_ABSENTE = "[catégorie non renseignée]"


class ErreurExportTabulaire(Exception):
    """Entrepôt non ouvert, ou export impossible."""


class LigneTableau(NamedTuple):
    code_departement: str
    code_categorie: Optional[str]
    libelle_categorie: str
    effectif: int


class Diagnostics(NamedTuple):
    """Ce qui n'entre pas dans le tableau, compté explicitement (D6 : jamais
    de perte silencieuse)."""
    actifs_total: int
    sans_departement_resolu: int
    sans_categorie: int
    categories_inconnues: int


# ---------------------------------------------------------------------------
# Stub — voir le docstring du module.
# ---------------------------------------------------------------------------

def _tableau_departement_categorie_stub(
        entrepot: Entrepot) -> Tuple[Dict[Tuple[str, Optional[str]], int], int]:
    """Requête directe sur l'entrepôt. Retourne (comptes, actifs_total).

    `comptes` associe (code_departement, code_categorie) à un effectif ;
    `code_categorie` peut être `None` (catégorie non renseignée). Les
    établissements actifs sans département résoluble (pas d'adresse
    principale, ou `cog_commune` non résolu par `territoires`) n'apparaissent
    pas dans `comptes` — leur nombre est à déduire par l'appelant en
    comparant `actifs_total` à la somme des effectifs retenus.
    """
    if entrepot.connexion is None:
        raise ErreurExportTabulaire("entrepôt non ouvert")
    connexion = entrepot.connexion

    requete = """
        SELECT e.code_categorie, a.cog_commune
        FROM etablissement e
        LEFT JOIN adresse a
            ON a.type_porteur = 'ET'
           AND a.id_porteur = e.ege_id
           AND a.code_usage_adresse = ?
           AND a.rang = (
                SELECT MIN(a2.rang) FROM adresse a2
                WHERE a2.type_porteur = 'ET' AND a2.id_porteur = e.ege_id
                  AND a2.code_usage_adresse = ?
           )
        WHERE e.etat_objet = ?
    """
    lignes = connexion.execute(
        requete, (USAGE_ADRESSE_PRINCIPALE, USAGE_ADRESSE_PRINCIPALE, ETAT_ACTIF)).fetchall()

    comptes: Dict[Tuple[str, Optional[str]], int] = {}
    for code_categorie, cog_commune in lignes:
        if cog_commune is None:
            continue
        try:
            departement = departement_depuis_cog(cog_commune)
        except ErreurTerritoires:
            continue
        cle = (departement, code_categorie)
        comptes[cle] = comptes.get(cle, 0) + 1

    return comptes, len(lignes)


# ---------------------------------------------------------------------------
# Résolution des libellés et assemblage du tableau
# ---------------------------------------------------------------------------

def tableau_departement_categorie(
        entrepot: Entrepot) -> Tuple[List[LigneTableau], Diagnostics]:
    """Établissements actifs par département × catégorie, libellés résolus.

    Voir le docstring du module : le calcul lui-même vient du stub en
    attendant OOM-13. Cette fonction n'a rien de spécifique au stub — elle
    résout les libellés de catégorie (`nomenclatures`) et assemble le
    résultat final, et continuera de fonctionner à l'identique une fois le
    stub remplacé par l'appel réel.
    """
    comptes, actifs_total = _tableau_departement_categorie_stub(entrepot)

    lignes: List[LigneTableau] = []
    sans_categorie = 0
    categories_inconnues = 0
    for (departement, code_categorie), effectif in comptes.items():
        if code_categorie is None:
            sans_categorie += 1
            libelle = LIBELLE_CATEGORIE_ABSENTE
        else:
            try:
                libelle = resoudre_categorie(code_categorie)
            except CodeCategorieInconnu:
                categories_inconnues += 1
                libelle = f"[catégorie inconnue : {code_categorie}]"
        lignes.append(LigneTableau(departement, code_categorie, libelle, effectif))

    lignes.sort(key=lambda l: (l.code_departement, l.libelle_categorie))
    retenus = sum(l.effectif for l in lignes)
    diagnostics = Diagnostics(
        actifs_total=actifs_total,
        sans_departement_resolu=actifs_total - retenus,
        sans_categorie=sans_categorie,
        categories_inconnues=categories_inconnues,
    )
    return lignes, diagnostics


# ---------------------------------------------------------------------------
# Export CSV
# ---------------------------------------------------------------------------

def ecrire_csv(lignes: List[LigneTableau], chemin: Path) -> None:
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        graveur = csv.writer(f, delimiter=";")
        graveur.writerow(
            ["code_departement", "code_categorie", "libelle_categorie", "effectif"])
        for ligne in lignes:
            graveur.writerow([
                ligne.code_departement, ligne.code_categorie or "",
                ligne.libelle_categorie, ligne.effectif])


# ---------------------------------------------------------------------------
# Rapport de synthèse
# ---------------------------------------------------------------------------

def rapport_texte(entrepot: Entrepot, lignes: List[LigneTableau],
                  diagnostics: Diagnostics, chemin_csv: Path, duree_s: float) -> str:
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
        "",
        "-- Résultat produit --",
        f"CSV                      : {chemin_csv}",
        f"Lignes département×catégorie : {len(lignes)}",
        f"Établissements actifs (etat_objet={ETAT_ACTIF!r}) : {diagnostics.actifs_total}",
        f"    dont sans département résolu (pas d'adresse principale, ou "
        f"cog_commune non résolu) : {diagnostics.sans_departement_resolu}",
        f"    dont sans catégorie renseignée : {diagnostics.sans_categorie}",
        f"    dont catégorie hors référentiel : {diagnostics.categories_inconnues}",
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
    lignes, diagnostics = tableau_departement_categorie(entrepot)

    chemin_csv = dossier_sortie / "departement_categorie.csv"
    ecrire_csv(lignes, chemin_csv)

    duree_s = time.time() - debut
    texte = rapport_texte(entrepot, lignes, diagnostics, chemin_csv, duree_s)
    chemin_rapport = dossier_sortie / "rapport.txt"
    chemin_rapport.write_text(texte, encoding="utf-8")

    return {
        "chemin_csv": chemin_csv,
        "chemin_rapport": chemin_rapport,
        "lignes": lignes,
        "diagnostics": diagnostics,
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
