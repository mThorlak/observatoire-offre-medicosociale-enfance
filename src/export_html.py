"""
export_html.py — Couche 6 (restitution) : pages HTML du site, rendues depuis
l'entrepôt par gabarits (OOM-100), plus la page d'accueil (OOM-103) et une
page par département (OOM-106), paginée en sous-pages bornées (OOM-115).

Produit les pages du site depuis `front/gabarits/`, selon un découpage :

- `index.html` (gabarit `accueil.html`, OOM-103) — porte d'entrée : mention de
  périmètre (comptage brut, qualification enfance/adolescents non appliquée),
  chiffres clés du millésime, effectifs par département et par catégorie (les
  marges `Resultat.par_departement`/`par_categorie` de la couche 5), source
  FINESS et licence. En découpage départemental, le tableau par département
  liste les 101 départements du référentiel plus « département indéterminé »,
  chacun avec un lien vers sa page ;
- `indicateur.html` — sommaire du tableau département × catégorie de la
  couche 5 (`indicateurs.indicateur_departement_categorie`) : une ligne par
  département présent, liée à `indicateur/<code>.html` (gabarit
  `indicateur_departement.html`) qui porte ses cases, dans l'ordre de
  `Resultat.lignes_triees`, donc le même que le CSV de `restituer` (OOM-115,
  dans les deux découpages : le tableau national entier pèse 2,1 Mo) ;
- découpage `"departement"` (défaut, OOM-106, OOM-115) : une page par
  département (gabarit `departement.html`) qui ne porte aucune fiche mais
  liste ses sous-pages ; chaque sous-page (gabarit
  `departement_sous_page.html`) porte au plus `LIGNES_PAR_SOUS_PAGE`
  établissements du département, par numéro FINESS croissant ; leurs
  activités de niveau `ET` ne sont pas embarquées mais écrites dans un
  fragment JSON par sous-page, chargé à la demande au premier clic sur un
  `<details>` (OOM-107) — voir contrat B, PAGINATION et FRAGMENTS
  D'ACTIVITÉS ;
- découpage `"national"` : `liste.html` — tous les établissements sur une
  seule page (même lecture qu'`export_front.etablissements_bruts` et
  `activites_par_etablissement`). Conservé pour consultation locale : à
  l'échelle réelle (~55 Mo) il viole D9.

CONTRAT A — figé par OOM-100, consommé par OOM-102, OOM-103, OOM-104
-----------------------------------------------------------------
    rendre(entrepot, dossier_gabarits, dossier_sortie,
           decoupage="departement",
           lignes_par_sous_page=LIGNES_PAR_SOUS_PAGE) -> dict

`entrepot` est un `Entrepot` ouvert ; `dossier_gabarits` contient `base.html`
et un gabarit par page (`accueil.html`, `indicateur.html`, plus
`departement.html` ou `liste.html` selon le découpage) ; `dossier_sortie` est
créé au besoin et reçoit les pages — l'accueil publié en `index.html`
(`GABARITS_PAGE`). `decoupage` (paramètre nommé ajouté par OOM-106) vaut
`"departement"` ou `"national"` (`DECOUPAGES`) ; `lignes_par_sous_page`
(ajouté par OOM-115) borne la pagination départementale. Le dictionnaire
retourné, sur
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
                                      sous-pages départementales en
                                      départemental)
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
    indicateur_lignes      int        cases département × catégorie, = somme
                                      de pages_indicateur (vérifié)
    indicateur_pages       int        pages `indicateur/<code>.html`,
                                      = lignes_rendues["indicateur.html"]
    pages_indicateur       dict       {code: cases de sa page d'indicateur}
    indicateur_total_actifs, indicateur_exclus
                           int        Resultat.total_actifs / Resultat.exclus()
    accueil_departements, accueil_categories
                           int        départements / catégories présents dans
                                      les marges de la couche 5
    pages_departement      dict       {code ou "indetermine": établissements}
                                      (découpage départemental seulement ;
                                      vide en national)
    sous_pages_departement dict       {code ou "indetermine": [établissements
                                      de la sous-page 1, 2…]}, au moins une
                                      entrée par code, chacune au plus
                                      lignes_par_sous_page ; leur somme
                                      totale = nombre_etablissements
                                      (vérifié, D6) ; vide en national
    lignes_par_sous_page   int        borne appliquée
    fragments_ecrits       list[str]  chemins relatifs des fragments
                                      d'activités (OOM-107), un par
                                      sous-page ; vide en national
    octets_fragments       dict       {fragment: taille en octets}
    activites_fragments    int        activités écrites dans les fragments
    activites_orphelines   int        activités dont le `num_finess_et`
                                      n'est porté par aucun établissement
                                      rendu (extraits décalés, cf. OOM-44) :
                                      comptées, jamais tues ;
                                      activites_fragments + orphelines
                                      = activites_total (vérifié)
    actifs_copies          list[str]  fichiers de `actifs/` copiés (OOM-102)
    octets_actifs          dict       {fichier: taille en octets}

CONTRAT B — chemins du site, posé par OOM-106, révisé par OOM-115
-----------------------------------------------------------------
Relatifs à `dossier_sortie` (`site/` par défaut) :

    index.html, indicateur.html     pages nationales ; indicateur.html n'est
                                    que le sommaire de l'indicateur
    indicateur/<code>.html          cases de l'indicateur d'un département
                                    présent dans le tableau (OOM-115)
    departement/<code>.html         une page par département du référentiel
                                    `referentiels/departements.csv` (101 au
                                    COG 2025), y compris sans établissement :
                                    le sommaire de ses sous-pages, liées en
                                    HTML avec leurs effectifs ;
                                    `<code>` = code département INSEE en texte,
                                    tel qu'au référentiel : `01`…`95`, `2A`,
                                    `2B`, `971`…`976` — jamais un nombre
    departement/indetermine.html    même chose pour les établissements dont le
                                    `cog_commune` est absent, non résolu, ou
                                    résolu en un code hors référentiel —
                                    visibles, jamais écartés
    departement/<code>/<n>.html     sous-page `n` (1, 2…) : au plus
                                    `LIGNES_PAR_SOUS_PAGE` établissements ;
                                    au moins une par département, même vide
                                    (OOM-115)
    donnees/activites/<code>/<n>.json
                                    fragment d'activités de la sous-page de
                                    mêmes `<code>` et `<n>`, un par sous-page
                                    (OOM-107, OOM-115) — voir ci-dessous
    actifs/                         feuille de style et îlots JS (OOM-102)

Tous les liens entre pages sont relatifs (le site est servi sous un
sous-chemin GitHub Pages) : une page de `departement/` ou d'`indicateur/`
atteint la racine par `../`, une sous-page par `../../`. Aucune page ne
charge de JSON national.

PAGINATION (OOM-115) — bornée par construction
-----------------------------------------------------------------
Les établissements d'un département, dans l'ordre d'`etablissements_bruts`
(numéro FINESS croissant), sont découpés en tranches consécutives d'au plus
`LIGNES_PAR_SOUS_PAGE` (constante mesurée) : pas de cas particulier pour un
département qui tient en une tranche. La recherche et les filtres JS ne
portent que sur la sous-page affichée, ce que la sous-page écrit en clair.
Avant toute écriture, chaque page — sauf `PAGES_NON_BORNEES` (`liste.html`) —
est mesurée en octets bruts, comptée avec tous les actifs du site : au-delà
de `BUDGET_PAGE` (500 Ko, D9), `ErreurExportHtml` nomme les pages fautives et
rien n'est écrit.

FRAGMENTS D'ACTIVITÉS (OOM-107) — chargés à la demande, jamais en bloc
-----------------------------------------------------------------
Chaque sous-page départementale a son fragment
`donnees/activites/<code>/<n>.json`, de même structure qu'`activites.json`
d'`export_front` (inchangée) restreinte aux établissements de la sous-page : `{num_finess_et: [activité, ...]}`, clé
absente = aucune activité, `code_nature` brut et `libelle_nature` à `None`
(aucune nomenclature de nature versionnée, OOM-29). Écrit compact, même vide
(`{}`), pour qu'à toute sous-page corresponde un fragment. Un par sous-page
plutôt qu'un par département : le fragment du Nord pèse 3,1 Mo ; découpé
comme la page, celui que télécharge un clic reste proportionnel à ce qui est
affiché (710,7 Ko au plus sur l'extrait complet du 27/09/2026).

La page n'embarque que le nombre d'activités de chaque établissement (dans le
`<summary>` d'un `<details data-finess>`) et l'URL relative du fragment
(`data-fragment` de la table) ; aucune requête n'est émise au chargement.
L'îlot `actifs/activites.js` télécharge le fragment à la première ouverture
d'un panneau (une seule fois par page), puis remplit le panneau ; un échec de
`fetch` s'affiche dans le panneau (D6). Un établissement sans activité porte
« aucune » dans le HTML, sans panneau ni requête. Sans JavaScript, la page
garde toutes ses fiches et un lien `<noscript>` vers le fragment (D10).

ACTIFS (OOM-102) — le dossier `actifs/` voisin de `dossier_gabarits` (feuille
de style commune, îlots JS) est recopié tel quel dans `dossier_sortie/actifs/`
après les pages ; son absence est une erreur levée avant toute écriture.

Lève `ErreurExportHtml` — avant d'écrire quoi que ce soit — si un gabarit ou
un bloc manque (le message porte le chemin attendu), si un gabarit réclame une
valeur que le module ne fournit pas, si le référentiel des départements est
illisible, si la somme des sous-pages départementales diffère du total des
établissements ou celle des pages d'indicateur du nombre de cases, si une
page bornée dépasse `BUDGET_PAGE`, ou si l'entrepôt est incohérent (plusieurs millésimes, source
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
(`""` ou `"../"`), `$lien_etablissements` la cible du lien de navigation
« Établissements » et les valeurs de `MENTIONS_PIED` le pied de page commun
(OOM-55 : statut non officiel, attribution de la source, lien vers le dépôt,
licence du code) ; ces dernières sont aussi offertes aux blocs de page. Les blocs de ligne (`ligne`, `option`, `activite`…) sont
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
import json
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
           "DECOUPAGES", "PAGES_NATIONALES", "GABARIT_DEPARTEMENT", "GABARIT_SOUS_PAGE",
           "GABARIT_INDICATEUR_DEPARTEMENT", "DOSSIER_DEPARTEMENT", "DOSSIER_INDICATEUR",
           "PAGE_INDETERMINEE", "chemin_page_departement", "chemin_sous_page",
           "chemin_indicateur_departement", "DOSSIER_ACTIVITES", "chemin_fragment_activites",
           "LIGNES_PAR_SOUS_PAGE", "BUDGET_PAGE", "PAGES_NON_BORNEES", "decouper",
           "DEPOT", "MENTIONS_PIED"]

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
GABARIT_SOUS_PAGE = "departement_sous_page.html"
GABARIT_INDICATEUR_DEPARTEMENT = "indicateur_departement.html"
DOSSIER_DEPARTEMENT = "departement"
DOSSIER_INDICATEUR = "indicateur"
# Préfixes relatifs vers la racine du site : d'une page de `departement/` ou
# d'`indicateur/`, et d'une sous-page `departement/<code>/`.
RACINE_DEPARTEMENT = "../"
RACINE_SOUS_PAGE = "../../"
PAGE_INDETERMINEE = "indetermine"
DOSSIER_ACTIVITES = "donnees/activites"

# D9 (OOM-115) : aucune page au-delà de 500 Ko bruts au chargement initial.
BUDGET_PAGE = 500 * 1024
# Borne de pagination des pages départementales, mesurée sur l'extrait FINESS
# complet du 27/09/2026 (mesures/poids_site.md) : après allègement du
# balisage (OOM-115), une ligne d'établissement pèse 364 octets en médiane,
# 456 au plus ; le reste d'une sous-page 17,0 Ko au plus, les actifs 18,5 Ko.
# Mille fois la ligne la plus longue tient donc sous le budget (~480 Ko). La
# borne en lignes ne suffit pas à le garantir (des noms plus longs le
# feraient franchir) : `rendre` mesure aussi chaque page, voir BUDGET_PAGE.
LIGNES_PAR_SOUS_PAGE = 1000
# Pages non bornées par construction : la liste nationale (consultation
# locale, ~55 Mo à l'échelle réelle, viole D9 en connaissance de cause).
PAGES_NON_BORNEES = ("liste.html",)
# Un code servant de nom de fichier : lettres et chiffres seulement.
# Pied de page commun (OOM-55) : de quoi citer le site honnêtement, sur chaque
# page et sous-page. Valeurs fixées ici et substituées dans `base.html` (et
# offertes aux blocs de page) : le gabarit ne les compose pas (D7).
DEPOT = "https://github.com/mThorlak/observatoire-offre-medicosociale-enfance"
MENTIONS_PIED = {
    "statut_donnees": "Retraitement indépendant de données publiques, pas une donnée "
                      "officielle de l'administration.",
    "attribution_source": "FINESS, ministère chargé de la Santé, publié sur data.gouv.fr",
    "lien_depot": DEPOT,
    "licence_code": "EUPL 1.2",
    "lien_licence": DEPOT + "/blob/main/LICENSE",
}
_CODE_FICHIER = re.compile(r"[0-9A-Za-z]+")
DOSSIER_GABARITS = Path(__file__).resolve().parent.parent / "front" / "gabarits"

# Blocs que chaque gabarit de page doit fournir à `base.html`.
BLOCS_PAGE = ("titre", "pied", "style", "contenu", "script")

_MOTIF_BLOC = re.compile(r"<!-- BLOC (\w+) -->\n?(.*?)\n?<!-- FIN \1 -->", re.DOTALL)

_CLASSES_ETAT = {"A": "etat-actif", "I": "etat-inactif"}


class ErreurExportHtml(Exception):
    """Gabarit manquant ou incomplet, ou entrepôt impropre à l'export."""


def chemin_page_departement(code: str) -> str:
    """Chemin relatif (contrat B) de la page d'un département — le sommaire de
    ses sous-pages —, ou de la page indéterminée pour `PAGE_INDETERMINEE`.
    `code` est pris tel quel : du texte."""
    return f"{DOSSIER_DEPARTEMENT}/{code}.html"


def chemin_sous_page(code: str, numero: int) -> str:
    """Chemin relatif (contrat B) de la sous-page `numero` (1, 2…) d'un
    département ou de la page indéterminée."""
    return f"{DOSSIER_DEPARTEMENT}/{code}/{numero}.html"


def chemin_fragment_activites(code: str, numero: int) -> str:
    """Chemin relatif (contrat B) du fragment d'activités de la sous-page
    `chemin_sous_page(code, numero)` — mêmes `code` et `numero`."""
    return f"{DOSSIER_ACTIVITES}/{code}/{numero}.json"


def chemin_indicateur_departement(code: str) -> str:
    """Chemin relatif (contrat B) de la page de l'indicateur restreinte à un
    département."""
    return f"{DOSSIER_INDICATEUR}/{code}.html"


def decouper(elements: List[Dict[str, object]], borne: int) -> List[List[Dict[str, object]]]:
    """Tranches consécutives d'au plus `borne` éléments, dans l'ordre ; au
    moins une, même vide — un département sans établissement a une sous-page,
    comme les autres (pas de cas particulier)."""
    if borne < 1:
        raise ErreurExportHtml(f"borne de pagination invalide : {borne}")
    return [elements[i:i + borne] for i in range(0, len(elements), borne)] or [[]]


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


def _activites_differees(gabarit: Gabarit, num_finess: str,
                         activites: List[Dict[str, object]]) -> str:
    """Cellule d'activités d'une page départementale (OOM-107) : le nombre
    seulement, le détail étant chargé à la demande depuis le fragment."""
    if not activites:
        return gabarit.remplir("activites_aucune", {})
    return gabarit.remplir("activites_differees",
                           {"num_finess": _e(num_finess), "nombre": len(activites)})


def _lignes_etablissements(gabarit: Gabarit, etablissements: List[Dict[str, object]],
                           activites: Mapping[str, List[Dict[str, object]]],
                           departements: Mapping[str, str], differees: bool = False) -> str:
    cellule = ((lambda e, a: _activites_differees(gabarit, e["num_finess_et"], a)) if differees
               else (lambda e, a: _activites(gabarit, a)))
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
        "activites": cellule(e, activites.get(e["num_finess_et"], [])),
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


def _indicateur_par_departement(donnees: _Donnees) -> List[Tuple[str, List[Tuple[str, int]]]]:
    """Cases de l'indicateur groupées par département, dans l'ordre de
    `Resultat.lignes_triees` : [(code, [(catégorie, effectif)])]. Le code sert
    de nom de fichier : un code qui n'est pas fait de lettres et de chiffres
    est une erreur, jamais un chemin fabriqué (D6)."""
    groupes: Dict[str, List[Tuple[str, int]]] = {}
    for departement, categorie, nombre in donnees.resultat().lignes_triees():
        if not _CODE_FICHIER.fullmatch(str(departement)):
            raise ErreurExportHtml(
                f"code département {departement!r} impropre à un nom de page d'indicateur")
        groupes.setdefault(departement, []).append((categorie, nombre))
    return list(groupes.items())


def _page_indicateur(gabarit: Gabarit, donnees: _Donnees,
                     compteurs: Dict[str, object]) -> Dict[str, str]:
    """Sommaire de l'indicateur (OOM-115) : une ligne par département présent
    dans le tableau, liée à sa page `indicateur/<code>.html`."""
    resultat = donnees.resultat()
    groupes = _indicateur_par_departement(donnees)
    dans_tableau = resultat.dans_tableau()

    compteurs.update({
        "indicateur_lignes": sum(len(lignes) for _, lignes in groupes),
        "indicateur_pages": len(groupes),
        "indicateur_total_actifs": resultat.total_actifs,
        "indicateur_exclus": resultat.exclus(),
    })
    valeurs = dict(compteurs)
    valeurs.update({
        "lignes": gabarit.repeter("ligne", (
            {"lien": _e(chemin_indicateur_departement(d)), "code_departement": _e(d),
             "categories": len(lignes), "effectif": sum(n for _, n in lignes)}
            for d, lignes in groupes), "\n"),
        "total": dans_tableau,
        "total_actifs": resultat.total_actifs,
        "dans_tableau": dans_tableau,
        "sans_departement": resultat.sans_departement,
        "categorie_inconnue": resultat.categorie_inconnue,
    })
    compteurs["lignes_rendues"]["indicateur.html"] = len(groupes)
    return valeurs


def _page_indicateur_departement(gabarit: Gabarit, donnees: _Donnees, code: str,
                                 lignes: List[Tuple[str, int]],
                                 compteurs: Dict[str, object]) -> Dict[str, str]:
    """Cases de l'indicateur d'un département (OOM-115), la largeur de barre
    étant relative au plus grand effectif du département."""
    resultat = donnees.resultat()
    maximum = max((n for _, n in lignes), default=0) or 1
    valeurs = dict(compteurs)
    valeurs.update({
        "code_departement": _e(code),
        "lignes": gabarit.repeter("ligne", (
            {"libelle_categorie": _e(c), "effectif": n, "largeur": round(n / maximum * 100)}
            for c, n in lignes), "\n"),
        "lignes_page": len(lignes),
        "total": sum(n for _, n in lignes),
        "total_actifs": resultat.total_actifs,
        "dans_tableau": resultat.dans_tableau(),
    })
    compteurs["lignes_rendues"][chemin_indicateur_departement(code)] = len(lignes)
    compteurs["pages_indicateur"][code] = len(lignes)
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


def _actifs_parmi(etablissements: Iterable[Mapping[str, object]]) -> int:
    return sum(1 for e in etablissements if etat_objet_actif(e["etat_objet"]))


def _valeurs_departement(donnees: _Donnees, code: str, tranches: List[List[Dict[str, object]]],
                         compteurs: Dict[str, object]) -> Dict[str, object]:
    """Valeurs communes au sommaire d'un département et à ses sous-pages."""
    indeterminee = code == PAGE_INDETERMINEE
    tous = [e for tranche in tranches for e in tranche]
    valeurs = dict(compteurs)
    valeurs.update({
        "code_departement": "—" if indeterminee else _e(code),
        "libelle_departement": ("Département indéterminé" if indeterminee
                                else _e(donnees.departements[code])),
        "nombre_departement": len(tous),
        "actifs_departement": _actifs_parmi(tous),
        "nombre_sous_pages": len(tranches),
        "millesime": _e(compteurs["millesime"]),
    })
    return valeurs


def _page_departement(gabarit: Gabarit, donnees: _Donnees, code: str,
                      tranches: List[List[Dict[str, object]]], borne: int,
                      compteurs: Dict[str, object]) -> Dict[str, object]:
    """Page d'un département (OOM-106, OOM-115) : sommaire de ses sous-pages,
    liées en HTML avec leurs effectifs et leur plage de numéros FINESS ; ne
    porte aucune fiche. Page explicite même sans établissement."""
    valeurs = _valeurs_departement(donnees, code, tranches, compteurs)
    valeurs["lignes_par_sous_page"] = borne
    valeurs["explication"] = gabarit.remplir(
        "explication_indeterminee" if code == PAGE_INDETERMINEE else "explication", valeurs)
    valeurs["sous_pages"] = gabarit.repeter("sous_page", (
        {"lien": _e(f"{code}/{numero}.html"), "numero": numero, "effectif": len(tranche),
         "actifs": _actifs_parmi(tranche),
         "premier": _e(tranche[0]["num_finess_et"]) if tranche else "—",
         "dernier": _e(tranche[-1]["num_finess_et"]) if tranche else "—"}
        for numero, tranche in enumerate(tranches, 1)), "\n")
    compteurs["lignes_rendues"][chemin_page_departement(code)] = len(tranches)
    return valeurs


def _page_sous_page(gabarit: Gabarit, donnees: _Donnees, code: str,
                    tranches: List[List[Dict[str, object]]], numero: int,
                    compteurs: Dict[str, object]) -> Dict[str, object]:
    """Sous-page `numero` d'un département (OOM-115) : ses seuls
    établissements, leurs activités renvoyées au fragment de la sous-page,
    chargé à la demande (OOM-107) ; le texte dit que les filtres ne portent
    que sur elle."""
    activites = donnees.activites()
    etablissements = tranches[numero - 1]
    premiere = sum(len(t) for t in tranches[:numero - 1]) + 1
    valeurs = _valeurs_departement(donnees, code, tranches, compteurs)
    valeurs.update({
        "numero": numero,
        "nombre_page": len(etablissements),
        "actifs_page": _actifs_parmi(etablissements),
        "activites_page": sum(len(activites.get(e["num_finess_et"], [])) for e in etablissements),
        "avec_activites_page": sum(1 for e in etablissements if e["num_finess_et"] in activites),
        "premiere": premiere,
        "derniere": premiere + len(etablissements) - 1,
        "sommaire": _e(f"../{code}.html"),
    })
    valeurs["explication"] = gabarit.remplir(
        "explication_indeterminee" if code == PAGE_INDETERMINEE else "explication", valeurs)
    valeurs["limite"] = gabarit.remplir("limite" if etablissements else "limite_vide", valeurs)
    valeurs["precedente"] = (gabarit.remplir("precedente", {
        "lien": f"{numero - 1}.html", "numero": numero - 1}) if numero > 1 else "")
    valeurs["suivante"] = (gabarit.remplir("suivante", {
        "lien": f"{numero + 1}.html", "numero": numero + 1}) if numero < len(tranches) else "")
    if etablissements:
        valeurs["tableau"] = gabarit.remplir("tableau", {
            "nombre_page": len(etablissements),
            "fragment": _e(RACINE_SOUS_PAGE + chemin_fragment_activites(code, numero)),
            "lignes": _lignes_etablissements(gabarit, etablissements, activites,
                                             donnees.departements, differees=True),
            "options_categorie": _options(
                gabarit, (e["libelle_categorie"] for e in etablissements)),
        })
    else:
        valeurs["tableau"] = gabarit.remplir("aucun", valeurs)
    compteurs["lignes_rendues"][chemin_sous_page(code, numero)] = len(etablissements)
    return valeurs


def _fragment_activites(donnees: _Donnees, etablissements: List[Dict[str, object]]) -> bytes:
    """Fragment d'activités d'une page (OOM-107) : même structure
    qu'`export_front.activites_par_etablissement`, restreinte aux établissements
    de la page qui ont au moins une activité, dans l'ordre de la page."""
    activites = donnees.activites()
    contenu = {e["num_finess_et"]: activites[e["num_finess_et"]]
               for e in etablissements if e["num_finess_et"] in activites}
    return json.dumps(contenu, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _verifier_fragments(fragments: Mapping[str, bytes], donnees: _Donnees,
                        compteurs: Dict[str, object]) -> None:
    """Invariant D6 : chaque activité est dans un fragment, ou comptée comme
    orpheline (aucun établissement rendu ne porte son `num_finess_et`)."""
    rendus = {e["num_finess_et"] for e in donnees.etablissements()}
    orphelines = sum(len(lignes) for num, lignes in donnees.activites().items()
                     if num not in rendus)
    dans_fragments = sum(len(lignes) for contenu in fragments.values()
                         for lignes in json.loads(contenu).values())
    compteurs["activites_fragments"] = dans_fragments
    compteurs["activites_orphelines"] = orphelines
    if dans_fragments + orphelines != compteurs["activites_total"]:
        raise ErreurExportHtml(
            f"fragments d'activités incohérents : {dans_fragments} en fragments + "
            f"{orphelines} orpheline(s) pour {compteurs['activites_total']} au total")


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


def _verifier_budget(encodes: Mapping[str, bytes], octets_actifs: int) -> None:
    """D9 par construction (OOM-115) : chaque page bornée, comptée avec tous
    les actifs du site (majorant de ce qu'elle charge), tient dans
    `BUDGET_PAGE` ; sinon rien n'est écrit."""
    hors_budget = sorted(((len(contenu) + octets_actifs, page)
                          for page, contenu in encodes.items() if page not in PAGES_NON_BORNEES),
                         reverse=True)
    hors_budget = [(n, page) for n, page in hors_budget if n > BUDGET_PAGE]
    if hors_budget:
        raise ErreurExportHtml(
            f"budget D9 dépassé ({BUDGET_PAGE} octets par page, actifs compris) : "
            + ", ".join(f"{page} ({n} octets)" for n, page in hors_budget[:5])
            + (f" et {len(hors_budget) - 5} autre(s)" if len(hors_budget) > 5 else ""))


def rendre(entrepot: Entrepot, dossier_gabarits: Path, dossier_sortie: Path,
           decoupage: str = "departement",
           lignes_par_sous_page: int = LIGNES_PAR_SOUS_PAGE) -> Dict[str, object]:
    """Rend les pages du découpage choisi dans `dossier_sortie` — voir les
    contrats A et B en tête de module pour la forme exacte du dictionnaire
    retourné et les chemins écrits.

    Tous les gabarits sont lus et toutes les pages rendues en mémoire, et le
    budget D9 vérifié, avant la première écriture : un gabarit manquant ou
    incomplet, ou une page trop lourde, ne laisse jamais un site à moitié
    régénéré.
    """
    if decoupage not in DECOUPAGES:
        raise ErreurExportHtml(
            f"découpage inconnu {decoupage!r} (attendu : {', '.join(DECOUPAGES)})")
    if entrepot.connexion is None:
        raise ErreurExportHtml("entrepôt non ouvert")
    decouper([], lignes_par_sous_page)  # borne invalide : erreur avant toute lecture
    dossier_gabarits = Path(dossier_gabarits)
    dossier_sortie = Path(dossier_sortie)

    base = Gabarit(dossier_gabarits / GABARIT_BASE)
    gabarits = {page: Gabarit(dossier_gabarits / GABARITS_PAGE.get(page, page))
                for page in PAGES_NATIONALES[decoupage]}
    gabarits[GABARIT_INDICATEUR_DEPARTEMENT] = Gabarit(
        dossier_gabarits / GABARIT_INDICATEUR_DEPARTEMENT)
    if decoupage == "departement":
        gabarits[GABARIT_DEPARTEMENT] = Gabarit(dossier_gabarits / GABARIT_DEPARTEMENT)
        gabarits[GABARIT_SOUS_PAGE] = Gabarit(dossier_gabarits / GABARIT_SOUS_PAGE)
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
        "sous_pages_departement": {},
        "pages_indicateur": {},
        "lignes_par_sous_page": lignes_par_sous_page,
        "fragments_ecrits": [],
        "octets_fragments": {},
        "activites_fragments": 0,
        "activites_orphelines": 0,
    }
    _compter_etablissements(donnees, compteurs)
    millesime = _e(compteurs["millesime"])
    lien_etablissements = ("index.html#par-departement" if decoupage == "departement"
                           else "liste.html")

    mentions = {cle: _e(valeur) for cle, valeur in MENTIONS_PIED.items()}

    def habiller(page: str, gabarit: Gabarit, valeurs: Dict[str, object], racine: str) -> str:
        valeurs["millesime"] = millesime
        valeurs["racine"] = racine
        valeurs.update(mentions)
        return _substituer(
            base_modele,
            {bloc: gabarit.remplir(bloc, valeurs) for bloc in BLOCS_PAGE}
            | mentions
            | {"millesime": millesime, "racine": racine,
               "lien_etablissements": racine + lien_etablissements},
            f"{base.chemin} (pour {page})")

    rendus: Dict[str, str] = {}
    fragments: Dict[str, bytes] = {}
    for page in PAGES_NATIONALES[decoupage]:
        gabarit = gabarits[page]
        rendus[page] = habiller(page, gabarit, _CONSTRUCTEURS[page](gabarit, donnees, compteurs), "")

    gabarit = gabarits[GABARIT_INDICATEUR_DEPARTEMENT]
    for code, lignes in _indicateur_par_departement(donnees):
        page = chemin_indicateur_departement(code)
        rendus[page] = habiller(page, gabarit, _page_indicateur_departement(
            gabarit, donnees, code, lignes, compteurs), RACINE_DEPARTEMENT)
    if sum(compteurs["pages_indicateur"].values()) != compteurs["indicateur_lignes"]:
        raise ErreurExportHtml(
            f"indicateur incohérent : {sum(compteurs['pages_indicateur'].values())} case(s) "
            f"réparties en pages pour {compteurs['indicateur_lignes']} au total")

    if decoupage == "departement":
        for code, etablissements in donnees.par_page().items():
            tranches = decouper(etablissements, lignes_par_sous_page)
            page = chemin_page_departement(code)
            rendus[page] = habiller(page, gabarits[GABARIT_DEPARTEMENT], _page_departement(
                gabarits[GABARIT_DEPARTEMENT], donnees, code, tranches, lignes_par_sous_page,
                compteurs), RACINE_DEPARTEMENT)
            for numero, tranche in enumerate(tranches, 1):
                page = chemin_sous_page(code, numero)
                rendus[page] = habiller(page, gabarits[GABARIT_SOUS_PAGE], _page_sous_page(
                    gabarits[GABARIT_SOUS_PAGE], donnees, code, tranches, numero, compteurs),
                    RACINE_SOUS_PAGE)
                fragments[chemin_fragment_activites(code, numero)] = _fragment_activites(
                    donnees, tranche)
            compteurs["pages_departement"][code] = len(etablissements)
            compteurs["sous_pages_departement"][code] = [len(t) for t in tranches]
        # D6 : la somme porte sur les sous-pages, là où les fiches sont rendues.
        reparti = sum(sum(n) for n in compteurs["sous_pages_departement"].values())
        if reparti != compteurs["nombre_etablissements"]:
            raise ErreurExportHtml(
                f"découpage incohérent : {reparti} établissement(s) répartis en sous-pages "
                f"départementales pour {compteurs['nombre_etablissements']} au total")
        trop = [(code, n) for code, effectifs in compteurs["sous_pages_departement"].items()
                for n in effectifs if n > lignes_par_sous_page]
        if trop:
            raise ErreurExportHtml(f"sous-page(s) au-delà de {lignes_par_sous_page} lignes : {trop}")
        _verifier_fragments(fragments, donnees, compteurs)

    encodes = {page: contenu.encode("utf-8") for page, contenu in rendus.items()}
    _verifier_budget(encodes, sum(chemin.stat().st_size for chemin in actifs))

    for page, donnees_page in encodes.items():
        (dossier_sortie / page).parent.mkdir(parents=True, exist_ok=True)
        (dossier_sortie / page).write_bytes(donnees_page)
        compteurs["pages_ecrites"].append(page)
        compteurs["octets"][page] = len(donnees_page)
    for fragment, contenu_fragment in fragments.items():
        (dossier_sortie / fragment).parent.mkdir(parents=True, exist_ok=True)
        (dossier_sortie / fragment).write_bytes(contenu_fragment)
        compteurs["fragments_ecrits"].append(fragment)
        compteurs["octets_fragments"][fragment] = len(contenu_fragment)
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
    analyseur.add_argument("--lignes-par-sous-page", type=int, default=LIGNES_PAR_SOUS_PAGE,
                           help=f"borne de pagination départementale "
                                f"(défaut {LIGNES_PAR_SOUS_PAGE}, mesurée)")
    arguments = analyseur.parse_args()

    if not arguments.base.is_file():
        sys.exit(f"entrepôt introuvable : {arguments.base}")
    try:
        with Entrepot(arguments.base) as entrepot:
            bilan = rendre(entrepot, arguments.gabarits, arguments.sortie,
                           decoupage=arguments.decoupage,
                           lignes_par_sous_page=arguments.lignes_par_sous_page)
    except ErreurExportHtml as erreur:
        sys.exit(f"export_html : {erreur}")
    print(f"Site écrit dans {arguments.sortie} — millésime {bilan['millesime']}, "
          f"découpage {bilan['decoupage']}")
    dossiers = (DOSSIER_DEPARTEMENT + "/", DOSSIER_INDICATEUR + "/")
    for page in bilan["pages_ecrites"]:
        if not page.startswith(dossiers):
            print(f"    {page:<18}{bilan['lignes_rendues'][page]:>7} ligne(s)"
                  f"{bilan['octets'][page] / 1024:>10.1f} Ko")
    pages = [p for p in bilan["pages_ecrites"] if p.startswith(DOSSIER_INDICATEUR + "/")]
    if pages:
        lourde = max(pages, key=lambda p: bilan["octets"][p])
        print(f"    {DOSSIER_INDICATEUR}/ : {len(pages)} page(s), {bilan['indicateur_lignes']} "
              f"case(s) ; la plus lourde {lourde} ({bilan['octets'][lourde] / 1024:.1f} Ko)")
    if bilan["pages_departement"]:
        sous_pages = [chemin_sous_page(code, numero)
                      for code, effectifs in bilan["sous_pages_departement"].items()
                      for numero in range(1, len(effectifs) + 1)]
        lourde = max(sous_pages, key=lambda p: bilan["octets"][p])
        vides = sum(1 for n in bilan["pages_departement"].values() if n == 0)
        decoupes = sum(1 for n in bilan["sous_pages_departement"].values() if len(n) > 1)
        print(f"    {DOSSIER_DEPARTEMENT}/ : {len(bilan['pages_departement'])} page(s) de "
              f"département, dont {vides} sans établissement ; {len(sous_pages)} sous-page(s) "
              f"d'au plus {bilan['lignes_par_sous_page']} ligne(s), {decoupes} département(s) "
              f"en plusieurs ; {bilan['pages_departement'][PAGE_INDETERMINEE]} en page "
              f"indéterminée ; la plus lourde {lourde} ({bilan['octets'][lourde] / 1024:.1f} Ko)")
    if bilan["fragments_ecrits"]:
        lourd = max(bilan["fragments_ecrits"], key=lambda f: bilan["octets_fragments"][f])
        print(f"    {DOSSIER_ACTIVITES}/ : {len(bilan['fragments_ecrits'])} fragment(s), "
              f"{bilan['activites_fragments']} activité(s), "
              f"{bilan['activites_orphelines']} orpheline(s) sans établissement rendu ; "
              f"le plus lourd {lourd} ({bilan['octets_fragments'][lourd] / 1024:.1f} Ko), "
              f"chargé à la demande")
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
