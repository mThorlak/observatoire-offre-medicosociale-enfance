"""
indicateurs.py — Couche 5 (analyse), premier indicateur (OOM-13).

Compte les établissements actifs de l'entrepôt par département × catégorie
(libellés) : première brique de la couche 5 (`docs/architecture/
01_ARCHITECTURE_GLOBALE.md` §3 : « Agrégats, densités rapportées à la
population, séries par millésime »). Ni densité ni série temporelle ici :
elles viendront avec INSEE et les millésimes suivants.

DÉFINITION RETENUE — « actif »
--------------------------------
`etablissement.etat_objet == 'A'`. Champ à exactement deux valeurs observées
sur l'extrait réel chargé, `A`/`I` (`docs/architecture/03_SCHEMA_PIVOT.md` :
104 699 `A` / 69 809 `I`) ; « fermé » (`I`) est exclu. Ceci applique la
remarque de l'architecture selon laquelle les entités fermées ne sont pas
filtrées à l'ingestion mais à l'analyse (la couche 2 stocke verbatim, la
couche 5 juge). Aucune autre condition (date de fermeture, autorisation
active...) n'entre dans cette définition minimale ; l'élargir est un choix
ultérieur, à documenter ici s'il est fait.

DÉPARTEMENT ET CATÉGORIE — résolution, jamais d'invention
------------------------------------------------------------
Le département vient de l'adresse principale de l'établissement
(`code_usage_adresse = '03'`, rang le plus faible en cas de doublon — même
règle que `export_front.etablissements_bruts`), passée à
`territoires.departement_depuis_cog`. Le libellé de catégorie vient de
`nomenclatures.resoudre_categorie`. Un établissement actif dont le
département ou la catégorie ne peut pas être résolu (pas d'adresse
principale, `cog_commune` invalide, `code_categorie` absent ou hors
référentiel) n'est **jamais compté en silence dans une case erronée** : il
est exclu du tableau et comptabilisé séparément (`Resultat.sans_departement`,
`Resultat.categorie_inconnue`), de sorte que le tableau plus les exclusions
reconstitue toujours exactement `Resultat.total_actifs` — un total vérifiable
à la main (`Resultat.verifier_total`).

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from entrepot import Entrepot
from nomenclatures import CodeCategorieInconnu, resoudre_categorie
from territoires import ErreurTerritoires, departement_depuis_cog

__all__ = ["ErreurIndicateurs", "Resultat", "etat_objet_actif",
           "indicateur_departement_categorie"]

# '03' = adresse principale — cf. export_front.py et
# docs/architecture/03_SCHEMA_PIVOT.md (adresse.code_usage_adresse).
USAGE_ADRESSE_PRINCIPALE = "03"

# Seule valeur retenue comme « actif » — voir la note de module ci-dessus.
ETAT_OBJET_ACTIF = "A"


class ErreurIndicateurs(Exception):
    """Entrepôt non ouvert."""


class Resultat:
    """Table département × catégorie, et les établissements actifs exclus.

    `tableau` est indexé par `(code_departement, libelle_categorie)`. Les
    compteurs d'exclusion ne sont pas mutuellement exclusifs : un
    établissement sans département résolu ET sans catégorie résolue est
    compté dans les deux, d'où `sans_departement_et_categorie_inconnue`, qui
    sert à ne pas le compter deux fois dans `exclus()`.
    """

    def __init__(self) -> None:
        self.tableau: Dict[Tuple[str, str], int] = {}
        self.total_actifs = 0
        self.sans_departement = 0
        self.categorie_inconnue = 0
        self.sans_departement_et_categorie_inconnue = 0

    def ajouter(self, code_departement: Optional[str],
                libelle_categorie: Optional[str]) -> None:
        self.total_actifs += 1
        if code_departement is None and libelle_categorie is None:
            self.sans_departement_et_categorie_inconnue += 1
            self.sans_departement += 1
            self.categorie_inconnue += 1
            return
        if code_departement is None:
            self.sans_departement += 1
            return
        if libelle_categorie is None:
            self.categorie_inconnue += 1
            return
        cle = (code_departement, libelle_categorie)
        self.tableau[cle] = self.tableau.get(cle, 0) + 1

    def exclus(self) -> int:
        """Établissements actifs absents du tableau : hors inclusion-exclusion."""
        return (self.sans_departement + self.categorie_inconnue
                - self.sans_departement_et_categorie_inconnue)

    def verifier_total(self) -> bool:
        """`tableau` + exclusions doit toujours reconstituer `total_actifs`."""
        return sum(self.tableau.values()) + self.exclus() == self.total_actifs

    def lignes_triees(self) -> List[Tuple[str, str, int]]:
        """`(département, catégorie, nombre)`, triées département puis catégorie."""
        return sorted(
            ((d, c, n) for (d, c), n in self.tableau.items()),
            key=lambda ligne: (ligne[0], ligne[1]))

    def rapport(self) -> str:
        lignes = [f"{'DÉPARTEMENT':<12}{'CATÉGORIE':<60}{'ACTIFS':>8}"]
        for departement, categorie, nombre in self.lignes_triees():
            lignes.append(f"{departement:<12}{categorie:<60}{nombre:>8}")
        lignes.append("")
        lignes.append(f"Total établissements actifs : {self.total_actifs}")
        lignes.append(f"    dont dans le tableau      : {sum(self.tableau.values())}")
        lignes.append(f"    sans département résolu   : {self.sans_departement}")
        lignes.append(f"    catégorie non résolue      : {self.categorie_inconnue}")
        return "\n".join(lignes)


def etat_objet_actif(etat_objet: Optional[str]) -> bool:
    """« Actif » = `etat_objet == 'A'` — voir la définition en tête de module."""
    return etat_objet == ETAT_OBJET_ACTIF


def indicateur_departement_categorie(
        entrepot: Entrepot,
        categories: Optional[Dict[str, str]] = None) -> Resultat:
    """Compte les établissements actifs par département × catégorie (libellés).

    `categories` permet d'injecter un référentiel déjà chargé (tests, appel
    en masse évitant de recharger le CSV) ; à défaut, le référentiel par
    défaut de `nomenclatures` est utilisé et mis en cache par ce module.

    Lève `ErreurIndicateurs` si l'entrepôt n'est pas ouvert.
    """
    if entrepot.connexion is None:
        raise ErreurIndicateurs("entrepôt non ouvert")
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
        requete,
        (USAGE_ADRESSE_PRINCIPALE, USAGE_ADRESSE_PRINCIPALE, ETAT_OBJET_ACTIF),
    ).fetchall()

    resultat = Resultat()
    for code_categorie, cog_commune in lignes:
        departement = None
        if cog_commune is not None:
            try:
                departement = departement_depuis_cog(cog_commune)
            except ErreurTerritoires:
                departement = None

        libelle = None
        if code_categorie is not None:
            try:
                libelle = resoudre_categorie(code_categorie, categories=categories)
            except CodeCategorieInconnu:
                libelle = None

        resultat.ajouter(departement, libelle)
    return resultat


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    analyseur = argparse.ArgumentParser(
        description="Établissements actifs par département × catégorie (OOM-13).")
    analyseur.add_argument("base", type=Path, help="fichier de l'entrepôt SQLite")
    arguments = analyseur.parse_args()

    with Entrepot(arguments.base) as entrepot:
        resultat = indicateur_departement_categorie(entrepot)
    print(resultat.rapport())
    if not resultat.verifier_total():
        raise SystemExit("incohérence : tableau + exclusions != total actifs")
