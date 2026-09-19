"""
export_html.py — Couche 6 (restitution) : pages HTML du site, rendues depuis
l'entrepôt par gabarits (OOM-100), plus la page d'accueil (OOM-103) et une
page par département (OOM-106).

Produit les pages du site depuis `front/gabarits/`, selon un découpage :

- `index.html` (gabarit `accueil.html`, OOM-103) — porte d'entrée : mention de
  périmètre (comptage brut, qualification enfance/adolescents non appliquée),
  chiffres clés du millésime, effectifs par département et par catégorie (les
  marges `Resultat.par_departement`/`par_categorie` de la couche 5), source
  FINESS et licence. En découpage départemental, le tableau par département
  liste les 101 départements du référentiel plus « département indéterminé »,
  chacun avec un lien vers sa page ;
- `indicateur.html` — le tableau département × catégorie de la couche 5
  (`indicateurs.indicateur_departement_categorie`), dans l'ordre de
  `Resultat.lignes_triees`, donc le même que le CSV de `restituer` ;
- découpage `"departement"` (défaut, OOM-106) : une page par département
  (gabarit `departement.html`), chacune ne portant que ses établissements,
  avec leurs activités de niveau `ET` dans un `<details>` — voir contrat B ;
- découpage `"national"` : `liste.html` — tous les établissements sur une
  seule page (même lecture qu'`export_front.etablissements_bruts` et
  `activites_par_etablissement`). Conservé pour consultation locale : à
  l'échelle réelle (~55 Mo) il viole D9.

CONTRAT A — figé par OOM-100, consommé par OOM-102, OOM-103, OOM-104
-----------------------------------------------------------------
    rendre(entrepot, dossier_gabarits, dossier_sortie,
           decoupage="departement") -> dict

`entrepot` est un `Entrepot` ouvert ; `dossier_gabarits` contient `base.html`
et un gabarit par page (`accueil.html`, `indicateur.html`, plus
`departement.html` ou `liste.html` selon le découpage) ; `dossier_sortie` est
créé au besoin et reçoit les pages — l'accueil publié en `index.html`
(`GABARITS_PAGE`). `decoupage` (paramètre nommé ajouté par OOM-106) vaut
`"departement"` ou `"national"` (`DECOUPAGES`). Le dictionnaire retourné, sur
le modèle d'`export_front.exporter` :

    millesime              str        millésime unique de l'entrepôt
    genere_le              str        horodatage du rendu (ISO, seconde)
    decoupage              str        découpage appliqué
    pages_ecrites          list[str]  chemins relatifs des pages écrites (`/`
                                      comme séparateur), dans l'ordre
    octets                 dict       {page: taille en octets}
    lignes_rendues         dict       {page: lignes de tableau principal}
    nombre_etablissements  int        tous les établissements rendus
                                      (= lignes_rendues["liste.html"] en
                                      national, = somme des pages
                                      départementales en départemental)
    sans_adresse_principale, departement_non_resolu, categorie_non_resolue
                           int        mêmes définitions qu'export_front
    departement_hors_referentiel
                           int        département dérivé mais absent de
                                      `referentiels/departements.csv` (975,
                                      98x…) — rangé en page indéterminée
    activites_total, etablissements_avec_activites
                           int        mêmes définitions qu'export_front
    nature_non_resolue     int        = activites_total tant qu'aucune
                                      nomenclature de nature n'est versionnée
    indicateur_lignes      int        = lignes_rendues["indicateur.html"]
    indicateur_total_actifs, indicateur_exclus
                           int        Resultat.total_actifs / Resultat.exclus()
    accueil_departements, accueil_categories
                           int        départements / catégories présents dans
                                      les marges de la couche 5
    pages_departement      dict       {code ou "indetermine": établissements}
                                      (découpage départemental seulement ;
                                      vide en national)
    actifs_copies          list[str]  fichiers de `actifs/` copiés (OOM-102)
    octets_actifs          dict       {fichier: taille en octets}

CONTRAT B — chemins du site, figé par OOM-106, consommé par OOM-107
-----------------------------------------------------------------
Relatifs à `dossier_sortie` (`site/` par défaut) ; ils ne bougeront plus :

    index.html, indicateur.html     pages nationales
    departement/<code>.html         une page par département du référentiel
                                    `referentiels/departements.csv` (101 au
                                    COG 2025), y compris sans établissement ;
                                    `<code>` = code département INSEE en texte,
                                    tel qu'au référentiel : `01`…`95`, `2A`,
                                    `2B`, `971`…`976` — jamais un nombre
    departement/indetermine.html    établissements dont le `cog_commune` est
                                    absent, non résolu, ou résolu en un code
                                    hors référentiel — visibles, jamais écartés
    donnees/activites/<code>.json   fragments d'activités d'un département,
    donnees/activites/indetermine.json
                                    même `<code>` que la page ; produits et
                                    chargés à la demande par OOM-107 — pas
                                    encore écrits ici (les activités restent
                                    embarquées dans les pages départementales)
    actifs/                         feuille de style et îlots JS (OOM-102)

Tous les liens entre pages sont relatifs (le site est servi sous un
sous-chemin GitHub Pages) : une page de `departement/` atteint la racine par
`../`. Aucune page ne charge de JSON national.

ACTIFS (OOM-102) — le dossier `actifs/` voisin de `dossier_gabarits` (feuille
de style commune, îlots JS) est recopié tel quel dans `dossier_sortie/actifs/`
après les pages ; son absence est une erreur levée avant toute écriture.

Lève `ErreurExportHtml` — avant d'écrire quoi que ce soit — si un gabarit ou
un bloc manque (le message porte le chemin attendu), si un gabarit réclame une
valeur que le module ne fournit pas, si le référentiel des départements est
illisible, si la somme des pages départementales diffère du total des
établissements, ou si l'entrepôt est incohérent (plusieurs millésimes, source
chargée deux fois, aucun lot) : un export ne sort pas d'un entrepôt en échec
(D6).

GABARITS — des trous, pas de logique
-----------------------------------------------------------------
Un gabarit est du HTML lisible découpé en blocs nommés :

    <!-- BLOC nom -->…<!-- FIN nom -->

chacun étant un `string.Template` de la stdlib (`$valeur`, `$$` pour un `$`
littéral). Le texte hors blocs n'est pas publié (il sert à documenter le
gabarit). `base.html` est un seul gabarit, sans blocs, dont les trous `$titre`,
`$style`, `$contenu`, `$script`, `$pied` et `$millesime` reçoivent les blocs
homonymes de la page, `$racine` le préfixe relatif vers la racine du site
(`""` ou `"../"`) et `$lien_etablissements` la cible du lien de navigation
« Établissements ». Les blocs de ligne (`ligne`, `option`, `activite`…) sont
substitués une fois par élément puis concaténés par ce module ; quand une page
a deux variantes (département vide ou non, accueil national ou découpé), le
choix du bloc est fait ici.

Toute décision — libellé de repli d'un code non résolu, classe d'état,
largeur de barre, total, rattachement d'un établissement à une page — est
prise ici, en Python, jamais dans un gabarit (D7). Toute valeur issue des
données est échappée (`html.escape`) avant substitution ; les fragments déjà
rendus sont insérés tels quels.

Ce module ne lit l'entrepôt qu'au travers des couches existantes
(`export_front`, `indicateurs`, `Entrepot.etat`) et la liste des départements
qu'au travers de `territoires.charger_departements` : aucune requête SQL ici,
aucune liste de départements en dur (D4).

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import html
import shutil
import re
import time
from pathlib import Path
from string import Template
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from entrepot import Entrepot
from export_front import activites_par_etablissement, etablissements_bruts
from indicateurs import Resultat, etat_objet_actif, indicateur_departement_categorie
from territoires import ErreurTerritoires, charger_departements

__all__ = ["rendre", "ErreurExportHtml", "GABARIT_BASE", "PAGES", "DOSSIER_GABARITS",
           "DECOUPAGES", "PAGES_NATIONALES", "GABARIT_DEPARTEMENT",
           "DOSSIER_DEPARTEMENT", "PAGE_INDETERMINEE", "chemin_page_departement"]

GABARIT_BASE = "base.html"
# Pages du découpage national (historique OOM-100).
PAGES = ("index.html", "liste.html", "indicateur.html")
DECOUPAGES = ("departement", "national")
# Pages nationales écrites à la racine, par découpage.
PAGES_NATIONALES = {"departement": ("index.html", "indicateur.html"), "national": PAGES}
# Gabarit d'une page quand il ne porte pas son nom (l'accueil est publié en
# `index.html`, porte d'entrée par défaut d'un site statique).
GABARITS_PAGE = {"index.html": "accueil.html"}
GABARIT_DEPARTEMENT = "departement.html"
DOSSIER_DEPARTEMENT = "departement"
PAGE_INDETERMINEE = "indetermine"
DOSSIER_GABARITS = Path(__file__).resolve().parent.parent / "front" / "gabarits"

# Blocs que chaque gabarit de page doit fournir à `base.html`.
BLOCS_PAGE = ("titre", "pied", "style", "contenu", "script")

_MOTIF_BLOC = re.compile(r"<!-- BLOC (\w+) -->\n?(.*?)\n?<!-- FIN \1 -->", re.DOTALL)

_CLASSES_ETAT = {"A": "etat-actif", "I": "etat-inactif"}


class ErreurExportHtml(Exception):
    """Gabarit manquant ou incomplet, ou entrepôt impropre à l'export."""


def chemin_page_departement(code: str) -> str:
    """Chemin relatif (contrat B) de la page d'un département, ou de la page
    indéterminée pour `PAGE_INDETERMINEE`. `code` est pris tel quel : du texte."""
    return f"{DOSSIER_DEPARTEMENT}/{code}.html"


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
# lecture commune : établissements et activités
# ---------------------------------------------------------------------------

class _Donnees:
    """Lectures de l'entrepôt partagées par les pages d'un même rendu, faites
    une seule fois (couches 4-5 existantes, jamais de SQL ici)."""

    def __init__(self, entrepot: Entrepot) -> None:
        self.entrepot = entrepot
        self._etablissements: Optional[List[Dict[str, object]]] = None
        self._activites: Optional[Dict[str, List[Dict[str, object]]]] = None
        self._resultat: Optional[Resultat] = None
        self.departements: Dict[str, str] = {}

    def etablissements(self) -> List[Dict[str, object]]:
        if self._etablissements is None:
            self._etablissements = etablissements_bruts(self.entrepot)
        return self._etablissements

    def activites(self) -> Dict[str, List[Dict[str, object]]]:
        if self._activites is None:
            self._activites = activites_par_etablissement(self.entrepot)
        return self._activites

    def resultat(self) -> Resultat:
        if self._resultat is None:
            resultat = indicateur_departement_categorie(self.entrepot)
            if not resultat.verifier_total():
                raise ErreurExportHtml(
                    "indicateur incohérent : tableau + exclusions != total actifs")
            self._resultat = resultat
        return self._resultat

    def page_de(self, etablissement: Mapping[str, object]) -> str:
        """Code de la page départementale d'un établissement : son code
        département s'il est au référentiel, sinon `PAGE_INDETERMINEE`."""
        code = etablissement["code_departement"]
        return code if code in self.departements else PAGE_INDETERMINEE

    def par_page(self) -> Dict[str, List[Dict[str, object]]]:
        """{code: établissements}, une entrée par département du référentiel
        (dans son ordre) puis `PAGE_INDETERMINEE` — même vide."""
        pages: Dict[str, List[Dict[str, object]]] = {code: [] for code in self.departements}
        pages[PAGE_INDETERMINEE] = []
        for etablissement in self.etablissements():
            pages[self.page_de(etablissement)].append(etablissement)
        return pages


def _compter_etablissements(donnees: _Donnees, compteurs: Dict[str, object]) -> None:
    etablissements = donnees.etablissements()
    activites = donnees.activites()
    compteurs.update({
        "nombre_etablissements": len(etablissements),
        "sans_adresse_principale": sum(1 for e in etablissements if e["cog_commune"] is None),
        "departement_non_resolu": sum(
            1 for e in etablissements
            if e["cog_commune"] is not None and e["code_departement"] is None),
        "departement_hors_referentiel": sum(
            1 for e in etablissements
            if e["code_departement"] is not None
            and donnees.departements and e["code_departement"] not in donnees.departements),
        "categorie_non_resolue": sum(
            1 for e in etablissements
            if e["code_categorie"] is not None and e["libelle_categorie"] is None),
        "activites_total": sum(len(lignes) for lignes in activites.values()),
        "etablissements_avec_activites": len(activites),
        "nature_non_resolue": sum(
            1 for lignes in activites.values() for a in lignes if a["libelle_nature"] is None),
    })


# ---------------------------------------------------------------------------
# fragments communs aux listes d'établissements
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


def _departement_affiche(e: Mapping[str, object], departements: Mapping[str, str]) -> str:
    """Texte de la colonne « Département » : le code résolu, ou un repli
    explicite qui dit pourquoi l'établissement est en page indéterminée."""
    code = e["code_departement"]
    if code is None:
        return "[non résolu]" if e["cog_commune"] else "[absent]"
    if departements and code not in departements:
        return f"{code} [hors référentiel]"
    return str(code)


def _lignes_etablissements(gabarit: Gabarit, etablissements: List[Dict[str, object]],
                           activites: Mapping[str, List[Dict[str, object]]],
                           departements: Mapping[str, str]) -> str:
    return gabarit.repeter("ligne", ({
        "num_finess": _e(e["num_finess_et"]),
        "nom": _e(e["nom"]),
        "code_categorie": _e(e["code_categorie"]),
        "libelle_categorie": _e(e["libelle_categorie"]),
        "categorie": _e(e["libelle_categorie"] or (
            "[non résolu]" if e["code_categorie"] else "[absent]")),
        "code_departement": _e(e["code_departement"]),
        "departement": _e(_departement_affiche(e, departements)),
        "code_postal": _e(e["code_postal"]),
        "code_etat": _e(e["etat_objet"]),
        "etat": _e(e["etat_libelle"]),
        "classe_etat": _CLASSES_ETAT.get(e["etat_objet"], ""),
        "activites": _activites(gabarit, activites.get(e["num_finess_et"], [])),
    } for e in etablissements), "\n")


# ---------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------

def _page_liste(gabarit: Gabarit, donnees: _Donnees,
                compteurs: Dict[str, object]) -> Dict[str, str]:
    etablissements = donnees.etablissements()
    valeurs = dict(compteurs)
    valeurs.update({
        "lignes": _lignes_etablissements(gabarit, etablissements, donnees.activites(),
                                         donnees.departements),
        "options_departement": _options(gabarit, (e["code_departement"] for e in etablissements)),
        "options_categorie": _options(gabarit, (e["libelle_categorie"] for e in etablissements)),
    })
    compteurs["lignes_rendues"]["liste.html"] = len(etablissements)
    return valeurs


def _page_indicateur(gabarit: Gabarit, donnees: _Donnees,
                     compteurs: Dict[str, object]) -> Dict[str, str]:
    resultat = donnees.resultat()
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


def _accueil_departements(gabarit: Gabarit, donnees: _Donnees,
                          departements: List[Tuple[str, int]]) -> Tuple[str, int]:
    """Section « par département » de l'accueil et son nombre de lignes.

    National : les départements des marges de la couche 5, sans lien.
    Départemental : chaque département du référentiel, puis « indéterminé »,
    avec un lien vers sa page (contrat B). L'effectif affiché reste la marge
    de la couche 5 (actifs répartis) ; celui de la ligne « indéterminé » est
    la somme des marges des codes hors référentiel, de sorte que la colonne
    totalise toujours `Resultat.dans_tableau()`.
    """
    if not donnees.departements:
        lignes = gabarit.repeter("departement", (
            {"code_departement": _e(d), "effectif": n} for d, n in departements), "\n")
        return gabarit.remplir("departements_national", {
            "nombre_departements": len(departements), "departements": lignes}), len(departements)

    marges = dict(departements)
    pages = donnees.par_page()
    lignes_page = [
        {"lien": _e(chemin_page_departement(code)), "code_departement": _e(code),
         "libelle_departement": _e(libelle), "effectif": marges.get(code, 0),
         "fiches": len(pages[code])}
        for code, libelle in donnees.departements.items()]
    indeterminee = gabarit.remplir("departement_indetermine_lien", {
        "lien": _e(chemin_page_departement(PAGE_INDETERMINEE)),
        "effectif": sum(n for d, n in departements if d not in donnees.departements),
        "fiches": len(pages[PAGE_INDETERMINEE])})
    return gabarit.remplir("departements_decoupes", {
        "nombre_departements": len(departements),
        "nombre_pages": len(lignes_page) + 1,
        "departements": gabarit.repeter("departement_lien", lignes_page, "\n")
                        + "\n" + indeterminee,
    }), len(lignes_page) + 1


def _page_accueil(gabarit: Gabarit, donnees: _Donnees,
                  compteurs: Dict[str, object]) -> Dict[str, str]:
    """Accueil (OOM-103) : tous les chiffres viennent de la couche 5
    (`Resultat` et ses marges) ou de `Entrepot.etat` — rien n'est recompté ici,
    sinon le nombre de fiches de chaque page départementale."""
    resultat = donnees.resultat()
    departements = resultat.par_departement()
    categories = resultat.par_categorie()
    lots = donnees.entrepot.etat()["lots"]

    compteurs.update({
        "accueil_departements": len(departements),
        "accueil_categories": len(categories),
    })
    section, lignes = _accueil_departements(gabarit, donnees, departements)
    valeurs = dict(compteurs)
    valeurs.update({
        "total_actifs": resultat.total_actifs,
        "dans_tableau": resultat.dans_tableau(),
        "exclus": resultat.exclus(),
        "sans_departement": resultat.sans_departement,
        "categorie_inconnue": resultat.categorie_inconnue,
        "nombre_departements": len(departements),
        "nombre_categories": len(categories),
        "detail": gabarit.remplir(
            "detail_departement" if donnees.departements else "detail_national", {}),
        "section_departements": section,
        "categories": gabarit.repeter("categorie", (
            {"libelle_categorie": _e(c), "effectif": n} for c, n in categories), "\n"),
        "lots": gabarit.repeter("lot", (
            {"source": _e(l["source"]), "millesime": _e(l["millesime"]),
             "fichier": _e(l["fichier"]), "empreinte": _e(l["empreinte"])}
            for l in lots), "\n"),
    })
    compteurs["lignes_rendues"]["index.html"] = lignes
    return valeurs


def _page_departement(gabarit: Gabarit, donnees: _Donnees, code: str,
                      etablissements: List[Dict[str, object]],
                      compteurs: Dict[str, object]) -> Dict[str, str]:
    """Une page départementale (OOM-106) : seulement ses établissements, avec
    leurs activités embarquées ; page explicite même sans établissement."""
    activites = donnees.activites()
    indeterminee = code == PAGE_INDETERMINEE
    avec_activites = sum(1 for e in etablissements if e["num_finess_et"] in activites)
    valeurs = dict(compteurs)
    valeurs.update({
        "code_departement": "—" if indeterminee else _e(code),
        "libelle_departement": ("Département indéterminé" if indeterminee
                                else _e(donnees.departements[code])),
        "nombre_page": len(etablissements),
        "actifs_page": sum(1 for e in etablissements if etat_objet_actif(e["etat_objet"])),
        "activites_page": sum(len(activites.get(e["num_finess_et"], [])) for e in etablissements),
        "avec_activites_page": avec_activites,
        "millesime": _e(compteurs["millesime"]),
    })
    valeurs["explication"] = gabarit.remplir(
        "explication_indeterminee" if indeterminee else "explication", valeurs)
    if etablissements:
        valeurs["tableau"] = gabarit.remplir("tableau", {
            "nombre_page": len(etablissements),
            "lignes": _lignes_etablissements(gabarit, etablissements, activites,
                                             donnees.departements),
            "options_categorie": _options(
                gabarit, (e["libelle_categorie"] for e in etablissements)),
        })
    else:
        valeurs["tableau"] = gabarit.remplir("aucun", valeurs)
    compteurs["lignes_rendues"][chemin_page_departement(code)] = len(etablissements)
    return valeurs


_CONSTRUCTEURS = {"index.html": _page_accueil, "liste.html": _page_liste,
                  "indicateur.html": _page_indicateur}


# ---------------------------------------------------------------------------
# actifs (OOM-102)
# ---------------------------------------------------------------------------

def _actifs(dossier_gabarits: Path) -> List[Path]:
    """Fichiers du dossier `actifs/` voisin des gabarits, triés par nom."""
    dossier = dossier_gabarits.parent / "actifs"
    if not dossier.is_dir():
        raise ErreurExportHtml(f"dossier d'actifs manquant : {dossier}")
    return sorted(chemin for chemin in dossier.iterdir() if chemin.is_file())


def _copier_actifs(actifs: List[Path], dossier_sortie: Path, compteurs: Dict[str, object]) -> None:
    cible = dossier_sortie / "actifs"
    cible.mkdir(parents=True, exist_ok=True)
    compteurs["actifs_copies"] = []
    compteurs["octets_actifs"] = {}
    for chemin in actifs:
        shutil.copyfile(chemin, cible / chemin.name)
        compteurs["actifs_copies"].append(chemin.name)
        compteurs["octets_actifs"][chemin.name] = chemin.stat().st_size


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


def rendre(entrepot: Entrepot, dossier_gabarits: Path, dossier_sortie: Path,
           decoupage: str = "departement") -> Dict[str, object]:
    """Rend les pages du découpage choisi dans `dossier_sortie` — voir les
    contrats A et B en tête de module pour la forme exacte du dictionnaire
    retourné et les chemins écrits.

    Tous les gabarits sont lus et toutes les pages rendues en mémoire avant
    la première écriture : un gabarit manquant ou incomplet ne laisse jamais
    un site à moitié régénéré.
    """
    if decoupage not in DECOUPAGES:
        raise ErreurExportHtml(
            f"découpage inconnu {decoupage!r} (attendu : {', '.join(DECOUPAGES)})")
    if entrepot.connexion is None:
        raise ErreurExportHtml("entrepôt non ouvert")
    dossier_gabarits = Path(dossier_gabarits)
    dossier_sortie = Path(dossier_sortie)

    base = Gabarit(dossier_gabarits / GABARIT_BASE)
    gabarits = {page: Gabarit(dossier_gabarits / GABARITS_PAGE.get(page, page))
                for page in PAGES_NATIONALES[decoupage]}
    if decoupage == "departement":
        gabarit_departement = Gabarit(dossier_gabarits / GABARIT_DEPARTEMENT)
        gabarit_departement.exiger(BLOCS_PAGE)
    for gabarit in gabarits.values():
        gabarit.exiger(BLOCS_PAGE)
    actifs = _actifs(dossier_gabarits)
    base_modele = Template(base.chemin.read_text(encoding="utf-8"))

    donnees = _Donnees(entrepot)
    if decoupage == "departement":
        try:
            donnees.departements = charger_departements()
        except ErreurTerritoires as erreur:
            raise ErreurExportHtml(f"référentiel des départements : {erreur}") from erreur

    compteurs: Dict[str, object] = {
        "millesime": _millesime(entrepot),
        "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "decoupage": decoupage,
        "pages_ecrites": [],
        "octets": {},
        "lignes_rendues": {},
        "pages_departement": {},
    }
    _compter_etablissements(donnees, compteurs)
    millesime = _e(compteurs["millesime"])
    lien_etablissements = ("index.html#par-departement" if decoupage == "departement"
                           else "liste.html")

    def habiller(page: str, gabarit: Gabarit, valeurs: Dict[str, object], racine: str) -> str:
        valeurs["millesime"] = millesime
        valeurs["racine"] = racine
        return _substituer(
            base_modele,
            {bloc: gabarit.remplir(bloc, valeurs) for bloc in BLOCS_PAGE}
            | {"millesime": millesime, "racine": racine,
               "lien_etablissements": racine + lien_etablissements},
            f"{base.chemin} (pour {page})")

    rendus: Dict[str, str] = {}
    for page, gabarit in gabarits.items():
        rendus[page] = habiller(page, gabarit, _CONSTRUCTEURS[page](gabarit, donnees, compteurs), "")

    if decoupage == "departement":
        for code, etablissements in donnees.par_page().items():
            page = chemin_page_departement(code)
            valeurs = _page_departement(gabarit_departement, donnees, code, etablissements,
                                        compteurs)
            rendus[page] = habiller(page, gabarit_departement, valeurs, "../")
            compteurs["pages_departement"][code] = len(etablissements)
        reparti = sum(compteurs["pages_departement"].values())
        if reparti != compteurs["nombre_etablissements"]:
            raise ErreurExportHtml(
                f"découpage incohérent : {reparti} établissement(s) répartis en pages "
                f"départementales pour {compteurs['nombre_etablissements']} au total")

    (dossier_sortie / DOSSIER_DEPARTEMENT if decoupage == "departement"
     else dossier_sortie).mkdir(parents=True, exist_ok=True)
    for page, contenu in rendus.items():
        donnees_page = contenu.encode("utf-8")
        (dossier_sortie / page).write_bytes(donnees_page)
        compteurs["pages_ecrites"].append(page)
        compteurs["octets"][page] = len(donnees_page)
    _copier_actifs(actifs, dossier_sortie, compteurs)
    return compteurs


if __name__ == "__main__":
    import argparse
    import sys

    analyseur = argparse.ArgumentParser(
        description="Rendu HTML du site depuis l'entrepôt, par gabarits (OOM-100, OOM-106).")
    analyseur.add_argument("base", type=Path, help="fichier de l'entrepôt SQLite")
    analyseur.add_argument("--sortie", type=Path, default=Path("site"))
    analyseur.add_argument("--gabarits", type=Path, default=DOSSIER_GABARITS)
    analyseur.add_argument("--decoupage", choices=DECOUPAGES, default="departement",
                           help="une page par département (défaut) ou une liste nationale")
    arguments = analyseur.parse_args()

    if not arguments.base.is_file():
        sys.exit(f"entrepôt introuvable : {arguments.base}")
    try:
        with Entrepot(arguments.base) as entrepot:
            bilan = rendre(entrepot, arguments.gabarits, arguments.sortie,
                           decoupage=arguments.decoupage)
    except ErreurExportHtml as erreur:
        sys.exit(f"export_html : {erreur}")
    print(f"Site écrit dans {arguments.sortie} — millésime {bilan['millesime']}, "
          f"découpage {bilan['decoupage']}")
    for page in bilan["pages_ecrites"]:
        if not page.startswith(DOSSIER_DEPARTEMENT + "/"):
            print(f"    {page:<18}{bilan['lignes_rendues'][page]:>7} ligne(s)"
                  f"{bilan['octets'][page] / 1024:>10.1f} Ko")
    if bilan["pages_departement"]:
        pages = [p for p in bilan["pages_ecrites"] if p.startswith(DOSSIER_DEPARTEMENT + "/")]
        lourde = max(pages, key=lambda p: bilan["octets"][p])
        vides = sum(1 for n in bilan["pages_departement"].values() if n == 0)
        print(f"    {DOSSIER_DEPARTEMENT}/ : {len(pages)} page(s), dont {vides} sans "
              f"établissement ; {bilan['pages_departement'][PAGE_INDETERMINEE]} en page "
              f"indéterminée ; la plus lourde {lourde} "
              f"({bilan['octets'][lourde] / 1024:.1f} Ko)")
    for actif in bilan["actifs_copies"]:
        print(f"    {'actifs/' + actif:<34}{bilan['octets_actifs'][actif] / 1024:>10.1f} Ko")
    print(f"    {bilan['nombre_etablissements']} établissement(s), "
          f"{bilan['sans_adresse_principale']} sans adresse principale, "
          f"{bilan['departement_non_resolu']} département(s) non résolu(s), "
          f"{bilan['departement_hors_referentiel']} hors référentiel, "
          f"{bilan['categorie_non_resolue']} catégorie(s) non résolue(s), "
          f"{bilan['activites_total']} activité(s) sur "
          f"{bilan['etablissements_avec_activites']} établissement(s) "
          f"({bilan['nature_non_resolue']} nature(s) non résolue(s)), "
          f"indicateur : {bilan['indicateur_total_actifs']} actif(s) dont "
          f"{bilan['indicateur_exclus']} exclu(s), accueil : "
          f"{bilan['accueil_departements']} département(s) et "
          f"{bilan['accueil_categories']} catégorie(s).")
