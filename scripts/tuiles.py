"""
tuiles.py — Archive PMTiles des établissements (OOM-111), entrée : contrat C.

Chaîne, dans le job `rendre` de `.github/workflows/pages.yml` :

    entrepôt ──export_geo.exporter──▶ <travail>/etablissements.geojson
             ──tippecanoe──────────▶ <travail>/etablissements.pmtiles
             ──contrôles (D6)──────▶ site/tuiles/etablissements.pmtiles

Le GeoJSON et l'archive sont produits HORS de `site/` (contrat C) ; l'archive
n'est recopiée dans `site/tuiles/` qu'une fois tous les contrôles passés. Un
contrôle en échec lève `ErreurTuiles`, sort en 1, et laisse la destination
intacte : aucune archive tronquée, trop lourde ou incomplète n'est publiée.
Ni le GeoJSON ni l'archive ne sont versionnés (D8).

PARAMÈTRES VERSIONNÉS — tout ce qui détermine l'archive est dans ce fichier :
la version de tippecanoe (tag ET commit, l'installation compile ce commit
précis et vérifie son identité), la couche, les zooms, la règle d'éclaircissement
aux petits zooms, les propriétés conservées (celles du contrat C, ni plus ni
moins) et le nombre de fils de tippecanoe. À paramètres et millésime égaux,
l'archive est identique octet pour octet : le chemin des fichiers passés à
tippecanoe est lui aussi fixé par le workflow, parce que tippecanoe recopie sa
ligne de commande dans les métadonnées de l'archive.

Des points n'ont pas de géométrie à simplifier : la « simplification » se
résume ici à l'éclaircissement des petits zooms (`--drop-densest-as-needed`),
qui écarte les points les plus denses d'une tuile trop lourde. Au zoom
maximal, tous les points sont présents.

CONTRÔLES DE L'ARCHIVE (D6), stdlib seule — lecture de l'en-tête PMTiles v3
(127 octets, petit-boutiste) et des métadonnées JSON :

- taille ≤ `PLAFOND_OCTETS` (100 000 000 o : sous le plafond de 100 Mio d'un
  fichier sur GitHub Pages), vérifiée en premier ;
- signature `PMTiles`, version 3, tuiles vectorielles (MVT) ;
- sections dans le fichier et données de tuiles finissant exactement à la fin
  du fichier — une archive tronquée échoue ici ;
- couche `etablissements` présente, avec toutes les propriétés du contrat C ;
- nombre de points de la couche (`tilestats`) égal aux points localisés
  écrits par `export_geo` : aucun point perdu entre GeoJSON et archive.

Commandes :

    python scripts/tuiles.py version
        tag et commit de tippecanoe, pour l'installation et sa clé de cache
    python scripts/tuiles.py generer <base.sqlite> --travail <dossier>
                                     --archive site/tuiles/etablissements.pmtiles
                                     [--resume $GITHUB_STEP_SUMMARY]
    python scripts/tuiles.py verifier <archive.pmtiles> [--points N]

Aucune dépendance tierce (tippecanoe est un exécutable externe, installé par
le workflow). Compatible Python 3.9+.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

TIPPECANOE_VERSION = "2.79.0"
TIPPECANOE_COMMIT = "68ab8dcc229f95b8b25877697d5e8d66783af503"
TIPPECANOE_DEPOT = "https://github.com/felt/tippecanoe.git"

COUCHE = "etablissements"
ZOOM_MIN = 0
ZOOM_MAX = 14
# Propriétés du contrat C (export_geo) : toutes conservées, aucune autre.
PROPRIETES = ("finess", "nom", "categorie", "dep", "lien", "score_ban", "etat")
# Fils de tippecanoe fixés : l'archive ne dépend pas du nombre de cœurs du runner.
FILS = 4
PLAFOND_OCTETS = 100_000_000
NOM_ARCHIVE = "etablissements.pmtiles"
NOM_GEOJSON = "etablissements.geojson"
ATTRIBUTION = "FINESS, ministère chargé de la Santé (data.gouv.fr)"

TAILLE_ENTETE = 127
_FORMAT_ENTETE = "<7sB" + "Q" * 11 + "BBBBBB" + "iiii" + "B" + "ii"
_CHAMPS_ENTETE = (
    "signature", "version",
    "racine_offset", "racine_longueur", "metadonnees_offset", "metadonnees_longueur",
    "feuilles_offset", "feuilles_longueur", "tuiles_offset", "tuiles_longueur",
    "tuiles_adressees", "entrees_tuiles", "contenus_tuiles",
    "groupee", "compression_interne", "compression_tuiles", "type_tuiles",
    "zoom_min", "zoom_max",
    "lon_min_e7", "lat_min_e7", "lon_max_e7", "lat_max_e7",
    "zoom_centre", "lon_centre_e7", "lat_centre_e7",
)
COMPRESSION_AUCUNE, COMPRESSION_GZIP = 1, 2
TYPE_MVT = 1

__all__ = ["generer", "verifier_archive", "lire_entete", "lire_metadonnees",
           "arguments_tippecanoe", "ErreurTuiles"]


class ErreurTuiles(Exception):
    """Archive impropre à la publication, ou étape de la chaîne en échec."""


def arguments_tippecanoe(geojson: str, archive: str, millesime: str) -> List[str]:
    """Arguments de tippecanoe (sans l'exécutable) : la seule source des
    paramètres de génération."""
    arguments = [
        "--output=" + archive,
        "--force",
        "--quiet",
        "--layer=" + COUCHE,
        "--name=" + COUCHE,
        "--description=Établissements FINESS, millésime " + millesime,
        "--attribution=" + ATTRIBUTION,
        f"--minimum-zoom={ZOOM_MIN}",
        f"--maximum-zoom={ZOOM_MAX}",
        "--drop-densest-as-needed",
    ]
    arguments += ["--include=" + p for p in PROPRIETES]
    arguments.append(geojson)
    return arguments


def lire_entete(chemin: Path) -> Dict[str, object]:
    with open(chemin, "rb") as f:
        octets = f.read(TAILLE_ENTETE)
    if len(octets) < TAILLE_ENTETE:
        raise ErreurTuiles(f"{chemin} : {len(octets)} octet(s), moins que l'en-tête PMTiles "
                           f"({TAILLE_ENTETE})")
    entete = dict(zip(_CHAMPS_ENTETE, struct.unpack(_FORMAT_ENTETE, octets)))
    if entete["signature"] != b"PMTiles":
        raise ErreurTuiles(f"{chemin} : signature {entete['signature']!r}, pas une archive "
                           f"PMTiles")
    if entete["version"] != 3:
        raise ErreurTuiles(f"{chemin} : PMTiles version {entete['version']}, 3 attendue")
    return entete


def lire_metadonnees(chemin: Path, entete: Dict[str, object]) -> Dict[str, object]:
    with open(chemin, "rb") as f:
        f.seek(entete["metadonnees_offset"])
        brut = f.read(entete["metadonnees_longueur"])
    compression = entete["compression_interne"]
    if compression == COMPRESSION_GZIP:
        brut = gzip.decompress(brut)
    elif compression != COMPRESSION_AUCUNE:
        raise ErreurTuiles(f"{chemin} : compression interne {compression} non lisible "
                           f"(1 aucune, 2 gzip)")
    try:
        return json.loads(brut.decode("utf-8"))
    except ValueError as erreur:
        raise ErreurTuiles(f"{chemin} : métadonnées illisibles ({erreur})") from erreur


def _points_de_la_couche(metadonnees: Dict[str, object]) -> Optional[int]:
    for couche in (metadonnees.get("tilestats") or {}).get("layers", []):
        if couche.get("layer") == COUCHE:
            return couche.get("count")
    return None


def verifier_archive(chemin: Path, points_attendus: Optional[int] = None,
                     plafond: int = PLAFOND_OCTETS) -> Dict[str, object]:
    """Contrôle l'archive (voir l'en-tête du module) ; lève `ErreurTuiles` au
    premier défaut. Retourne taille, empreinte, points, zooms et nombre de tuiles."""
    chemin = Path(chemin)
    taille = chemin.stat().st_size
    if taille > plafond:
        raise ErreurTuiles(f"archive de {taille} octets, au-delà du plafond de {plafond} "
                           f"octets (fichier GitHub Pages) : rien n'est publié")
    entete = lire_entete(chemin)
    for section in ("racine", "metadonnees", "feuilles", "tuiles"):
        fin = entete[section + "_offset"] + entete[section + "_longueur"]
        if fin > taille:
            raise ErreurTuiles(f"archive tronquée : section {section} jusqu'à l'octet {fin}, "
                               f"fichier de {taille} octets")
    if entete["tuiles_offset"] + entete["tuiles_longueur"] != taille:
        raise ErreurTuiles(f"archive tronquée ou incohérente : données de tuiles finissant à "
                           f"l'octet {entete['tuiles_offset'] + entete['tuiles_longueur']}, "
                           f"fichier de {taille} octets")
    if entete["type_tuiles"] != TYPE_MVT:
        raise ErreurTuiles(f"type de tuiles {entete['type_tuiles']}, MVT ({TYPE_MVT}) attendu")
    if entete["tuiles_adressees"] < 1:
        raise ErreurTuiles("archive sans aucune tuile")
    metadonnees = lire_metadonnees(chemin, entete)
    couches = {c.get("id"): c for c in metadonnees.get("vector_layers", [])}
    if COUCHE not in couches:
        raise ErreurTuiles(f"couche {COUCHE!r} absente (couches : {sorted(couches)})")
    manquantes = [p for p in PROPRIETES if p not in (couches[COUCHE].get("fields") or {})]
    if manquantes:
        raise ErreurTuiles(f"propriétés du contrat C absentes de la couche {COUCHE!r} : "
                           f"{manquantes}")
    points = _points_de_la_couche(metadonnees)
    if points is None:
        raise ErreurTuiles(f"nombre de points de la couche {COUCHE!r} absent des métadonnées "
                           f"(tilestats)")
    if points_attendus is not None and points != points_attendus:
        raise ErreurTuiles(f"{points} point(s) dans l'archive pour {points_attendus} "
                           f"localisé(s) dans le GeoJSON")
    empreinte = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            empreinte.update(bloc)
    return {
        "octets": taille,
        "sha256": empreinte.hexdigest(),
        "points": points,
        "zoom_min": entete["zoom_min"],
        "zoom_max": entete["zoom_max"],
        "tuiles": entete["tuiles_adressees"],
        "generateur": metadonnees.get("generator"),
    }


def generer(base: Path, travail: Path, archive: Path,
            tippecanoe: Sequence[str] = ("tippecanoe",),
            plafond: int = PLAFOND_OCTETS) -> Dict[str, object]:
    """Entrepôt → GeoJSON → archive contrôlée, recopiée dans `archive`. En cas
    d'échec, `archive` n'est ni créée ni modifiée."""
    from entrepot import Entrepot
    import export_geo

    base, travail, archive = Path(base), Path(travail), Path(archive)
    if not base.is_file():
        raise ErreurTuiles(f"entrepôt introuvable : {base}")
    travail.mkdir(parents=True, exist_ok=True)
    geojson, produite = travail / NOM_GEOJSON, travail / NOM_ARCHIVE
    if produite.exists():
        produite.unlink()

    debut = time.monotonic()
    try:
        with Entrepot(base) as entrepot:
            geo = export_geo.exporter(entrepot, geojson)
    except export_geo.ErreurExportGeo as erreur:
        raise ErreurTuiles(f"export_geo : {erreur}") from erreur
    duree_geo = time.monotonic() - debut

    debut = time.monotonic()
    commande = list(tippecanoe) + arguments_tippecanoe(
        geojson.as_posix(), produite.as_posix(), geo["millesime"])
    environnement = dict(os.environ, TIPPECANOE_MAX_THREADS=str(FILS))
    try:
        retour = subprocess.run(commande, env=environnement)
    except OSError as erreur:
        raise ErreurTuiles(f"tippecanoe introuvable ou non exécutable : {erreur}") from erreur
    if retour.returncode != 0:
        raise ErreurTuiles(f"tippecanoe a échoué (code {retour.returncode})")
    if not produite.is_file():
        raise ErreurTuiles(f"tippecanoe n'a pas écrit {produite}")
    duree_tuiles = time.monotonic() - debut

    controle = verifier_archive(produite, points_attendus=geo["localises"], plafond=plafond)
    archive.parent.mkdir(parents=True, exist_ok=True)
    partiel = archive.with_name(archive.name + ".partiel")
    try:
        shutil.copyfile(produite, partiel)
        os.replace(partiel, archive)
    finally:
        if partiel.exists():
            partiel.unlink()
    return {"geo": geo, "archive": controle, "chemin": str(archive),
            "duree_geojson_s": duree_geo, "duree_tippecanoe_s": duree_tuiles}


def resume_markdown(bilan: Dict[str, object]) -> str:
    geo, archive = bilan["geo"], bilan["archive"]
    return "\n".join([
        "",
        "#### Archive de tuiles (OOM-111)",
        "",
        f"- Archive : `{bilan['chemin']}` — **{archive['octets']} octets** "
        f"({archive['octets'] / 1_000_000:.1f} Mo, plafond {PLAFOND_OCTETS} o)",
        f"- Empreinte SHA-256 : `{archive['sha256']}`",
        f"- Points dans la couche `{COUCHE}` : **{archive['points']}** "
        f"(= localisés d'export_geo), zooms {archive['zoom_min']}–{archive['zoom_max']}, "
        f"{archive['tuiles']} tuiles",
        f"- Générateur : {archive['generateur']} (épinglé {TIPPECANOE_VERSION}, "
        f"commit `{TIPPECANOE_COMMIT[:12]}`)",
        f"- GeoJSON (hors site, non publié) : {geo['octets']} octets, millésime "
        f"{geo['millesime']}",
        "",
        "| Compteur export_geo | Valeur |",
        "|---|---:|",
        f"| établissements lus (`total`) | {geo['total']} |",
        f"| localisés | {geo['localises']} |",
        f"| non localisés | {geo['non_localises']} |",
        f"| dont `sans_coordonnees` | {geo['sans_coordonnees']} |",
        f"| dont `coordonnees_invalides` (hors WGS84, ex. Lambert 93) | "
        f"{geo['coordonnees_invalides']} |",
        "",
        f"Durées : GeoJSON {bilan['duree_geojson_s']:.0f} s, tippecanoe "
        f"{bilan['duree_tippecanoe_s']:.0f} s",
        "",
    ])


def _principal(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    analyseur = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    commandes = analyseur.add_subparsers(dest="commande", required=True)
    commandes.add_parser("version", help="tag et commit épinglés de tippecanoe")
    g = commandes.add_parser("generer", help="entrepôt → GeoJSON → archive contrôlée")
    g.add_argument("base", type=Path)
    g.add_argument("--travail", type=Path, required=True,
                   help="dossier hors de site/ pour le GeoJSON et l'archive brute")
    g.add_argument("--archive", type=Path, required=True, help="archive publiée")
    g.add_argument("--tippecanoe", default="tippecanoe", help="exécutable de tippecanoe")
    g.add_argument("--plafond", type=int, default=PLAFOND_OCTETS, help="taille maximale (o)")
    g.add_argument("--resume", type=Path, help="fichier markdown où ajouter le résumé")
    v = commandes.add_parser("verifier", help="contrôler une archive existante")
    v.add_argument("archive", type=Path)
    v.add_argument("--points", type=int, help="nombre de points attendu")
    v.add_argument("--plafond", type=int, default=PLAFOND_OCTETS)
    arguments = analyseur.parse_args(argv)

    if arguments.commande == "version":
        print(TIPPECANOE_VERSION, TIPPECANOE_COMMIT)
        return 0
    try:
        if arguments.commande == "verifier":
            controle = verifier_archive(arguments.archive, arguments.points, arguments.plafond)
            print(json.dumps(controle, ensure_ascii=False, indent=2))
            return 0
        bilan = generer(arguments.base, arguments.travail, arguments.archive,
                        tippecanoe=(arguments.tippecanoe,), plafond=arguments.plafond)
    except ErreurTuiles as erreur:
        print(f"tuiles : {erreur}", file=sys.stderr)
        return 1
    texte = resume_markdown(bilan)
    print(texte)
    if arguments.resume:
        with open(arguments.resume, "a", encoding="utf-8") as f:
            f.write(texte + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(_principal())
