"""
export_front.py — Export de l'entrepôt en JSON statique pour le front simple (OOM-19).

Produit `etablissements.json` (et `meta.json`) à partir d'un entrepôt SQLite
déjà chargé (`entrepot.py`/`chargement.py`, couche 2). Ces fichiers sont
consommés tels quels par `front/liste.html` (OOM-20) — pas de serveur HTTP,
pas d'API : cadrage tranché dans OOM-18 (18/08).

PORTÉE ACTUELLE — codes bruts, pas encore de libellés résolus
-----------------------------------------------------------------
Ce module ne résout ni le département (`cog_commune` -> code département,
OOM-11) ni le libellé de catégorie (`code_categorie` -> libellé lisible,
OOM-12) : ces deux modules sont écrits séparément, dans le même arbre de
travail, au moment où ce fichier est écrit. Les exposer ici en parallèle
créerait une collision directe sur les mêmes fichiers. `code_categorie` et
`cog_commune` sont donc exposés verbatim pour l'instant.

`etat_objet` fait exception : c'est un champ à exactement deux valeurs
('A'/'I', cf. `docs/architecture/03_SCHEMA_PIVOT.md` — jamais 300 comme la
catégorie), traduit ici en toutes lettres sans passer par une nomenclature
externe. Aucun recouvrement avec OOM-12.

Le contrat JSON est conçu pour ne pas changer de forme une fois OOM-11/OOM-12
branchés : `code_departement`/`libelle_categorie` viendront s'ajouter aux
côtés des champs bruts, sans renommer ni retirer les clés existantes — le
front qui les consomme n'aura pas à changer pour en profiter.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from entrepot import Entrepot

__all__ = ["etablissements_bruts", "exporter", "ErreurExportFront"]

# '03' = adresse principale, cf. docs/architecture/03_SCHEMA_PIVOT.md ligne
# consacrée à adresse.code_usage_adresse ('03' principale, '04'/'06' secondaires).
USAGE_ADRESSE_PRINCIPALE = "03"

# Deux valeurs seulement, documentées dans 03_SCHEMA_PIVOT.md : A 56 219 (EJ) /
# 104 699 (ET) actifs, I le reste. Ce n'est pas une nomenclature à résoudre
# comme la catégorie (300 valeurs, OOM-12) : elle est fixée ici sans référence
# externe.
ETAT_OBJET_LIBELLES = {"A": "Actif", "I": "Inactif"}


class ErreurExportFront(Exception):
    """Entrepôt non ouvert, ou export impossible."""


def _libelle_etat(code: Optional[str]) -> str:
    if not code:
        return "[état absent]"
    return ETAT_OBJET_LIBELLES.get(code, f"[code état non résolu : {code}]")


def etablissements_bruts(entrepot: Entrepot) -> List[Dict[str, object]]:
    """Une ligne par établissement, avec l'adresse principale s'il en a une.

    Un établissement sans adresse d'usage '03' apparaît quand même, avec
    `cog_commune`/`code_postal` à `None` — jamais absent en silence (D6).
    S'il existe plusieurs adresses '03' pour un même établissement (anomalie
    de données, non attendue mais non exclue par le schéma), seule celle du
    rang le plus faible est retenue, pour ne jamais dupliquer une ligne.
    """
    if entrepot.connexion is None:
        raise ErreurExportFront("entrepôt non ouvert")
    connexion = entrepot.connexion

    requete = """
        SELECT e.num_finess_et, e.nom_court, e.nom_long, e.code_categorie,
               e.etat_objet, a.cog_commune, a.code_postal
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
        ORDER BY e.num_finess_et
    """
    lignes = connexion.execute(
        requete, (USAGE_ADRESSE_PRINCIPALE, USAGE_ADRESSE_PRINCIPALE)).fetchall()

    resultat = []
    for num_finess_et, nom_court, nom_long, code_categorie, etat_objet, \
            cog_commune, code_postal in lignes:
        resultat.append({
            "num_finess_et": num_finess_et,
            "nom": nom_court or nom_long,
            "code_categorie": code_categorie,
            "etat_objet": etat_objet,
            "etat_libelle": _libelle_etat(etat_objet),
            "cog_commune": cog_commune,
            "code_postal": code_postal,
        })
    return resultat


def exporter(entrepot: Entrepot, dossier_sortie: Path) -> Dict[str, object]:
    """Écrit `etablissements.json` et `meta.json` dans `dossier_sortie`.

    Retourne le contenu de `meta.json`, pour affichage par l'appelant (CLI).
    """
    dossier_sortie = Path(dossier_sortie)
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    etablissements = etablissements_bruts(entrepot)
    sans_adresse_principale = sum(
        1 for e in etablissements if e["cog_commune"] is None)

    (dossier_sortie / "etablissements.json").write_text(
        json.dumps(etablissements, ensure_ascii=False, indent=2), encoding="utf-8")

    meta = {
        "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "nombre_etablissements": len(etablissements),
        "sans_adresse_principale": sans_adresse_principale,
        # Faux tant qu'OOM-11/OOM-12 ne sont pas branchés ici : le front doit
        # pouvoir savoir s'il affiche des codes bruts ou des libellés résolus.
        "departement_resolu": False,
        "libelles_categorie_resolus": False,
    }
    (dossier_sortie / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return meta


if __name__ == "__main__":
    import argparse

    analyseur = argparse.ArgumentParser(
        description="Export JSON de l'entrepôt pour le front simple (OOM-19).")
    analyseur.add_argument("base", type=Path, help="fichier de l'entrepôt SQLite")
    analyseur.add_argument("--sortie", type=Path, default=Path("front/data"))
    arguments = analyseur.parse_args()

    with Entrepot(arguments.base) as entrepot:
        meta = exporter(entrepot, arguments.sortie)
    print(f"Export écrit dans {arguments.sortie} : "
          f"{meta['nombre_etablissements']} établissement(s), "
          f"{meta['sans_adresse_principale']} sans adresse principale.")
