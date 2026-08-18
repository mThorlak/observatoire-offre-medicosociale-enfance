"""
nomenclatures.py — Couche 3 (référentiels), résolution code → libellé.

Ce module implémente le principe D4 de l'architecture (voir
docs/architecture/01_ARCHITECTURE_GLOBALE.md) : « Les nomenclatures, la
taxonomie et le périmètre sont des données versionnées, pas du code. » Le V1
du projet codait les libellés en dur dans `taxonomie.py` (voir ce fichier pour
le contre-exemple) ; ce module ne répète pas cette erreur. Les libellés
vivent dans `referentiels/nomenclature_categorie_finess.csv`, un fichier
texte versionné, daté et sourcé (principe D5 — provenance), que ce module se
contente de charger et d'interroger.

Portée : uniquement le domaine `categorie_etablissement`, c'est-à-dire
`etablissement.code_categorie` et `entite_juridique.code_categorie` du pivot
(ce dernier toujours nul). Les autres nomenclatures FINESS (discipline, mode
de fonctionnement, public, type de voie, etc.) ne sont pas couvertes ici :
elles suivront le même schéma, dans des fichiers de référence séparés, au fur
et à mesure des tickets qui les traiteront.

SIGNALEMENT DES CODES INCONNUS (principe D6 — aucun échec silencieux)
-----------------------------------------------------------------------
Un code présent dans les données réelles mais absent du référentiel n'est :
- ni retourné tel quel (le code brut n'est pas un libellé lisible) ;
- ni transformé en None ou chaîne vide silencieusement recopiée en aval ;
- ni la cause d'un plantage non contrôlé (`KeyError`, `IndexError`...).

Le mécanisme retenu est une exception dédiée, `CodeCategorieInconnu`
(sous-classe de `ErreurNomenclature`), levée par `resoudre_categorie` et
portant le code fautif (`erreur.code`). C'est l'idiome déjà en usage dans ce
dépôt pour signaler une violation détectée à l'exécution plutôt que de la
masquer : `contrat_source.ErreurContrat`, `entrepot.ErreurEntrepot`. Un appel
groupé sur un grand nombre d'établissements doit donc intercepter
`CodeCategorieInconnu` explicitement (par exemple pour l'agréger dans un
registre d'anomalies à la manière de `inventaire_codes.py`) ; rien dans ce
module n'avale l'anomalie à sa place.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Optional

__all__ = [
    "ErreurNomenclature", "CodeCategorieInconnu",
    "CHEMIN_REFERENTIEL_CATEGORIE",
    "charger_categories", "resoudre_categorie", "categorie_connue",
]

# Racine du dépôt : src/nomenclatures.py -> src/ -> racine.
_RACINE_PROJET = Path(__file__).resolve().parent.parent
CHEMIN_REFERENTIEL_CATEGORIE = _RACINE_PROJET / "referentiels" / "nomenclature_categorie_finess.csv"


class ErreurNomenclature(Exception):
    """Base des anomalies de résolution de nomenclature."""


class CodeCategorieInconnu(ErreurNomenclature):
    """Un code_categorie observé dans les données n'existe pas au référentiel.

    Porte le code fautif (`code`) pour permettre à l'appelant de l'exploiter
    (journalisation, registre d'anomalies, remontée à l'export qualité) sans
    reparser le message.
    """

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(
            f"code_categorie {code!r} absent du référentiel "
            f"{CHEMIN_REFERENTIEL_CATEGORIE.name} — libellé inconnu, non déduit."
        )


def charger_categories(chemin: Optional[Path] = None) -> Dict[str, str]:
    """Charge le référentiel code → libellé depuis le fichier CSV versionné.

    Les lignes commençant par `#` (en-tête de provenance) sont ignorées.
    Ne fait aucune supposition sur les codes absents : ce que le fichier ne
    contient pas, cette fonction ne l'invente pas.

    Lève `ErreurNomenclature` si le fichier est absent ou si un code y figure
    en double avec des libellés différents (le référentiel doit être une
    fonction, pas une relation).
    """
    chemin = chemin or CHEMIN_REFERENTIEL_CATEGORIE
    if not chemin.exists():
        raise ErreurNomenclature(f"Référentiel introuvable : {chemin}")

    categories: Dict[str, str] = {}
    with open(chemin, encoding="utf-8", newline="") as f:
        lignes_donnees = (ligne for ligne in f if not ligne.startswith("#"))
        lecteur = csv.DictReader(lignes_donnees, delimiter=";")
        for ligne in lecteur:
            code = (ligne.get("code") or "").strip()
            libelle = (ligne.get("libelle") or "").strip()
            if not code or not libelle:
                continue
            existant = categories.get(code)
            if existant is not None and existant != libelle:
                raise ErreurNomenclature(
                    f"Référentiel incohérent : code {code!r} porte deux libellés "
                    f"différents ({existant!r} et {libelle!r})")
            categories[code] = libelle
    return categories


# Cache module-level : le référentiel par défaut est immuable au cours d'une
# exécution (c'est un fichier versionné, pas une donnée qui bouge). Chargé au
# premier appel, jamais recalculé ensuite tant que le chemin par défaut est
# utilisé.
_CACHE_DEFAUT: Optional[Dict[str, str]] = None


def _categories_defaut() -> Dict[str, str]:
    global _CACHE_DEFAUT
    if _CACHE_DEFAUT is None:
        _CACHE_DEFAUT = charger_categories()
    return _CACHE_DEFAUT


def resoudre_categorie(code: str, *, categories: Optional[Dict[str, str]] = None) -> str:
    """Résout un code_categorie FINESS en son libellé long.

    `categories` permet d'injecter un référentiel déjà chargé (tests, ou
    appel en masse évitant de rouvrir le fichier à chaque ligne) ; à défaut,
    le référentiel par défaut est chargé une fois et mis en cache.

    Lève `CodeCategorieInconnu` si le code n'existe pas dans le référentiel :
    voir la note de module sur le signalement des codes inconnus.
    """
    table = categories if categories is not None else _categories_defaut()
    libelle = table.get(code)
    if libelle is None:
        raise CodeCategorieInconnu(code)
    return libelle


def categorie_connue(code: str, *, categories: Optional[Dict[str, str]] = None) -> bool:
    """Teste l'appartenance d'un code au référentiel, sans lever d'exception.

    Utile pour un contrôle en amont (ex. mesure de couverture) qui ne veut
    pas interrompre son propre déroulement pour chaque code inconnu ; la
    résolution elle-même (`resoudre_categorie`) reste, elle, bloquante.
    """
    table = categories if categories is not None else _categories_defaut()
    return code in table
