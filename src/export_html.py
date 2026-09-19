"""
export_html.py — Couche 6 (restitution) : pages HTML du site, rendues depuis
l'entrepôt par gabarits (OOM-100), plus la page d'accueil (OOM-103).

Remplace, à terme, les pages écrites à la main de `front/` (qui violent D7 et
D10) par des pages produites ici depuis `front/gabarits/`. Trois pages pour
l'instant :

- `index.html` (gabarit `accueil.html`, OOM-103) — porte d'entrée : mention de
  périmètre (comptage brut, qualification enfance/adolescents non appliquée),
  chiffres clés du millésime, effectifs par département et par catégorie (les
  marges `Resultat.par_departement`/`par_categorie` de la couche 5), source
  FINESS et licence ;
- `liste.html` — tous les établissements (même lecture qu'`export_front.
  etablissements_bruts`), chacun avec ses activités de niveau `ET` dans un
  `<details>` (même lecture qu'`export_front.activites_par_etablissement`) ;
- `indicateur.html` — le tableau département × catégorie de la couche 5
  (`indicateurs.indicateur_departement_categorie`), dans l'ordre de
  `Resultat.lignes_triees`, donc le même que le CSV de `restituer`.

CONTRAT A — figé par OOM-100, consommé par OOM-102, OOM-103, OOM-104
-----------------------------------------------------------------
    rendre(entrepot, dossier_gabarits, dossier_sortie) -> dict

`entrepot` est un `Entrepot` ouvert ; `dossier_gabarits` contient `base.html`
et un gabarit par page (`accueil.html`, `liste.html`, `indicateur.html`) ;
`dossier_sortie` est créé au besoin et reçoit une page par gabarit, sous le même
nom — sauf l'accueil, publié en `index.html` (`GABARITS_PAGE`). Le
dictionnaire retourné, sur le modèle d'`export_front.exporter` :

    millesime              str        millésime unique de l'entrepôt
    genere_le              str        horodatage du rendu (ISO, seconde)
    pages_ecrites          list[str]  noms des pages écrites, dans l'ordre
    octets                 dict       {page: taille en octets}
    lignes_rendues         dict       {page: lignes de tableau principal}
    nombre_etablissements  int        = lignes_rendues["liste.html"]
    sans_adresse_principale, departement_non_resolu, categorie_non_resolue
                           int        mêmes définitions qu'export_front
    activites_total, etablissements_avec_activites
                           int        mêmes définitions qu'export_front
    nature_non_resolue     int        = activites_total tant qu'aucune
                                      nomenclature de nature n'est versionnée
    indicateur_lignes      int        = lignes_rendues["indicateur.html"]
    indicateur_total_actifs, indicateur_exclus
                           int        Resultat.total_actifs / Resultat.exclus()
    accueil_departements, accueil_categories
                           int        entrées par département / par catégorie
                                      de l'accueil (= lignes_rendues["index.html"]
                                      pour les départements)

Lève `ErreurExportHtml` — avant d'écrire quoi que ce soit — si un gabarit ou
un bloc manque (le message porte le chemin attendu), si un gabarit réclame une
valeur que le module ne fournit pas, ou si l'entrepôt est incohérent (plusieurs
millésimes, source chargée deux fois, aucun lot) : un export ne sort pas d'un
entrepôt en échec (D6).

GABARITS — des trous, pas de logique
-----------------------------------------------------------------
Un gabarit est du HTML lisible découpé en blocs nommés :

    <!-- BLOC nom -->…<!-- FIN nom -->

chacun étant un `string.Template` de la stdlib (`$valeur`, `$$` pour un `$`
littéral). Le texte hors blocs n'est pas publié (il sert à documenter le
gabarit). `base.html` est un seul gabarit, sans blocs, dont les trous `$titre`,
`$style`, `$contenu`, `$script`, `$pied` et `$millesime` reçoivent les blocs
homonymes de la page. Les blocs de ligne (`ligne`, `option`, `activite`…)
sont substitués une fois par élément puis concaténés par ce module.

Toute décision — libellé de repli d'un code non résolu, classe d'état,
largeur de barre, total — est prise ici, en Python, jamais dans un gabarit
(D7). Toute valeur issue des données est échappée (`html.escape`) avant
substitution ; les fragments déjà rendus sont insérés tels quels.

Ce module ne lit l'entrepôt qu'au travers des couches existantes
(`export_front`, `indicateurs`, `Entrepot.etat`) : aucune requête SQL ici.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import html
import re
import time
from pathlib import Path
from string import Template
from typing import Dict, Iterable, List, Mapping, Optional

from entrepot import Entrepot
from export_front import activites_par_etablissement, etablissements_bruts
from indicateurs import Resultat, indicateur_departement_categorie

__all__ = ["rendre", "ErreurExportHtml", "GABARIT_BASE", "PAGES", "DOSSIER_GABARITS"]

GABARIT_BASE = "base.html"
PAGES = ("index.html", "liste.html", "indicateur.html")
# Gabarit d'une page quand il ne porte pas son nom (l'accueil est publié en
# `index.html`, porte d'entrée par défaut d'un site statique).
GABARITS_PAGE = {"index.html": "accueil.html"}
DOSSIER_GABARITS = Path(__file__).resolve().parent.parent / "front" / "gabarits"

# Blocs que chaque gabarit de page doit fournir à `base.html`.
BLOCS_PAGE = ("titre", "pied", "style", "contenu", "script")

_MOTIF_BLOC = re.compile(r"<!-- BLOC (\w+) -->\n?(.*?)\n?<!-- FIN \1 -->", re.DOTALL)

_CLASSES_ETAT = {"A": "etat-actif", "I": "etat-inactif"}


class ErreurExportHtml(Exception):
    """Gabarit manquant ou incomplet, ou entrepôt impropre à l'export."""


# ---------------------------------------------------------------------------
# gabarits
# ---------------------------------------------------------------------------

class Gabarit:
    """Blocs nommés d'un fichier de gabarit, chacun substituable."""

    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin
        if not chemin.is_file():
            raise ErreurExportHtml(f"gabarit manquant : {chemin}")
        self.blocs = {nom: Template(corps)
                      for nom, corps in _MOTIF_BLOC.findall(chemin.read_text(encoding="utf-8"))}

    def exiger(self, noms: Iterable[str]) -> None:
        absents = [nom for nom in noms if nom not in self.blocs]
        if absents:
            raise ErreurExportHtml(
                f"bloc(s) manquant(s) dans le gabarit {self.chemin} : {', '.join(absents)}")

    def remplir(self, bloc: str, valeurs: Mapping[str, object]) -> str:
        if bloc not in self.blocs:
            raise ErreurExportHtml(f"bloc manquant dans le gabarit {self.chemin} : {bloc}")
        return _substituer(self.blocs[bloc], valeurs, f"{self.chemin} (bloc {bloc})")

    def repeter(self, bloc: str, elements: Iterable[Mapping[str, object]],
                separateur: str = "") -> str:
        return separateur.join(self.remplir(bloc, valeurs) for valeurs in elements)


def _substituer(gabarit: Template, valeurs: Mapping[str, object], origine: str) -> str:
    try:
        return gabarit.substitute(valeurs)
    except KeyError as erreur:
        raise ErreurExportHtml(
            f"valeur {erreur} réclamée par {origine} mais non fournie") from erreur
    except ValueError as erreur:
        raise ErreurExportHtml(f"gabarit invalide {origine} : {erreur}") from erreur


def _e(valeur: Optional[object]) -> str:
    """Échappe une valeur issue des données ; `None` devient une chaîne vide."""
    return "" if valeur is None else html.escape(str(valeur))


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------

def _options(gabarit: Gabarit, valeurs: Iterable[Optional[str]]) -> str:
    return gabarit.repeter("option", ({"valeur": _e(v)} for v in sorted(set(filter(None, valeurs)))))


def _capacites(gabarit: Gabarit, capacites: List[Dict[str, object]]) -> str:
    if not capacites:
        return gabarit.remplir("capacites_aucune", {})
    lignes = gabarit.repeter("capacite", (
        {"nombre": _e(c["nombre"]) if c["nombre"] is not None else "?",
         "unite": _e(c["code_unite_mesure"] or "?"),
         "statut": _e(c["code_statut_capacite"] or "?")}
        for c in capacites))
    return gabarit.remplir("capacites", {"lignes": lignes})


def _activites(gabarit: Gabarit, activites: List[Dict[str, object]]) -> str:
    if not activites:
        return gabarit.remplir("activites_aucune", {})
    lignes = gabarit.repeter("activite", (
        {"code_nature": _e(a["code_nature"]),
         "nature": _e(a["libelle_nature"] or ("[non résolu]" if a["code_nature"] else "[absent]")),
         "classe_nature": "" if a["libelle_nature"] else "code-non-resolu",
         "code_etat": _e(a["etat_objet"]),
         "etat": _e(a["etat_libelle"]),
         "classe_etat": _CLASSES_ETAT.get(a["etat_objet"], ""),
         "capacites": _capacites(gabarit, a["capacites"])}
        for a in activites))
    return gabarit.remplir("activites", {"nombre": len(activites), "lignes": lignes})


def _page_liste(gabarit: Gabarit, entrepot: Entrepot, compteurs: Dict[str, object]) -> Dict[str, str]:
    etablissements = etablissements_bruts(entrepot)
    activites = activites_par_etablissement(entrepot)

    def ligne(e: Dict[str, object]) -> Dict[str, object]:
        return {
            "num_finess": _e(e["num_finess_et"]),
            "nom": _e(e["nom"]),
            "code_categorie": _e(e["code_categorie"]),
            "libelle_categorie": _e(e["libelle_categorie"]),
            "categorie": _e(e["libelle_categorie"] or (
                "[non résolu]" if e["code_categorie"] else "[absent]")),
            "code_departement": _e(e["code_departement"]),
            "departement": _e(e["code_departement"] or (
                "[non résolu]" if e["cog_commune"] else "[absent]")),
            "code_postal": _e(e["code_postal"]),
            "code_etat": _e(e["etat_objet"]),
            "etat": _e(e["etat_libelle"]),
            "classe_etat": _CLASSES_ETAT.get(e["etat_objet"], ""),
            "activites": _activites(gabarit, activites.get(e["num_finess_et"], [])),
        }

    activites_total = sum(len(lignes) for lignes in activites.values())
    compteurs.update({
        "nombre_etablissements": len(etablissements),
        "sans_adresse_principale": sum(1 for e in etablissements if e["cog_commune"] is None),
        "departement_non_resolu": sum(
            1 for e in etablissements
            if e["cog_commune"] is not None and e["code_departement"] is None),
        "categorie_non_resolue": sum(
            1 for e in etablissements
            if e["code_categorie"] is not None and e["libelle_categorie"] is None),
        "activites_total": activites_total,
        "etablissements_avec_activites": len(activites),
        "nature_non_resolue": sum(
            1 for lignes in activites.values() for a in lignes if a["libelle_nature"] is None),
    })
    valeurs = dict(compteurs)
    valeurs.update({
        "lignes": gabarit.repeter("ligne", (ligne(e) for e in etablissements), "\n"),
        "options_departement": _options(gabarit, (e["code_departement"] for e in etablissements)),
        "options_categorie": _options(gabarit, (e["libelle_categorie"] for e in etablissements)),
    })
    compteurs["lignes_rendues"]["liste.html"] = len(etablissements)
    return valeurs


def _page_indicateur(gabarit: Gabarit, entrepot: Entrepot,
                     compteurs: Dict[str, object]) -> Dict[str, str]:
    resultat = indicateur_departement_categorie(entrepot)
    if not resultat.verifier_total():
        raise ErreurExportHtml("indicateur incohérent : tableau + exclusions != total actifs")
    lignes = resultat.lignes_triees()
    maximum = max((n for _, _, n in lignes), default=0) or 1
    dans_tableau = sum(n for _, _, n in lignes)

    compteurs.update({
        "indicateur_lignes": len(lignes),
        "indicateur_total_actifs": resultat.total_actifs,
        "indicateur_exclus": resultat.exclus(),
    })
    valeurs = dict(compteurs)
    valeurs.update({
        "lignes": gabarit.repeter("ligne", (
            {"code_departement": _e(d), "libelle_categorie": _e(c), "effectif": n,
             "largeur": round(n / maximum * 100)}
            for d, c, n in lignes), "\n"),
        "options_departement": _options(gabarit, (d for d, _, _ in lignes)),
        "total": dans_tableau,
        "total_actifs": resultat.total_actifs,
        "dans_tableau": dans_tableau,
        "sans_departement": resultat.sans_departement,
        "categorie_inconnue": resultat.categorie_inconnue,
    })
    compteurs["lignes_rendues"]["indicateur.html"] = len(lignes)
    return valeurs


def _page_accueil(gabarit: Gabarit, entrepot: Entrepot,
                  compteurs: Dict[str, object]) -> Dict[str, str]:
    """Accueil (OOM-103) : tous les chiffres viennent de la couche 5
    (`Resultat` et ses marges) ou de `Entrepot.etat` — rien n'est recompté ici."""
    resultat: Resultat = indicateur_departement_categorie(entrepot)
    if not resultat.verifier_total():
        raise ErreurExportHtml("indicateur incohérent : tableau + exclusions != total actifs")
    departements = resultat.par_departement()
    categories = resultat.par_categorie()
    lots = entrepot.etat()["lots"]

    compteurs.update({
        "accueil_departements": len(departements),
        "accueil_categories": len(categories),
    })
    valeurs = dict(compteurs)
    valeurs.update({
        "total_actifs": resultat.total_actifs,
        "dans_tableau": resultat.dans_tableau(),
        "exclus": resultat.exclus(),
        "sans_departement": resultat.sans_departement,
        "categorie_inconnue": resultat.categorie_inconnue,
        "nombre_departements": len(departements),
        "nombre_categories": len(categories),
        "departements": gabarit.repeter("departement", (
            {"code_departement": _e(d), "effectif": n} for d, n in departements), "\n"),
        "categories": gabarit.repeter("categorie", (
            {"libelle_categorie": _e(c), "effectif": n} for c, n in categories), "\n"),
        "lots": gabarit.repeter("lot", (
            {"source": _e(l["source"]), "millesime": _e(l["millesime"]),
             "fichier": _e(l["fichier"]), "empreinte": _e(l["empreinte"])}
            for l in lots), "\n"),
    })
    compteurs["lignes_rendues"]["index.html"] = len(departements)
    return valeurs


_CONSTRUCTEURS = {"index.html": _page_accueil, "liste.html": _page_liste,
                  "indicateur.html": _page_indicateur}


# ---------------------------------------------------------------------------
# contrat A
# ---------------------------------------------------------------------------

def _millesime(entrepot: Entrepot) -> str:
    etat = entrepot.etat()
    if not etat["lots"]:
        raise ErreurExportHtml("entrepôt vide : aucun lot chargé")
    if not etat["coherent"]:
        raise ErreurExportHtml("entrepôt incohérent : " + " ; ".join(etat["motifs"]))
    return etat["millesimes"][0]


def rendre(entrepot: Entrepot, dossier_gabarits: Path, dossier_sortie: Path) -> Dict[str, object]:
    """Rend chaque page de `PAGES` dans `dossier_sortie` — voir le contrat A
    en tête de module pour la forme exacte du dictionnaire retourné.

    Tous les gabarits sont lus et toutes les pages rendues en mémoire avant
    la première écriture : un gabarit manquant ou incomplet ne laisse jamais
    un site à moitié régénéré.
    """
    if entrepot.connexion is None:
        raise ErreurExportHtml("entrepôt non ouvert")
    dossier_gabarits = Path(dossier_gabarits)
    dossier_sortie = Path(dossier_sortie)

    base = Gabarit(dossier_gabarits / GABARIT_BASE)
    gabarits = {page: Gabarit(dossier_gabarits / GABARITS_PAGE.get(page, page))
                for page in PAGES}
    for gabarit in gabarits.values():
        gabarit.exiger(BLOCS_PAGE)
    base_modele = Template(base.chemin.read_text(encoding="utf-8"))

    compteurs: Dict[str, object] = {
        "millesime": _millesime(entrepot),
        "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pages_ecrites": [],
        "octets": {},
        "lignes_rendues": {},
    }

    rendus: Dict[str, str] = {}
    for page, gabarit in gabarits.items():
        valeurs = _CONSTRUCTEURS[page](gabarit, entrepot, compteurs)
        valeurs["millesime"] = _e(compteurs["millesime"])
        rendus[page] = _substituer(
            base_modele,
            {bloc: gabarit.remplir(bloc, valeurs) for bloc in BLOCS_PAGE}
            | {"millesime": valeurs["millesime"]},
            f"{base.chemin} (pour {page})")

    dossier_sortie.mkdir(parents=True, exist_ok=True)
    for page, contenu in rendus.items():
        donnees = contenu.encode("utf-8")
        (dossier_sortie / page).write_bytes(donnees)
        compteurs["pages_ecrites"].append(page)
        compteurs["octets"][page] = len(donnees)
    return compteurs


if __name__ == "__main__":
    import argparse
    import sys

    analyseur = argparse.ArgumentParser(
        description="Rendu HTML du site depuis l'entrepôt, par gabarits (OOM-100).")
    analyseur.add_argument("base", type=Path, help="fichier de l'entrepôt SQLite")
    analyseur.add_argument("--sortie", type=Path, default=Path("site"))
    analyseur.add_argument("--gabarits", type=Path, default=DOSSIER_GABARITS)
    arguments = analyseur.parse_args()

    if not arguments.base.is_file():
        sys.exit(f"entrepôt introuvable : {arguments.base}")
    try:
        with Entrepot(arguments.base) as entrepot:
            bilan = rendre(entrepot, arguments.gabarits, arguments.sortie)
    except ErreurExportHtml as erreur:
        sys.exit(f"export_html : {erreur}")
    print(f"Site écrit dans {arguments.sortie} — millésime {bilan['millesime']}")
    for page in bilan["pages_ecrites"]:
        print(f"    {page:<18}{bilan['lignes_rendues'][page]:>7} ligne(s)"
              f"{bilan['octets'][page] / 1024:>10.1f} Ko")
    print(f"    {bilan['nombre_etablissements']} établissement(s), "
          f"{bilan['sans_adresse_principale']} sans adresse principale, "
          f"{bilan['departement_non_resolu']} département(s) et "
          f"{bilan['categorie_non_resolue']} catégorie(s) non résolu(e)s, "
          f"{bilan['activites_total']} activité(s) sur "
          f"{bilan['etablissements_avec_activites']} établissement(s) "
          f"({bilan['nature_non_resolue']} nature(s) non résolue(s)), "
          f"indicateur : {bilan['indicateur_total_actifs']} actif(s) dont "
          f"{bilan['indicateur_exclus']} exclu(s), accueil : "
          f"{bilan['accueil_departements']} département(s) et "
          f"{bilan['accueil_categories']} catégorie(s).")
