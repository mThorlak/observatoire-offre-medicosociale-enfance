"""
export_geo.py — Couche 6 (restitution) : GeoJSON des établissements (OOM-110).

Projette en GeoJSON (RFC 7946) les coordonnées déjà présentes dans l'entrepôt,
sans rien géocoder : un point par établissement localisé, placé à l'adresse
principale de l'ET (usage '03', même règle qu'`export_front.etablissements_bruts`).
Le fichier sert d'entrée à tippecanoe (OOM-111) ; il n'est ni versionné ni
publié (D8) — 175 000 points feraient environ 30 Mo.

CONTRAT C — posé par OOM-110, consommé par OOM-111, OOM-112 et OOM-113
-----------------------------------------------------------------
    exporter(entrepot, chemin_sortie,
             lignes_par_sous_page=LIGNES_PAR_SOUS_PAGE) -> dict

Écrit dans `chemin_sortie` une `FeatureCollection` de `Point`, coordonnées
`[longitude, latitude]` WGS84, avec le membre étranger `millesime` (D5).
Propriétés de chaque point :

    finess      str         numéro FINESS de l'établissement
    nom         str|None    nom court, à défaut nom long
    categorie   str|None    code catégorie brut (le libellé est une jointure)
    dep         str         code de la page départementale, en texte (`01`,
                            `2A`, `971`…), `indetermine` si le département est
                            non résolu ou hors référentiel — même règle que le
                            site (`export_html.page_de`)
    lien        str         `departement/<code>/<n>.html#et-<finess>`, relatif
                            à la racine du site : la sous-page que rend
                            `export_html` avec la même borne
    score_ban   float|str|None
                            score d'appariement BAN, nombre s'il se lit comme
                            tel, sinon le texte brut, `None` s'il est absent
    etat        str         `actif` ou `fermé` (`indicateurs.etat_objet_actif`)

Dictionnaire retourné :

    localises              int   points écrits
    non_localises          int   établissements exclus, jamais placés à une
                                 position par défaut (D6) : sans coordonnées,
                                 ou coordonnées hors du domaine WGS84
    sans_coordonnees       int   dont : `coordonnee_x`/`coordonnee_y` absentes
                                 (ou pas d'adresse principale)
    coordonnees_invalides  int   dont : coordonnées illisibles ou hors de
                                 [-180, 180] × [-90, 90] — par exemple du
                                 Lambert 93 égaré dans `coordonnee_*`
    total                  int   établissements lus (= lignes d'`etablissement`)
    par_departement        dict  {dep: {"localises", "non_localises"}}, une
                                 entrée par département du référentiel puis
                                 `indetermine`, même vide
    millesime              str   millésime unique de l'entrepôt
    lignes_par_sous_page   int   borne de pagination utilisée pour `lien`
    chemin                 str   fichier écrit
    octets                 int   taille du fichier écrit

Invariants bloquants (D6), vérifiés avant de publier le fichier :
`localises + non_localises = total`, somme de `par_departement` = total, et
total = nombre de lignes d'`etablissement` (aucun établissement dupliqué ni
perdu par la jointure). En cas d'échec, `ErreurExportGeo` est levée et
`chemin_sortie` n'est ni créé ni modifié : le fichier est écrit à côté puis
renommé.

PIÈGE — longitude = `coordonnee_x`, latitude = `coordonnee_y` (degrés WGS84).
Les `direction_*` sont du Lambert 93, intervertis : jamais lus ici (voir
CLAUDE.md). Une ligne dont les `coordonnee_*` ne sont pas des degrés est
exclue et comptée, jamais « réparée » depuis les `direction_*`.

LIEN — rattachement et pagination ne sont pas réimplémentés : le département
passe par `export_html.page_de`, la sous-page par
`export_html.numero_sous_page` appliqué au rang de l'établissement dans sa
page, dans le même ordre que le rendu (numéro FINESS croissant, celui
d'`etablissements_bruts`). Tous les établissements comptent dans ce rang,
localisés ou non, puisque tous ont leur ligne dans les sous-pages.

D1 — lecture par curseur et écriture en flux : ni la table ni la collection
ne sont tenues en mémoire, seuls les compteurs par département le sont.

EMPRISES (OOM-113) — cadrage des cartes départementales
-----------------------------------------------------------------
    emprises(entrepot, departements) -> {dep: {"localises": int,
                                               "emprise": [ouest, sud, est, nord] | None}}

Une entrée par code de `departements` puis `PAGE_INDETERMINEE`, même vide :
le rectangle englobant, en degrés WGS84, des points que `exporter` placerait
dans ce département (même requête, même rattachement, mêmes exclusions), et
leur nombre ; `None` si aucun n'est localisé. C'est sur ce rectangle
qu'`export_html` cadre la carte d'un département : le cadrage suit les
données publiées, sans référentiel géographique supplémentaire.

COUVERTURE (OOM-112) — bandeau de couverture des cartes
-----------------------------------------------------------------
    couverture(entrepot, departements) -> {"national": {…},
                                           "par_departement": {dep: {…}}}

Même parcours qu'`emprises` (même requête, même rattachement, mêmes
exclusions qu'`exporter`), mais tous les établissements comptent, localisés
ou non. Chaque entrée, nationale ou départementale (une par code de
`departements` puis `PAGE_INDETERMINEE`, même vide), porte :

    total                  int         établissements du périmètre
    localises              int         dont placés sur la carte
    non_localises          int         dont exclus = sans_coordonnees
                                       + coordonnees_invalides
    sans_coordonnees       int         mêmes définitions qu'`exporter`
    coordonnees_invalides  int
    part_localises         float|None  localises / total en pour cent, au
                                       dixième ; `None` si total = 0. Jamais
                                       100,0 s'il en manque un, jamais 0,0
                                       s'il y en a un (l'arrondi ne ment pas)

et, par département seulement, `emprise` (celle d'`emprises`). Invariants
bloquants (D6), `ErreurExportGeo` sinon : localises + non_localises = total
dans chaque entrée, somme des départements (indéterminé compris) = national,
national = nombre de lignes d'`etablissement`. C'est de là que viennent les
chiffres du bandeau des cartes : `export_html` les rend, sans les recalculer.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple, Union

from entrepot import Entrepot
from export_front import USAGE_ADRESSE_PRINCIPALE
from export_html import (LIGNES_PAR_SOUS_PAGE, PAGE_INDETERMINEE, ErreurExportHtml,
                         ancre_etablissement, chemin_sous_page, numero_sous_page, page_de)
from indicateurs import etat_objet_actif
from territoires import ErreurTerritoires, charger_departements, departement_depuis_cog

__all__ = ["exporter", "emprises", "couverture", "ErreurExportGeo", "ETAT_ACTIF", "ETAT_FERME"]

ETAT_ACTIF = "actif"
ETAT_FERME = "fermé"

# Même sélection d'adresse qu'`export_front.etablissements_bruts` (adresse
# principale '03', celle du plus petit rang), même ordre : c'est ce qui aligne
# le rang d'un établissement sur celui du rendu. Le test le vérifie contre un
# rendu réel.
_REQUETE = """
    SELECT e.num_finess_et, e.nom_court, e.nom_long, e.code_categorie, e.etat_objet,
           a.cog_commune, a.coordonnee_x, a.coordonnee_y, a.score_ban
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


class ErreurExportGeo(Exception):
    """Entrepôt impropre à l'export, ou invariant de comptage violé."""


def _millesime(entrepot: Entrepot) -> str:
    etat = entrepot.etat()
    if not etat["lots"]:
        raise ErreurExportGeo("entrepôt vide : aucun lot chargé")
    if not etat["coherent"]:
        raise ErreurExportGeo("entrepôt incohérent : " + " ; ".join(etat["motifs"]))
    return etat["millesimes"][0]


def _departement(cog_commune: Optional[str]) -> Optional[str]:
    if cog_commune is None:
        return None
    try:
        return departement_depuis_cog(cog_commune)
    except ErreurTerritoires:
        return None


def _degres(texte: Optional[str], limite: float) -> Optional[float]:
    """Le nombre lu dans `texte` s'il est un angle fini dans [-limite, limite],
    sinon `None`."""
    try:
        valeur = float(texte)
    except (TypeError, ValueError):
        return None
    return valeur if math.isfinite(valeur) and -limite <= valeur <= limite else None


def _position(x: Optional[str], y: Optional[str]) -> Tuple[str, Optional[Tuple[float, float]]]:
    """(`"sans"` | `"invalide"` | `"ok"`, [longitude, latitude] ou None)."""
    if x is None or y is None:
        return "sans", None
    longitude, latitude = _degres(x, 180.0), _degres(y, 90.0)
    if longitude is None or latitude is None:
        return "invalide", None
    return "ok", (longitude, latitude)


def _score(texte: Optional[str]) -> Union[float, str, None]:
    if texte is None:
        return None
    try:
        valeur = float(texte)
    except ValueError:
        return texte
    return valeur if math.isfinite(valeur) else texte


def _part(localises: int, total: int) -> Optional[float]:
    """Part des localisés en pour cent, au dixième — voir COUVERTURE."""
    if not total:
        return None
    part = round(100 * localises / total, 1)
    if part == 100.0 and localises < total:
        return 99.9
    if part == 0.0 and localises:
        return 0.1
    return part


def _entree_couverture() -> Dict[str, object]:
    return {"total": 0, "localises": 0, "non_localises": 0, "sans_coordonnees": 0,
            "coordonnees_invalides": 0, "part_localises": None}


def couverture(entrepot: Entrepot,
               departements: Mapping[str, str]) -> Dict[str, object]:
    """Compteurs de localisation, national et par page départementale, et
    emprise des points de chaque département — voir COUVERTURE en tête de
    module. Lecture par curseur : seuls des compteurs et quatre bornes par
    département sont tenus (D1)."""
    if entrepot.connexion is None:
        raise ErreurExportGeo("entrepôt non ouvert")
    national = _entree_couverture()
    par_departement: Dict[str, Dict[str, object]] = {
        code: dict(_entree_couverture(), emprise=None)
        for code in list(departements) + [PAGE_INDETERMINEE]}
    cles = {"sans": "sans_coordonnees", "invalide": "coordonnees_invalides", "ok": "localises"}
    curseur = entrepot.connexion.execute(
        _REQUETE, (USAGE_ADRESSE_PRINCIPALE, USAGE_ADRESSE_PRINCIPALE))
    for (_finess, _court, _long, _categorie, _etat, cog_commune, x, y, _score_ban) in curseur:
        statut, position = _position(x, y)
        entree = par_departement[page_de(_departement(cog_commune), departements)]
        for compteur in (national, entree):
            compteur["total"] += 1
            compteur[cles[statut]] += 1
            if position is None:
                compteur["non_localises"] += 1
        if position is None:
            continue
        longitude, latitude = position
        emprise = entree["emprise"]
        if emprise is None:
            entree["emprise"] = [longitude, latitude, longitude, latitude]
        else:
            emprise[0] = min(emprise[0], longitude)
            emprise[1] = min(emprise[1], latitude)
            emprise[2] = max(emprise[2], longitude)
            emprise[3] = max(emprise[3], latitude)

    attendu = entrepot.connexion.execute("SELECT COUNT(*) FROM etablissement").fetchone()[0]
    for nom, entree in [("national", national)] + list(par_departement.items()):
        if entree["localises"] + entree["non_localises"] != entree["total"]:
            raise ErreurExportGeo(
                f"couverture incohérente ({nom}) : {entree['localises']} localisé(s) + "
                f"{entree['non_localises']} non localisé(s) pour {entree['total']}")
        entree["part_localises"] = _part(entree["localises"], entree["total"])
    for cle in ("total", "localises", "sans_coordonnees", "coordonnees_invalides"):
        reparti = sum(entree[cle] for entree in par_departement.values())
        if reparti != national[cle]:
            raise ErreurExportGeo(
                f"couverture incohérente : {reparti} ({cle}) répartis par département pour "
                f"{national[cle]} au national")
    if national["total"] != attendu:
        raise ErreurExportGeo(
            f"couverture incohérente : {national['total']} établissement(s) lus pour "
            f"{attendu} dans la table etablissement")
    return {"national": national, "par_departement": par_departement}


def emprises(entrepot: Entrepot,
             departements: Mapping[str, str]) -> Dict[str, Dict[str, object]]:
    """Rectangle englobant et nombre des points localisés de chaque page
    départementale — voir EMPRISES en tête de module ; extrait de
    `couverture`, qui fait le parcours."""
    return {code: {"localises": entree["localises"], "emprise": entree["emprise"]}
            for code, entree in couverture(entrepot, departements)["par_departement"].items()}


def exporter(entrepot: Entrepot, chemin_sortie: Path,
             lignes_par_sous_page: int = LIGNES_PAR_SOUS_PAGE) -> Dict[str, object]:
    """Écrit le GeoJSON des établissements localisés — voir le contrat C en
    tête de module pour les propriétés et le dictionnaire retourné."""
    if entrepot.connexion is None:
        raise ErreurExportGeo("entrepôt non ouvert")
    try:
        numero_sous_page(0, lignes_par_sous_page)
    except ErreurExportHtml as erreur:
        raise ErreurExportGeo(str(erreur)) from erreur
    try:
        departements = charger_departements()
    except ErreurTerritoires as erreur:
        raise ErreurExportGeo(f"référentiel des départements : {erreur}") from erreur
    millesime = _millesime(entrepot)
    connexion = entrepot.connexion
    attendu = connexion.execute("SELECT COUNT(*) FROM etablissement").fetchone()[0]

    chemin_sortie = Path(chemin_sortie)
    chemin_sortie.parent.mkdir(parents=True, exist_ok=True)
    partiel = chemin_sortie.with_name(chemin_sortie.name + ".partiel")

    par_departement: Dict[str, Dict[str, int]] = {
        code: {"localises": 0, "non_localises": 0}
        for code in list(departements) + [PAGE_INDETERMINEE]}
    rangs = {code: 0 for code in par_departement}
    compteurs = {"sans": 0, "invalide": 0, "ok": 0}
    total = 0
    try:
        with open(partiel, "w", encoding="utf-8", newline="\n") as sortie:
            sortie.write('{"type":"FeatureCollection","millesime":'
                         + json.dumps(millesime, ensure_ascii=False) + ',"features":[')
            premier = True
            curseur = connexion.execute(
                _REQUETE, (USAGE_ADRESSE_PRINCIPALE, USAGE_ADRESSE_PRINCIPALE))
            for (num_finess_et, nom_court, nom_long, code_categorie, etat_objet,
                 cog_commune, x, y, score_ban) in curseur:
                total += 1
                dep = page_de(_departement(cog_commune), departements)
                rang = rangs[dep]
                rangs[dep] += 1
                statut, position = _position(x, y)
                compteurs[statut] += 1
                if position is None:
                    par_departement[dep]["non_localises"] += 1
                    continue
                par_departement[dep]["localises"] += 1
                lien = (chemin_sous_page(dep, numero_sous_page(rang, lignes_par_sous_page))
                        + "#" + ancre_etablissement(num_finess_et))
                point = {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": list(position)},
                    "properties": {
                        "finess": num_finess_et,
                        "nom": nom_court or nom_long,
                        "categorie": code_categorie,
                        "dep": dep,
                        "lien": lien,
                        "score_ban": _score(score_ban),
                        "etat": ETAT_ACTIF if etat_objet_actif(etat_objet) else ETAT_FERME,
                    },
                }
                sortie.write(("\n" if premier else ",\n")
                             + json.dumps(point, ensure_ascii=False, separators=(",", ":")))
                premier = False
            sortie.write("\n]}\n")

        localises = compteurs["ok"]
        non_localises = compteurs["sans"] + compteurs["invalide"]
        reparti = sum(n["localises"] + n["non_localises"] for n in par_departement.values())
        if localises + non_localises != total:
            raise ErreurExportGeo(
                f"comptage incohérent : {localises} localisé(s) + {non_localises} non "
                f"localisé(s) pour {total} établissement(s)")
        if reparti != total:
            raise ErreurExportGeo(
                f"répartition incohérente : {reparti} établissement(s) répartis par "
                f"département pour {total} au total")
        if total != attendu:
            raise ErreurExportGeo(
                f"lecture incohérente : {total} établissement(s) lus pour {attendu} dans "
                f"la table etablissement")
        os.replace(partiel, chemin_sortie)
    finally:
        if partiel.exists():
            partiel.unlink()

    return {
        "localises": localises,
        "non_localises": non_localises,
        "sans_coordonnees": compteurs["sans"],
        "coordonnees_invalides": compteurs["invalide"],
        "total": total,
        "par_departement": par_departement,
        "millesime": millesime,
        "lignes_par_sous_page": lignes_par_sous_page,
        "chemin": str(chemin_sortie),
        "octets": chemin_sortie.stat().st_size,
    }


if __name__ == "__main__":
    import argparse
    import sys

    analyseur = argparse.ArgumentParser(
        description="GeoJSON des établissements localisés, entrée de tippecanoe (OOM-110).")
    analyseur.add_argument("base", type=Path, help="fichier de l'entrepôt SQLite")
    analyseur.add_argument("--sortie", type=Path, required=True, help="fichier .geojson écrit")
    analyseur.add_argument("--lignes-par-sous-page", type=int, default=LIGNES_PAR_SOUS_PAGE,
                           help=f"borne de pagination du site visé par `lien` "
                                f"(défaut {LIGNES_PAR_SOUS_PAGE}, celle d'export_html)")
    arguments = analyseur.parse_args()

    if not arguments.base.is_file():
        sys.exit(f"entrepôt introuvable : {arguments.base}")
    try:
        with Entrepot(arguments.base) as entrepot:
            bilan = exporter(entrepot, arguments.sortie,
                             lignes_par_sous_page=arguments.lignes_par_sous_page)
    except ErreurExportGeo as erreur:
        sys.exit(f"export_geo : {erreur}")
    part = 100 * bilan["localises"] / bilan["total"] if bilan["total"] else 0.0
    print(f"GeoJSON écrit dans {bilan['chemin']} — millésime {bilan['millesime']}, "
          f"{bilan['octets'] / 1024:.1f} Ko")
    print(f"    {bilan['total']} établissement(s) : {bilan['localises']} localisé(s) "
          f"({part:.1f} %), {bilan['non_localises']} exclu(s) — "
          f"{bilan['sans_coordonnees']} sans coordonnées, "
          f"{bilan['coordonnees_invalides']} aux coordonnées hors WGS84")
    indetermine = bilan["par_departement"][PAGE_INDETERMINEE]
    print(f"    département indéterminé : {indetermine['localises']} localisé(s), "
          f"{indetermine['non_localises']} exclu(s)")
