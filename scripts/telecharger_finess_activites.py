"""
telecharger_finess_activites.py — Script d'acquisition automatisée (hors couches).

Récupère l'extrait FINESS-Activités quotidien publié par l'Agence du
Numérique en Santé sur data.gouv.fr, vérifie son intégrité contre le
checksum et la taille publiés par la plateforme, et écrit un fichier de
métadonnées à côté du fichier téléchargé (provenance, cf. principe D5 de
docs/architecture/01_ARCHITECTURE_GLOBALE.md).

Ne fait pas partie de la chaîne src/ (couches 0 à 6) : c'est un script
d'infrastructure, appelé par le workflow GitHub Actions
`.github/workflows/finess-activites-quotidien.yml`, avant que la couche 1
(acquisition FINESS proprement dite, dans src/) ne prenne le relais. Dans le
même esprit que scripts/recensement.py et scripts/construire_echantillon.py.

CONTRAT AVEC L'API DATA.GOUV.FR, CONSTATÉ LE 19/08/2026
---------------------------------------------------------

    GET https://www.data.gouv.fr/api/1/datasets/finess-activites-1/

Renvoie un objet portant une liste "resources". Deux ressources y coexistent
sous le même format ("json.gz") : le flux journalier
("finess-activites-journalier-AAAAMMJJ.json.gz") et un mensuel figé
("finess-activites-mensuel-AAAAMM.json.gz") — exactement comme Structures,
contrairement à l'hypothèse initiale du ticket qui supposait une cadence
mensuelle uniquement. Ce script mire donc le dispositif Structures à
l'identique : le journalier est le comportement par défaut (workflow
d'acquisition quotidien) ; `--mensuel AAAAMM` sélectionne à la place le
mensuel figé de ce millésime (OOM-54, publication du site sur millésime
figé). Le 29/09/2026, l'API publiait deux mensuels (202607 et 202608) :
plusieurs peuvent coexister, d'où la sélection par millésime exact, jamais
« le premier trouvé ». Distinguer les ressources par leur titre évite de
charger le mauvais fichier en silence si data.gouv.fr modifie un jour
l'ordre de la liste.

Chaque ressource porte : id, title, url (téléchargement direct, hébergé sur
static.data.gouv.fr — distinct de l'URL redirectrice data.gouv.fr/api/1/
datasets/r/...), filesize (octets), checksum {type: "sha1", value}, et
last_modified. C'est ce triplet (taille, sha1, url) qui permet de vérifier
un téléchargement sans dépendre d'un second appel.

Aucune dépendance tierce : bibliothèque standard uniquement (urllib,
hashlib, json), comme le reste du projet. Le téléchargement se fait en
flux, par blocs, jamais chargé intégralement en mémoire — même principe que
flux_json.py pour la couche 1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["ErreurTelechargement", "resource_courante", "interroger_api",
           "telecharger", "empreinte_sha1", "verifier_checksum",
           "verifier_taille", "executer", "API_DATASET",
           "mensuels_disponibles", "resource_mensuelle"]

API_DATASET = "https://www.data.gouv.fr/api/1/datasets/finess-activites-1/"
FORMAT_ATTENDU = "json.gz"
PREFIXE_JOURNALIER = "finess-activites-journalier-"
# Mensuel figé (OOM-54) : titre exact, millésime AAAAMM capturé.
MOTIF_MENSUEL = re.compile(r"^finess-activites-mensuel-(\d{6})\.json\.gz$")
MOTIF_MILLESIME_MENSUEL = re.compile(r"^\d{4}(0[1-9]|1[0-2])$")
TIMEOUT_S = 120
TAILLE_BLOC = 1 << 20  # 1 Mio


class ErreurTelechargement(Exception):
    """API inattendue, ressource introuvable ou ambiguë, taille ou checksum divergents."""


def resource_courante(donnees_api: Dict[str, Any]) -> Dict[str, Any]:
    """Sélectionne la ressource journalière, sans deviner en silence.

    Refuse explicitement s'il n'y en a pas exactement une : zéro voudrait
    dire que data.gouv.fr a changé sa nomenclature de titres, plusieurs
    voudrait dire qu'on risquerait de prendre la mauvaise par hasard.
    """
    candidats = [
        r for r in donnees_api.get("resources", [])
        if r.get("format") == FORMAT_ATTENDU
        and str(r.get("title", "")).startswith(PREFIXE_JOURNALIER)
    ]
    if len(candidats) != 1:
        titres = [r.get("title") for r in donnees_api.get("resources", [])]
        raise ErreurTelechargement(
            f"{len(candidats)} ressource(s) journalière(s) {FORMAT_ATTENDU!r} "
            f"trouvée(s) dans l'API, une seule attendue. Titres vus : {titres}")
    return candidats[0]


def mensuels_disponibles(donnees_api: Dict[str, Any]) -> List[str]:
    """Millésimes AAAAMM des ressources mensuelles publiées, triés croissants.

    Une ressource ne compte que si son format est `json.gz` et son titre suit
    exactement le motif `finess-*-mensuel-AAAAMM.json.gz`.
    """
    millesimes = []
    for r in donnees_api.get("resources", []):
        trouve = MOTIF_MENSUEL.match(str(r.get("title", "")))
        if trouve and r.get("format") == FORMAT_ATTENDU:
            millesimes.append(trouve.group(1))
    return sorted(millesimes)


def resource_mensuelle(donnees_api: Dict[str, Any], millesime: str) -> Dict[str, Any]:
    """Sélectionne le mensuel figé `millesime` (AAAAMM), sans jamais se rabattre.

    Si ce mensuel n'est pas publié (ou l'est en double), échoue en listant les
    mensuels disponibles : ni le journalier ni un mois voisin ne le
    remplacent en silence (D6).
    """
    if not MOTIF_MILLESIME_MENSUEL.match(millesime or ""):
        raise ErreurTelechargement(
            f"Millésime mensuel invalide : {millesime!r} (attendu AAAAMM, "
            f"mois 01 à 12)")
    candidats = []
    for r in donnees_api.get("resources", []):
        trouve = MOTIF_MENSUEL.match(str(r.get("title", "")))
        if trouve and trouve.group(1) == millesime and r.get("format") == FORMAT_ATTENDU:
            candidats.append(r)
    if len(candidats) != 1:
        raise ErreurTelechargement(
            f"{len(candidats)} ressource(s) mensuelle(s) {millesime} "
            f"{FORMAT_ATTENDU!r} trouvée(s) dans l'API, une seule attendue. "
            f"Mensuels disponibles : {mensuels_disponibles(donnees_api) or 'aucun'}")
    return candidats[0]


def interroger_api(url: str = API_DATASET) -> Dict[str, Any]:
    requete = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(requete, timeout=TIMEOUT_S) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def telecharger(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    requete = urllib.request.Request(url)
    with urllib.request.urlopen(requete, timeout=TIMEOUT_S) as reponse, \
            open(destination, "wb") as fichier:
        while True:
            bloc = reponse.read(TAILLE_BLOC)
            if not bloc:
                break
            fichier.write(bloc)


def empreinte_sha1(chemin: Path) -> str:
    hachage = hashlib.sha1()
    with open(chemin, "rb") as fichier:
        while True:
            bloc = fichier.read(TAILLE_BLOC)
            if not bloc:
                break
            hachage.update(bloc)
    return hachage.hexdigest()


def verifier_taille(chemin: Path, resource: Dict[str, Any]) -> None:
    attendue = resource.get("filesize")
    obtenue = chemin.stat().st_size
    if attendue is not None and attendue != obtenue:
        raise ErreurTelechargement(
            f"Taille divergente pour {chemin.name} : attendue {attendue} octets "
            f"(publiée par data.gouv.fr), obtenue {obtenue}. Téléchargement "
            f"tronqué ou interrompu, à ne pas utiliser")


def verifier_checksum(chemin: Path, resource: Dict[str, Any]) -> None:
    checksum = resource.get("checksum") or {}
    if checksum.get("type") != "sha1" or not checksum.get("value"):
        raise ErreurTelechargement(
            f"Pas de checksum sha1 exploitable dans la réponse API pour "
            f"{resource.get('title')!r} : {checksum!r}")
    attendu = str(checksum["value"]).lower()
    obtenu = empreinte_sha1(chemin).lower()
    if attendu != obtenu:
        raise ErreurTelechargement(
            f"Checksum divergent pour {chemin.name} : attendu {attendu} "
            f"(publié par data.gouv.fr), obtenu {obtenu}. Fichier corrompu, "
            f"à ne pas utiliser")


def ecrire_metadonnees(chemin_meta: Path, resource: Dict[str, Any],
                       destination: Path) -> None:
    """Provenance du fichier : ce que le principe D5 (architecture) exige
    sur chaque ligne, appliqué ici au fichier source lui-même."""
    metadonnees = {
        "resource_id": resource.get("id"),
        "titre": resource.get("title"),
        "url_source": resource.get("url"),
        "filesize": resource.get("filesize"),
        "checksum_sha1": (resource.get("checksum") or {}).get("value"),
        "last_modified_source": resource.get("last_modified"),
        "fichier_local": str(destination),
        "telecharge_le": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    chemin_meta.write_text(
        json.dumps(metadonnees, indent=2, ensure_ascii=False), encoding="utf-8")


def executer(destination: Path, api_url: str = API_DATASET,
             mensuel: Optional[str] = None) -> Dict[str, Any]:
    """Point d'entrée réutilisable (CLI et tests).

    Sans `mensuel`, sélectionne le journalier (comportement par défaut) ;
    avec `mensuel` = AAAAMM, le mensuel figé de ce millésime (OOM-54).

    Ordre délibéré : taille avant checksum. La taille suffit à écarter la
    plupart des téléchargements tronqués sans relire tout le fichier ; le
    checksum, plus coûteux (relit tout le fichier), ne s'exécute que si la
    taille est déjà correcte.
    """
    donnees_api = interroger_api(api_url)
    if mensuel is None:
        resource = resource_courante(donnees_api)
    else:
        resource = resource_mensuelle(donnees_api, mensuel)
    telecharger(resource["url"], destination)
    verifier_taille(destination, resource)
    verifier_checksum(destination, resource)
    chemin_meta = destination.with_suffix(destination.suffix + ".metadata.json")
    ecrire_metadonnees(chemin_meta, resource, destination)
    return {"resource": resource, "destination": destination, "metadata": chemin_meta}


def main(argv=None) -> int:
    analyseur = argparse.ArgumentParser(
        description="Télécharge et vérifie l'extrait FINESS-Activités quotidien "
                     "(ou, avec --mensuel, le mensuel figé AAAAMM) publié par "
                     "l'Agence du Numérique en Santé sur data.gouv.fr.")
    analyseur.add_argument("destination", type=Path, nargs="?",
                           help="chemin du fichier .json.gz à écrire (garder le "
                                "nom source, qui porte le millésime)")
    analyseur.add_argument("--mensuel", metavar="AAAAMM",
                           help="sélectionner le mensuel figé de ce millésime au "
                                "lieu du journalier ; échoue s'il n'est pas publié")
    analyseur.add_argument("--lister-mensuels", action="store_true",
                           help="afficher les millésimes mensuels publiés (un par "
                                "ligne, croissants) et sortir, sans télécharger")
    analyseur.add_argument("--api", default=API_DATASET,
                           help="URL de l'API dataset (défaut : FINESS-Activités)")
    arguments = analyseur.parse_args(argv)
    if arguments.lister_mensuels:
        try:
            millesimes = mensuels_disponibles(interroger_api(arguments.api))
        except (urllib.error.URLError, OSError, ValueError) as erreur:
            print(f"ÉCHEC — {erreur}", file=sys.stderr)
            return 1
        if not millesimes:
            print("ÉCHEC — aucun mensuel publié dans l'API", file=sys.stderr)
            return 1
        print("\n".join(millesimes))
        return 0
    if arguments.destination is None:
        analyseur.error("destination requise (sauf avec --lister-mensuels)")
    try:
        resultat = executer(arguments.destination, arguments.api, arguments.mensuel)
    except (ErreurTelechargement, urllib.error.URLError, OSError) as erreur:
        print(f"ÉCHEC — {erreur}", file=sys.stderr)
        return 1
    resource = resultat["resource"]
    print(f"OK — {resource['title']} ({resource['filesize']} octets) "
          f"→ {resultat['destination']}")
    print(f"Checksum sha1 vérifié : {resource['checksum']['value']}")
    print(f"Métadonnées écrites  : {resultat['metadata']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
