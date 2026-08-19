"""
export_front.py — Export de l'entrepôt en JSON statique pour le front simple (OOM-19).

Produit `etablissements.json`, `indicateur.json`, `activites.json` et
`meta.json` à partir d'un entrepôt SQLite déjà chargé (`entrepot.py`/
`chargement.py`, couche 2). Ces fichiers sont consommés tels quels par
`front/liste.html` (OOM-20, OOM-28) et `front/indicateur.html` (OOM-21) — pas
de serveur HTTP, pas d'API : cadrage tranché dans OOM-18 (18/08).

ACTIVITÉS PAR ÉTABLISSEMENT — activites.json (OOM-27)
-----------------------------------------------------------------
`activites.json` regroupe les activités FINESS-Activités de niveau `ET`
(rattachées à un établissement, par opposition au niveau `EJ`, rattaché à
l'entité juridique — hors périmètre de ce front centré établissement) sous
la forme `{num_finess_et: [activité, ...]}`. Chaque activité porte son
`code_nature` brut : aucune nomenclature versionnée ne couvre encore ce
domaine (seul `categorie_etablissement` l'est, via `nomenclatures.py`), donc
`libelle_nature` vaut toujours `None` — même politique de non-invention de
libellé que pour une catégorie hors référentiel, jamais un code tu ou un
plantage. Chaque activité porte aussi ses `capacites` (nombre, unité,
statut, tous en codes bruts pour la même raison).

Seuls les établissements ayant au moins une activité `ET` apparaissent comme
clé du dictionnaire — absence de clé = aucune activité, pas un échec
silencieux : le total d'établissements avec activités est compté
explicitement dans `meta.json` (`etablissements_avec_activites`), donc jamais
une omission qui se confond avec un oubli.

`indicateur.json` reprend `indicateurs.indicateur_departement_categorie`
(couche 5, OOM-13) telle quelle, triée dans le même ordre que
`export_tabulaire.ecrire_csv` (OOM-14) : mêmes chiffres, même tri, pour que
le front d'analyse (OOM-21) corresponde exactement au CSV déjà restitué.

LIBELLÉS RÉSOLUS — département et catégorie
-----------------------------------------------------------------
`cog_commune` est résolu en `code_departement` (`territoires.departement_depuis_cog`,
OOM-11) et `code_categorie` en `libelle_categorie` (`nomenclatures.resoudre_categorie`,
OOM-12). Même règle de non-résolution qu'`indicateurs.py` (D6) : un code
absent, invalide ou une adresse manquante ne fait pas planter l'export ni
n'invente de valeur — le champ résolu correspondant vaut `None` et la ligne
reste exportée avec son code brut, que le front peut toujours afficher en
repli. `meta.json` compte les lignes non résolues pour que ce ne soit jamais
silencieux à l'échelle de l'export.

`etat_objet` fait exception : c'est un champ à exactement deux valeurs
('A'/'I', cf. `docs/architecture/03_SCHEMA_PIVOT.md` — jamais 300 comme la
catégorie), traduit ici en toutes lettres sans passer par une nomenclature
externe.

Le contrat JSON conserve les champs bruts (`code_categorie`, `cog_commune`)
aux côtés des champs résolus (`libelle_categorie`, `code_departement`) : ni
renommage ni retrait des clés existantes depuis la portée initiale.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from entrepot import Entrepot
from indicateurs import ErreurIndicateurs, indicateur_departement_categorie
from nomenclatures import CodeCategorieInconnu, resoudre_categorie
from territoires import ErreurTerritoires, departement_depuis_cog

__all__ = ["etablissements_bruts", "indicateur_json", "activites_par_etablissement",
           "exporter", "ErreurExportFront"]

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


def etablissements_bruts(
        entrepot: Entrepot,
        categories: Optional[Dict[str, str]] = None) -> List[Dict[str, object]]:
    """Une ligne par établissement, avec l'adresse principale s'il en a une.

    Un établissement sans adresse d'usage '03' apparaît quand même, avec
    `cog_commune`/`code_postal` à `None` — jamais absent en silence (D6).
    S'il existe plusieurs adresses '03' pour un même établissement (anomalie
    de données, non attendue mais non exclue par le schéma), seule celle du
    rang le plus faible est retenue, pour ne jamais dupliquer une ligne.

    `categories` permet d'injecter un référentiel déjà chargé (tests, appel
    en masse évitant de recharger le CSV à chaque ligne) ; à défaut, le
    référentiel par défaut de `nomenclatures` est utilisé et mis en cache.
    `code_departement`/`libelle_categorie` valent `None` quand la résolution
    échoue (cog_commune/code_categorie absent ou non reconnu) — voir la note
    de module sur la résolution des libellés.
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
        code_departement = None
        if cog_commune is not None:
            try:
                code_departement = departement_depuis_cog(cog_commune)
            except ErreurTerritoires:
                code_departement = None

        libelle_categorie = None
        if code_categorie is not None:
            try:
                libelle_categorie = resoudre_categorie(code_categorie, categories=categories)
            except CodeCategorieInconnu:
                libelle_categorie = None

        resultat.append({
            "num_finess_et": num_finess_et,
            "nom": nom_court or nom_long,
            "code_categorie": code_categorie,
            "libelle_categorie": libelle_categorie,
            "etat_objet": etat_objet,
            "etat_libelle": _libelle_etat(etat_objet),
            "cog_commune": cog_commune,
            "code_postal": code_postal,
            "code_departement": code_departement,
        })
    return resultat


def indicateur_json(entrepot: Entrepot) -> List[Dict[str, object]]:
    """Table département × catégorie (OOM-13), une ligne par case non vide.

    Même calcul, même tri (`Resultat.lignes_triees`) que le CSV d'OOM-14
    (`export_tabulaire.ecrire_csv`) : le front d'analyse (OOM-21) doit
    retrouver exactement ces chiffres. Lève `ErreurExportFront` si
    l'entrepôt n'est pas ouvert (même contrat que `etablissements_bruts`).
    """
    try:
        resultat = indicateur_departement_categorie(entrepot)
    except ErreurIndicateurs as erreur:
        raise ErreurExportFront(str(erreur)) from erreur
    return [
        {"code_departement": departement, "libelle_categorie": categorie, "effectif": effectif}
        for departement, categorie, effectif in resultat.lignes_triees()
    ]


def activites_par_etablissement(entrepot: Entrepot) -> Dict[str, List[Dict[str, object]]]:
    """Activités de niveau `ET`, groupées par `num_finess_et`, capacités incluses.

    Voir la note de module sur `activites.json` pour le contrat exact (clés
    absentes = aucune activité, `libelle_nature` toujours `None` en l'absence
    de nomenclature). Lève `ErreurExportFront` si l'entrepôt n'est pas ouvert,
    même contrat que `etablissements_bruts`.
    """
    if entrepot.connexion is None:
        raise ErreurExportFront("entrepôt non ouvert")
    connexion = entrepot.connexion

    capacites_par_activite: Dict[str, List[Dict[str, object]]] = {}
    requete_capacites = """
        SELECT activite_ae_id, nombre, code_unite_mesure, code_statut_capacite
        FROM capacite
        ORDER BY activite_ae_id, rang
    """
    for activite_ae_id, nombre, code_unite_mesure, code_statut_capacite in \
            connexion.execute(requete_capacites).fetchall():
        capacites_par_activite.setdefault(activite_ae_id, []).append({
            "nombre": nombre,
            "code_unite_mesure": code_unite_mesure,
            "code_statut_capacite": code_statut_capacite,
        })

    requete_activites = """
        SELECT activite_ae_id, num_finess_et, code_nature,
               code_type_activite_smsse, etat_objet
        FROM activite
        WHERE niveau = 'ET' AND num_finess_et IS NOT NULL
        ORDER BY num_finess_et, activite_ae_id
    """
    resultat: Dict[str, List[Dict[str, object]]] = {}
    for activite_ae_id, num_finess_et, code_nature, code_type_activite_smsse, etat_objet in \
            connexion.execute(requete_activites).fetchall():
        resultat.setdefault(num_finess_et, []).append({
            "activite_ae_id": activite_ae_id,
            "code_nature": code_nature,
            "libelle_nature": None,
            "code_type_activite_smsse": code_type_activite_smsse,
            "etat_objet": etat_objet,
            "etat_libelle": _libelle_etat(etat_objet),
            "capacites": capacites_par_activite.get(activite_ae_id, []),
        })
    return resultat


def exporter(entrepot: Entrepot, dossier_sortie: Path) -> Dict[str, object]:
    """Écrit `etablissements.json`, `indicateur.json` et `meta.json` dans
    `dossier_sortie`.

    Retourne le contenu de `meta.json`, pour affichage par l'appelant (CLI).
    """
    dossier_sortie = Path(dossier_sortie)
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    etablissements = etablissements_bruts(entrepot)
    sans_adresse_principale = sum(
        1 for e in etablissements if e["cog_commune"] is None)
    departement_non_resolu = sum(
        1 for e in etablissements
        if e["cog_commune"] is not None and e["code_departement"] is None)
    categorie_non_resolue = sum(
        1 for e in etablissements
        if e["code_categorie"] is not None and e["libelle_categorie"] is None)

    (dossier_sortie / "etablissements.json").write_text(
        json.dumps(etablissements, ensure_ascii=False, indent=2), encoding="utf-8")

    indicateur = indicateur_json(entrepot)
    (dossier_sortie / "indicateur.json").write_text(
        json.dumps(indicateur, ensure_ascii=False, indent=2), encoding="utf-8")

    activites = activites_par_etablissement(entrepot)
    (dossier_sortie / "activites.json").write_text(
        json.dumps(activites, ensure_ascii=False, indent=2), encoding="utf-8")
    activites_total = sum(len(lignes) for lignes in activites.values())

    meta = {
        "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "nombre_etablissements": len(etablissements),
        "sans_adresse_principale": sans_adresse_principale,
        "departement_resolu": True,
        "libelles_categorie_resolus": True,
        # Comptent les lignes où le champ résolu n'a pas pu être produit à
        # partir d'un code brut présent — jamais silencieux à l'échelle de
        # l'export (D6), même si `departement_resolu`/`libelles_categorie_resolus`
        # signalent que la résolution est globalement active.
        "departement_non_resolu": departement_non_resolu,
        "categorie_non_resolue": categorie_non_resolue,
        "indicateur_lignes": len(indicateur),
        # OOM-27 : nature d'activité non couverte par une nomenclature à ce
        # jour (voir note de module) — comptée explicitement, jamais silencieuse.
        "etablissements_avec_activites": len(activites),
        "activites_total": activites_total,
        "libelles_nature_resolus": False,
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
          f"{meta['sans_adresse_principale']} sans adresse principale, "
          f"{meta['indicateur_lignes']} ligne(s) d'indicateur département×catégorie, "
          f"{meta['activites_total']} activité(s) sur "
          f"{meta['etablissements_avec_activites']} établissement(s).")
