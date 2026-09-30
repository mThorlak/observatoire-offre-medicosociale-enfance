"""test_export_html.py — Critères de sortie d'OOM-104, OOM-106 et OOM-115 (rendu
du site par gabarits, une page par département paginée en sous-pages bornées).

Vérifie `export_html.rendre` (contrats A et B) :

1. de bout en bout sur l'échantillon FINESS versionné (Structures + Activités),
   chargé dans un dossier temporaire, en découpage départemental (défaut),
   avec une borne de pagination réduite (`BORNE`) pour que des départements
   de l'échantillon tiennent en plusieurs sous-pages : accueil, sommaire de
   l'indicateur et une page d'indicateur par département, 101 pages
   départementales + la page indéterminée, chacune liant ses sous-pages en
   HTML, chaque sous-page ne portant qu'une tranche bornée de ses
   établissements (somme = total), liens relatifs, aucun JSON chargé, mention
   de périmètre, limite des filtres écrite, actifs copiés, aucun `$` non
   substitué ; la borne par défaut ; une page au-delà du budget D9 lève
   `ErreurExportHtml` sans rien écrire ;
1 bis. le découpage national : `liste.html` et ses compteurs, comme avant ;
1 ter. les activités chargées à la demande (OOM-107) : un fragment
   `donnees/activites/<code>/<n>.json` par sous-page, de même structure
   qu'`activites.json` (code_nature brut, libelle_nature None), aucune
   activité dans le HTML ; le site servi par `http.server` : le chargement
   initial d'une page (page + feuille de style + scripts) ne demande aucun
   fragment, le fragment est servi au chemin annoncé ; puis `activites.js`
   exécuté sous Node (DOM factice, vrai fetch vers ce serveur) : aucune
   requête avant clic, une seule au premier clic, panneau rempli, absence et
   échec de fetch affichés — ignoré, en le disant, si Node est absent ;
2. codes hors référentiel : catégorie `Z99` (repli `[non résolu]`, jamais un
   libellé inventé), et départements indéterminés (adresse absente, commune
   non résolue, collectivité `975` hors référentiel) rangés visiblement en
   page indéterminée, Corse en `2A.html` (D4, D6) ;
3. un gabarit manquant : échec bruyant, chemin dans le message, rien d'écrit.

1 quater. les cartes (OOM-113) : `carte.html` et une `carte/<code>.html` par
   département, aucun `<script src>` ni `<link href>` vers `vendor/` au
   chargement initial, chemins en data-* qui résolvent vers des fichiers
   écrits, filtre `dep` et cadrage sur l'emprise des points du GeoJSON
   d'`export_geo`, attribution IGN, liens sans JS, ancre `et-<finess>` de
   chaque point présente dans la sous-page que vise son `lien`, dépendances
   vendorisées copiées à l'identique (empreintes de front/vendor/README.md) ;
   puis `carte.js` exécuté sous Node (harnais `tests/js/harnais_carte.js`,
   doublures de MapLibre, pmtiles et fetch) : rien de chargé avant le clic,
   MapLibre chargé au clic, message visible en cas d'échec de MapLibre, du
   fond, de l'archive ou de WebGL ; et les vrais scripts vendorisés évalués
   pour vérifier qu'ils exposent l'API qu'emploie `carte.js`.
1 quinquies. le bandeau de couverture (OOM-112) : sur chaque carte, dans le
   HTML initial, avant le cadre, la part des localisés de son propre
   périmètre, le nombre de non-localisés décomposé (sans coordonnées,
   invalides) et le lien vers la page qui les liste tous ; chiffres égaux aux
   compteurs d'`export_geo`, somme des départements = national (D6), un
   bandeau incohérent avec le site lève `ErreurExportHtml` sans rien écrire ;
   en 2., les établissements sans département déterminé annoncés sur la
   carte nationale.

OOM-55 : le pied de page commun (lien vers le dépôt, statut non officiel,
source, licence du code EUPL 1.2) sur chaque type de page, valeurs fournies
par le module (`MENTIONS_PIED`), et le paragraphe « Méthode et
reproductibilité » de l'accueil.
"""
from __future__ import annotations
import functools, hashlib, html, http.server, json, re, shutil, subprocess, sys, tempfile, threading
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import finess_commun as fc
from chargement import charger
from contrat_source import CONTROLE_MINIMAL
from entrepot import Entrepot
from export_front import activites_par_etablissement, etablissements_bruts
from finess_activites import SourceFinessActivites
from finess_structures import SourceFinessStructures
from indicateurs import indicateur_departement_categorie
from nomenclatures import CodeCategorieInconnu, resoudre_categorie
from territoires import charger_departements
import export_geo
import export_html as eh

ECHANTILLON = Path(__file__).resolve().parent / "echantillon"
S = ECHANTILLON / "finess-structures-mensuel-202607-echantillon_json.gz"
A = ECHANTILLON / "finess-activites-mensuel-202607-echantillon_json.gz"
GABARITS = eh.DOSSIER_GABARITS
ACTIFS = GABARITS.parent / "actifs"
VENDOR = GABARITS.parent / "vendor"

# Un `$` suivi d'un identifiant ou d'une accolade : trou de gabarit non rempli.
_TROU = re.compile(r"\$[A-Za-z_{]")
# Un lien ou une ressource à chemin absolu : interdit, le site est servi sous
# un sous-chemin GitHub Pages.
_ABSOLU = re.compile(r'(?:href|src)="/')
DEPARTEMENTS = charger_departements()
CODES = list(DEPARTEMENTS) + [eh.PAGE_INDETERMINEE]
PAGES_DEP = [eh.chemin_page_departement(c) for c in CODES]
# Borne de pagination des tests : l'échantillon compte 314 établissements en
# Loire-Atlantique (44), 131 dans l'Ain (01) — plusieurs sous-pages.
BORNE = 100
# Une ligne d'établissement d'une sous-page (ses <td> suivent).
_LIGNE = re.compile(r'<tr id="et-[^"]*" data-cat="[^"]*" data-etat="[^"]*"><td>([^<]*)</td>')

ok = ko = 0


def verifier(intitule, condition, detail=""):
    global ok, ko
    if condition: ok += 1; print(f"  OK    {intitule}")
    else: ko += 1; print(f"  ECHEC {intitule} — {detail}")


def lire(dossier, page):
    return (dossier / page).read_text(encoding="utf-8")


_TYPES = {t.nom: t for t in fc.TOUS_LES_TYPES}


def inserer(connexion, table, **valeurs):
    """Insertion générique, pilotée par les colonnes déclarées dans le schéma."""
    colonnes = _TYPES[table].noms
    ligne = tuple(valeurs.get(c) for c in colonnes)
    marques = ",".join("?" for _ in colonnes)
    connexion.execute(
        f"INSERT INTO {table} ({','.join(colonnes)}) VALUES ({marques})", ligne)


LOT = dict(id_lot="l:202607:0000", source="finess_structures", millesime="202607",
           schema_version="v1.0.0", nom_fichier="f", empreinte="e", octets="1")

EJ = dict(num_finess_ej="010008400", pm_smsse_id="100", denomination="A",
          denomination_longue="A LONGUE", code_statut_juridique="60",
          code_type_personne_morale="1", date_creation="1980-01-01",
          etat_objet="A", date_derniere_maj="2026-01-01", id_lot=LOT["id_lot"])


def etablissement(num_finess_et, ege_id, code_categorie, nom):
    return dict(num_finess_et=num_finess_et, ege_id=ege_id,
                num_finess_ej=EJ["num_finess_ej"], pm_smsse_id=EJ["pm_smsse_id"],
                nom_court=nom, nom_long=nom, code_categorie=code_categorie,
                date_ouverture="1990-01-01", etat_objet="A",
                date_derniere_maj="2026-01-01", id_lot=LOT["id_lot"])


def adresse(ege_id, cog_commune):
    return dict(type_porteur="ET", id_porteur=ege_id, num_finess_porteur=ege_id,
                rang="1", code_usage_adresse="03", code_postal="01000",
                cog_commune=cog_commune, id_lot=LOT["id_lot"])


class _Journal(http.server.SimpleHTTPRequestHandler):
    """Sert `site/` et consigne chaque chemin demandé (le « journal serveur »)."""
    journal = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        _Journal.journal.append(self.path)
        super().do_GET()


def _sous_ressources(page_html):
    """Ce que charge un navigateur à l'ouverture de la page, sans action de
    l'utilisateur : feuilles de style, scripts, images, iframes (pas les <a>)."""
    return (re.findall(r'<link [^>]*href="([^"]+)"', page_html)
            + re.findall(r'<(?:script|img|iframe) [^>]*src="([^"]+)"', page_html))


def verifier_activites_a_la_demande(site, bilan, activites, attendu_par_page, fragment_de,
                                    pages):
    print("\n1 ter. Activités à la demande (OOM-107), un fragment par sous-page (OOM-115)")
    attendus = list(fragment_de.values())
    verifier("un fragment par sous-page départementale, au chemin du contrat B",
             bilan["fragments_ecrits"] == attendus
             and attendus[:2] == ["donnees/activites/01/1.json", "donnees/activites/01/2.json"],
             bilan["fragments_ecrits"][:3])
    verifier("chaque fragment sur disque, taille = octets annoncés",
             all((site / f).stat().st_size == bilan["octets_fragments"][f] for f in attendus))
    verifier("aucun fragment départemental d'avant OOM-115 (donnees/activites/<code>.json)",
             not list((site / eh.DOSSIER_ACTIVITES).glob("*.json")))
    fragments = {f: json.loads(lire(site, f)) for f in attendus}
    attendu = {fragment_de[p]: {n: activites[n] for n in nums if n in activites}
               for p, nums in attendu_par_page.items()}
    verifier("chaque fragment = activites_par_etablissement restreint à sa sous-page "
             "(structure inchangée)", fragments == attendu,
             [f for f in attendus if fragments[f] != attendu[f]][:3])
    verifier("activités des fragments = activites_total, 0 orpheline sur l'échantillon",
             bilan["activites_fragments"] == bilan["activites_total"]
             and bilan["activites_orphelines"] == 0, bilan["activites_fragments"])
    toutes = [a for f in fragments.values() for lignes in f.values() for a in lignes]
    verifier("code_nature brut, libelle_nature None partout (aucune nomenclature, OOM-29)",
             toutes and all(a["libelle_nature"] is None and a["code_nature"] for a in toutes))
    verifier("page vide : fragment « {} »",
             all(fragments[fragment_de[p]] == {}
                 for p, nums in attendu_par_page.items() if not nums))
    verifier("aucune activité embarquée dans les pages (ni ligne data-nature, ni tableau "
             "d'activités, ni capacité)",
             all("data-nature=" not in c and "<th>Capacité(s)</th>" not in c
                 and "capacites-liste" not in c for c in pages.values()))
    annonces = {n: int(k) for c in pages.values()
                for n, k in re.findall(r'<details data-finess="([^"]+)"><summary>(\d+) '
                                       r'activité', c)}
    verifier("chaque panneau annonce le nombre d'activités de son fragment",
             annonces == {n: len(l) for n, l in activites.items()}, len(annonces))
    sans = [n for nums in attendu_par_page.values() for n in nums if n not in activites]
    ligne_sans = next((l for c in pages.values() for l in c.splitlines()
                       if sans and f"<td>{sans[0]}</td>" in l), "")
    verifier("établissement sans activité : « aucune » explicite, sans panneau",
             sans and '<span class="code-brut">aucune</span>' in ligne_sans
             and "<details" not in ligne_sans, ligne_sans[-120:])
    page = pages["departement/44/2.html"]
    verifier("table : data-fragment relatif vers le fragment de sa sous-page",
             'data-fragment="../../donnees/activites/44/2.json"' in page)
    verifier("sans JS : lien <noscript> vers le fragment (D10)",
             '<noscript><p class="alerte">' in page
             and 'href="../../donnees/activites/44/2.json"' in page)
    verifier("îlot activites.js chargé en relatif, aucun script inline",
             'src="../../actifs/activites.js"' in page and "<script>" not in page)
    source_js = (ACTIFS / "activites.js").read_text(encoding="utf-8")
    verifier("activites.js : un seul appel fetch, dans la fonction de chargement différé",
             source_js.count("fetch(") == 1
             and re.search(r"function fragment\(\) \{\s*if \(!chargement\) \{\s*"
                           r"chargement = fetch\(", source_js) is not None)

    # Le site servi comme en local (py -3 -m http.server -d site).
    _Journal.journal = []
    serveur = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(_Journal, directory=str(site)))
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{serveur.server_port}/"
    try:
        url_page = urljoin(base, "departement/44/2.html")
        with urlopen(url_page) as r:
            servie = r.read().decode("utf-8")
        for ressource in _sous_ressources(servie):
            with urlopen(urljoin(url_page, ressource)) as r:
                r.read()
        initial = list(_Journal.journal)
        verifier("chargement initial servi : page, feuille de style, deux îlots, "
                 "aucune requête d'activités", initial == [
                     "/departement/44/2.html", "/actifs/ooms.css", "/actifs/filtres.js",
                     "/actifs/activites.js"], initial)
        url_fragment = urljoin(url_page, re.search(r'data-fragment="([^"]+)"', servie).group(1))
        with urlopen(url_fragment) as r:
            servi = json.loads(r.read().decode("utf-8"))
        verifier("« clic » : le fragment est servi au chemin annoncé, contenu attendu",
                 _Journal.journal[len(initial):] == ["/donnees/activites/44/2.json"]
                 and servi == fragments["donnees/activites/44/2.json"], _Journal.journal)
        _executer_ilot(site, base, fragments, page)
    finally:
        serveur.shutdown()
        serveur.server_close()


def _executer_ilot(site, base, fragments, page):
    """activites.js exécuté sous Node contre le serveur ; ignoré (dit) sans Node."""
    node = shutil.which("node")
    if node is None:
        print("  IGNORÉ activites.js sous Node : node absent du PATH")
        return
    avec = [{"finess": n, "nombre": int(k)}
            for n, k in re.findall(r'<details data-finess="([^"]+)"><summary>(\d+) ', page)]
    scenario = {
        "tables": [
            {"fragment": urljoin(base, "donnees/activites/44/2.json"),
             "details": avec[:2] + [{"finess": "000000000", "nombre": 1}]},
            {"fragment": urljoin(base, "donnees/activites/absent.json"),
             "details": avec[:1]},
        ],
        # ouvre 0, 1, rouvre 0, ouvre l'inconnu, puis deux fois le panneau en échec
        "ouvertures": [[0, 0], [0, 1], [0, 0], [0, 2], [1, 0], [1, 0]],
    }
    chemin = site.parent / "scenario.json"
    chemin.write_text(json.dumps(scenario), encoding="utf-8")
    harnais = Path(__file__).resolve().parent / "js" / "harnais_activites.js"
    fini = subprocess.run([node, str(harnais), str(ACTIFS / "activites.js"), str(chemin)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    if fini.returncode != 0:
        verifier("activites.js sous Node : exécution", False, fini.stderr[-500:])
        return
    r = json.loads(fini.stdout)
    o = [x["panneau"] for x in r["apres_ouverture"]]
    n = [x["requetes"] for x in r["apres_ouverture"]]
    attendu_0 = fragments["donnees/activites/44/2.json"][avec[0]["finess"]]
    verifier("Node : aucune requête au chargement de la page", r["requetes_initiales"] == [],
             r["requetes_initiales"])
    verifier("Node : premier clic -> une requête, vers le fragment de la page",
             n[0] == 1 and r["requetes"][0].endswith("/donnees/activites/44/2.json"), r["requetes"])
    verifier("Node : panneau rempli, une ligne par activité, natures brutes, « [non résolu] »",
             o[0]["chargees"] and o[0]["lignes"] == avec[0]["nombre"]
             and o[0]["natures"] == [a["code_nature"] for a in attendu_0]
             and "[non résolu]" in o[0]["texte"] and o[0]["evenements"] == 1, o[0])
    verifier("Node : deuxième panneau et réouverture sans nouvelle requête",
             n[1] == n[2] == 1 and o[1]["lignes"] == avec[1]["nombre"]
             and o[2]["lignes"] == avec[0]["nombre"] and o[2]["evenements"] == 1, n)
    verifier("Node : établissement absent du fragment -> message explicite, jamais vide",
             o[3]["alerte"] and "Aucune activité trouvée" in o[3]["alerte"] and not o[3]["vide"],
             o[3])
    verifier("Node : fetch en échec (404) -> message d'erreur avec statut et lien",
             o[4]["alerte"] and "Échec du chargement" in o[4]["alerte"]
             and "HTTP 404" in o[4]["alerte"]
             and o[4]["liens"] == [urljoin(base, "donnees/activites/absent.json")], o[4])
    verifier("Node : réouverture après échec -> nouvelle tentative, erreur toujours affichée",
             n[5] == n[4] + 1 and o[5]["alerte"] and "Échec du chargement" in o[5]["alerte"], n)


def _donnees_carte(contenu):
    """Attributs data-* de `#carte`, tels que les lit `dataset` (camelCase,
    entités décodées)."""
    div = re.search(r'<div class="carte" id="carte"[^>]*>', contenu)
    if not div:
        return {}
    return {re.sub(r"-(\w)", lambda m: m.group(1).upper(), cle): html.unescape(valeur)
            for cle, valeur in re.findall(r'data-([\w-]+)="([^"]*)"', div.group(0))}


def _hors_noscript(contenu):
    return re.sub(r"<noscript>.*?</noscript>", "", contenu, flags=re.DOTALL)


def _bandeau(contenu):
    """Le bandeau de couverture d'une carte, balisage compris, ou ''."""
    trouve = re.search(r'<section class="couverture" id="couverture".*?</section>', contenu,
                       re.DOTALL)
    return trouve.group(0) if trouve else ""


def _fr(n):
    return f"{n:,}".replace(",", " ")


COMPTEURS_GEO = ("total", "localises", "non_localises", "sans_coordonnees",
                 "coordonnees_invalides")


def verifier_couverture(site, bilan, geo):
    print("\n1 quinquies. Bandeau de couverture des cartes (OOM-112)")
    cartes = {p: lire(site, p) for p in bilan["pages_ecrites"]
              if p == eh.PAGE_CARTE or p.startswith(eh.DOSSIER_CARTE + "/")}
    bandeaux = {p: _bandeau(c) for p, c in cartes.items()}
    verifier("chaque carte porte un bandeau de couverture", all(bandeaux.values()),
             [p for p, b in bandeaux.items() if not b][:3])
    mal_places = [p for p, c in cartes.items()
                  if not (0 <= c.find('id="couverture"') < c.find('<div class="carte" id="carte"'))
                  or 'id="couverture"' not in _hors_noscript(c)
                  or re.search(r'<section class="couverture"[^>]*hidden', c)]
    verifier("bandeau dans le HTML initial, hors <noscript>, jamais caché, avant le cadre de "
             "la carte (D10)", not mal_places, mal_places[:3])

    # Les chiffres : ceux d'export_geo, calculés à part (GeoJSON), sans recalcul.
    nationale = bilan["couverture_cartes"][""]
    verifier("bilan : couverture nationale = compteurs d'export_geo.exporter",
             all(nationale[k] == geo[k] for k in COMPTEURS_GEO), (nationale, geo))
    national = bandeaux[eh.PAGE_CARTE]
    verifier("carte.html annonce 65,1 %, 1 141 sur 1 753, 612 non localisés dont 611 sans "
             "coordonnées et 1 invalide (échantillon)",
             "<strong>65,1 % des établissements du répertoire FINESS sont placés sur la "
             "carte : 1 141 sur 1 753.</strong>" in national
             and "612 n'y figurent pas : 611 sans coordonnées dans FINESS, 1 aux coordonnées "
             "invalides." in national, national)
    verifier("carte.html : la phrase sur les coordonnées invalides (interverties avec le "
             "Lambert 93), sans promesse de correction",
             "interverties avec les coordonnées Lambert 93" in national
             and "corrig" not in national, national)
    verifier("carte.html : lien vers l'accueil, où figurent tous les établissements",
             'href="index.html#par-departement">l\'accueil, par département</a>' in national)

    ecarts = []
    for code in DEPARTEMENTS:
        page = eh.chemin_carte_departement(code)
        chiffres = bilan["couverture_cartes"][code]
        attendu = geo["par_departement"][code]
        b = bandeaux[page]
        if (chiffres["localises"], chiffres["non_localises"]) \
                != (attendu["localises"], attendu["non_localises"]) \
                or chiffres["total"] != bilan["pages_departement"][code]:
            ecarts.append((code, "compteurs", chiffres, attendu))
        elif f'href="../{eh.chemin_page_departement(code)}">la page du département</a>' not in b:
            ecarts.append((code, "lien"))
        elif chiffres["total"] == 0:
            if "Aucun établissement FINESS du département" not in b:
                ecarts.append((code, "vide"))
        elif (f"{str(chiffres['part_localises']).replace('.', ',')} % des établissements "
              f"du département" not in b
              or f"{_fr(chiffres['localises'])} sur {_fr(chiffres['total'])}." not in b
              or f"{_fr(chiffres['non_localises'])} n'y figurent pas : "
                 f"{_fr(chiffres['sans_coordonnees'])} sans coordonnées dans FINESS, "
                 f"{_fr(chiffres['coordonnees_invalides'])} aux coordonnées invalides." not in b
              or ("interverties" in b) != bool(chiffres["coordonnees_invalides"])):
            ecarts.append((code, "texte", b))
    verifier("chaque carte départementale : ses propres chiffres (= export_geo), sa propre "
             "part, sa décomposition, lien vers la page du département", not ecarts, ecarts[:2])
    parts = {bilan["couverture_cartes"][c]["part_localises"] for c in DEPARTEMENTS
             if bilan["couverture_cartes"][c]["total"]}
    verifier("parts départementales distinctes, pas une moyenne nationale (44 : 58,3 %)",
             len(parts) > 1 and "58,3 % des établissements du département"
             in bandeaux["carte/44.html"], sorted(parts)[:5])
    indet = dict(geo["par_departement"][eh.PAGE_INDETERMINEE])
    indet["total"] = indet["localises"] + indet["non_localises"]
    sommes = {k: sum(bilan["couverture_cartes"][c][k] for c in DEPARTEMENTS)
              for k in ("total", "localises", "non_localises")}
    verifier("somme des bandeaux départementaux (+ indéterminés, sur aucune carte "
             "départementale) = bandeau national (D6)",
             all(sommes[k] + indet[k] == nationale[k] for k in sommes), (sommes, indet))
    verifier("échantillon : aucun indéterminé, la somme des bandeaux départementaux est "
             "exactement le national", indet["total"] == 0
             and all(sum(bilan["couverture_cartes"][c][k] for c in DEPARTEMENTS) == nationale[k]
                     for k in COMPTEURS_GEO), indet)
    verifier("aucun chiffre calculé dans le gabarit ni le JS : le bandeau n'est pas touché "
             "par carte.js", "couverture" not in (ACTIFS / "carte.js").read_text(encoding="utf-8"))


def verifier_cartes(site, bilan, geo, chemin_geo, etablissements, sous_pages):
    print("\n1 quater. Cartes (OOM-113) : îlot MapLibre à la demande")
    points = json.loads(chemin_geo.read_text(encoding="utf-8"))["features"]
    cartes = {p: lire(site, p) for p in bilan["pages_ecrites"]
              if p == eh.PAGE_CARTE or p.startswith(eh.DOSSIER_CARTE + "/")}
    verifier("une carte nationale et une par département du référentiel (101), aucune "
             "pour la page indéterminée",
             sorted(cartes) == sorted([eh.PAGE_CARTE] + [eh.chemin_carte_departement(c)
                                                         for c in DEPARTEMENTS])
             and not (site / eh.DOSSIER_CARTE / "indetermine.html").exists(), len(cartes))

    # D9 : rien de vendor/ au chargement initial, sur aucune page du site.
    vers_vendor = [p for p in bilan["pages_ecrites"]
                   if any("vendor/" in r for r in _sous_ressources(lire(site, p)))
                   or re.search(r'src="[^"]*vendor', lire(site, p))]
    verifier("aucune page ne charge vendor/ au chargement initial (<script src>, <link href>)",
             not vers_vendor, vers_vendor[:3])
    verifier("carte.html : chargement initial = feuille de style + carte.js, rien d'autre",
             _sous_ressources(cartes[eh.PAGE_CARTE]) == ["actifs/ooms.css", "actifs/carte.js"],
             _sous_ressources(cartes[eh.PAGE_CARTE]))
    verifier("carte/44.html : idem, en relatif (../)",
             _sous_ressources(cartes["carte/44.html"]) == ["../actifs/ooms.css",
                                                          "../actifs/carte.js"])
    source_js = (ACTIFS / "carte.js").read_text(encoding="utf-8")
    code_js = re.sub(r"/\*.*?\*/", "", source_js, flags=re.DOTALL)
    verifier("carte.js : aucune URL écrite en dur (chemins, fond et archive viennent de la page)",
             "http" not in code_js and "vendor/" not in code_js and "tuiles/" not in code_js
             and code_js.count("://") == 1 and '"pmtiles://" + archive' in code_js)
    cdn = [f for d in (GABARITS, ACTIFS) for f in d.iterdir()
           if re.search(r"https://.*cdn", f.read_text(encoding="utf-8"))]
    verifier("aucun CDN dans front/gabarits/ ni front/actifs/", not cdn, cdn)

    # Attributs data-* : chemins qui résolvent, archive et couche du contrat C.
    defauts = {}
    for page, contenu in cartes.items():
        d = _donnees_carte(contenu)
        racine = "" if page == eh.PAGE_CARTE else "../"
        dossier = (site / page).parent
        if d.get("racine") != racine: defauts[page] = f"racine {d.get('racine')!r}"
        elif d.get("archive") != racine + eh.ARCHIVE_TUILES: defauts[page] = "archive"
        elif d.get("couche") != eh.COUCHE_TUILES: defauts[page] = "couche"
        elif d.get("fond") != eh.FOND_CARTE: defauts[page] = "fond"
        elif not all((dossier / d.get(c, "?")).resolve().is_file()
                     for c in ("maplibre", "maplibreCss", "pmtiles")):
            defauts[page] = "dépendance vendorisée introuvable depuis la page"
        elif 'id="carte" hidden' not in contenu or 'id="carte-commande" hidden' not in contenu:
            defauts[page] = "carte ou bouton visible sans JS"
        elif eh.MENTIONS_FOND["attribution_fond"] not in contenu \
                or eh.MENTIONS_FOND["licence_fond"] not in contenu:
            defauts[page] = "attribution IGN absente"
    verifier("chaque carte : racine, archive tuiles/etablissements.pmtiles, couche, style IGN, "
             "MapLibre/pmtiles résolus vers site/vendor/, carte et bouton cachés sans JS, "
             "attribution IGN écrite", not defauts, list(defauts.items())[:3])
    verifier("attribution IGN transmise à MapLibre (data-attribution)",
             _donnees_carte(cartes["carte/44.html"])["attribution"]
             == eh.MENTIONS_FOND["attribution_fond"] == "© IGN – Plan IGN, Géoplateforme")

    # Filtre et cadrage : contre le GeoJSON d'export_geo, calculé à part.
    par_dep = {}
    for point in points:
        par_dep.setdefault(point["properties"]["dep"], []).append(point)
    decalages = []
    for code in DEPARTEMENTS:
        d = _donnees_carte(cartes[eh.chemin_carte_departement(code)])
        dedans = par_dep.get(code, [])
        if dedans:
            xs = [p["geometry"]["coordinates"][0] for p in dedans]
            ys = [p["geometry"]["coordinates"][1] for p in dedans]
            attendu = [round(min(xs), 6), round(min(ys), 6), round(max(xs), 6), round(max(ys), 6)]
        else:
            attendu = list(eh.EMPRISE_METROPOLE)
        if d["dep"] != code or json.loads(d["emprise"]) != attendu \
                or bilan["pages_carte"][code] != len(dedans):
            decalages.append((code, d["dep"], d["emprise"], attendu))
    verifier("carte départementale : filtre dep = code, cadrage = emprise de ses points dans "
             "le GeoJSON (métropole s'il n'en a aucun), points comptés",
             not decalages, decalages[:2])
    d_nat = _donnees_carte(cartes[eh.PAGE_CARTE])
    verifier("carte nationale : sans filtre, cadrée sur la métropole, tous les points comptés",
             d_nat["dep"] == "" and json.loads(d_nat["emprise"]) == list(eh.EMPRISE_METROPOLE)
             and bilan["pages_carte"][""] == len(points) == geo["localises"],
             (d_nat["dep"], bilan["pages_carte"].get("")))
    verifier("carte/44.html : « N sur M » localisés écrit dans la page",
             f"{len(par_dep['44'])} sur {sum(1 for x in etablissements if x['code_departement'] == '44')}"
             in cartes["carte/44.html"])
    vides = [c for c in DEPARTEMENTS if c not in par_dep]
    verifier("département sans point localisé : explication explicite, jamais une carte muette",
             vides and all("n'est localisé" in cartes[eh.chemin_carte_departement(c)]
                           for c in vides), vides[:3])
    libelles = {x["code_categorie"]: x["libelle_categorie"] for x in etablissements}
    manquants = [c for c in DEPARTEMENTS for p in par_dep.get(c, [])
                 if p["properties"]["categorie"] and libelles.get(p["properties"]["categorie"])
                 and json.loads(_donnees_carte(cartes[eh.chemin_carte_departement(c)])
                                ["categories"]).get(p["properties"]["categorie"])
                 != libelles[p["properties"]["categorie"]]]
    verifier("libellés de catégorie : ceux de chaque point de la carte, depuis le référentiel",
             not manquants, manquants[:3])

    # Sans JS (D10) : liens vers la page du département et sa liste.
    page_44 = _hors_noscript(cartes["carte/44.html"])
    verifier("sans JS, carte/44.html renvoie vers la page du département et sa liste",
             'href="../departement/44.html"' in page_44 and 'href="../departement/44/1.html"' in page_44
             and "<noscript>" in cartes["carte/44.html"])
    verifier("sans JS, carte.html liste chaque carte départementale et les listes par département",
             all(f'href="{eh.chemin_carte_departement(c)}"' in cartes[eh.PAGE_CARTE]
                 for c in DEPARTEMENTS) and 'href="index.html#par-departement"'
             in _hors_noscript(cartes[eh.PAGE_CARTE]))
    verifier("accès aux cartes : accueil -> carte.html, département -> sa carte, indéterminé -> "
             "carte nationale",
             'href="carte.html"' in lire(site, "index.html")
             and 'href="../carte/44.html"' in lire(site, "departement/44.html")
             and 'href="../carte.html"' in lire(site, "departement/indetermine.html"))

    # Le lien de chaque point mène à une fiche réelle : ancre sur la sous-page.
    ancres = {p: set(re.findall(r'<tr id="(et-[^"]+)"', c)) for p, c in sous_pages.items()}
    verifier("chaque ligne de sous-page porte l'ancre et-<finess> de sa fiche",
             all(len(a) == len(_LIGNE.findall(sous_pages[p])) for p, a in ancres.items())
             and all(f'<tr id="et-{n}" ' in c for p, c in sous_pages.items()
                     for n in _LIGNE.findall(c)))
    casses = []
    for point in points:
        page, _, ancre = point["properties"]["lien"].partition("#")
        if ancre != f"et-{point['properties']['finess']}" or ancre not in ancres.get(page, ()):
            casses.append(point["properties"]["lien"])
    verifier(f"lien de chacun des {len(points)} points -> sous-page écrite portant son ancre",
             points and not casses, casses[:3])

    # Dépendances vendorisées : copiées à l'identique, empreintes documentées.
    readme = (VENDOR / "README.md").read_text(encoding="utf-8")
    empreintes = {rel: hashlib.sha256((VENDOR.parent / rel).read_bytes()).hexdigest()
                  for rel in eh.VENDOR_CARTE.values()}
    verifier("vendor/ : MapLibre, pmtiles et leurs licences copiés à l'identique",
             all((site / r).read_bytes() == (VENDOR.parent / r).read_bytes()
                 for r in bilan["vendor_copies"])
             and {"vendor/maplibre-gl/LICENSE.txt", "vendor/pmtiles/LICENSE"}
             <= set(bilan["vendor_copies"]), bilan["vendor_copies"])
    verifier("vendor/ : empreintes SHA-256 = celles de front/vendor/README.md",
             all(h in readme for h in empreintes.values()), empreintes)
    octets = {p: len(c.encode("utf-8")) for p, c in cartes.items()}
    verifier("D9 : la carte la plus lourde, avec tous les actifs, sous 500 Ko (MapLibre exclu, "
             "chargé au clic)", max(octets.values()) + sum(
                 p.stat().st_size for p in ACTIFS.iterdir() if p.is_file()) <= eh.BUDGET_PAGE,
             max(octets.values()))

    node = shutil.which("node")
    if node is None:
        print("  IGNORÉ carte.js et scripts vendorisés sous Node : node absent du PATH")
        return
    js = Path(__file__).resolve().parent / "js"
    fini = subprocess.run([node, str(js / "verifier_vendor.js"),
                           str(VENDOR.parent / eh.VENDOR_CARTE["maplibre"]),
                           str(VENDOR.parent / eh.VENDOR_CARTE["pmtiles"])],
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    api = json.loads(fini.stdout) if fini.returncode == 0 else {}
    verifier("scripts vendorisés évalués : MapLibre 5.24.0 et pmtiles exposent l'API de carte.js",
             api.get("maplibre_version") == "5.24.0"
             and api.get("maplibre") == ["Map", "Popup", "AttributionControl",
                                         "NavigationControl", "addProtocol"]
             and "Protocol" in api.get("pmtiles", []) and api.get("protocole_tile") == "function",
             api or fini.stderr[-400:])

    point_44 = par_dep["44"][0]

    def executer(page, **scenario):
        d = _donnees_carte(cartes[page])
        scenario = {"dataset": d, "base": f"http://site.test/{page}", "fond": {"statut": 200},
                    "clic_point": {"properties": point_44["properties"],
                                   "coordinates": point_44["geometry"]["coordinates"]},
                    **scenario}
        chemin = site.parent / "scenario_carte.json"
        chemin.write_text(json.dumps(scenario), encoding="utf-8")
        fini = subprocess.run([node, str(js / "harnais_carte.js"), str(ACTIFS / "carte.js"),
                               str(chemin)], capture_output=True, text=True, encoding="utf-8",
                              timeout=60)
        if fini.returncode != 0:
            verifier(f"carte.js sous Node ({page}) : exécution", False, fini.stderr[-500:])
            return None
        return json.loads(fini.stdout)

    d44 = _donnees_carte(cartes["carte/44.html"])
    r = executer("carte/44.html")
    if r:
        avant, apres = r["avant_clic_attente"], r["apres_clics"][0]
        verifier("Node : avant le clic, aucune requête, rien d'injecté, MapLibre non chargé, "
                 "bouton montré, carte cachée",
                 avant["requetes"] == [] and avant["injectes"] == [] and not avant["maplibre_charge"]
                 and not avant["commande_cachee"] and avant["carte_cachee"]
                 and r["avant_clic"]["injectes"] == [], avant)
        verifier("Node : au clic, feuille de style et scripts de vendor/ injectés, style IGN demandé",
                 apres["injectes"] == [
                     {"type": "link", "href": d44["maplibreCss"], "rel": "stylesheet"},
                     {"type": "script", "src": d44["maplibre"]},
                     {"type": "script", "src": d44["pmtiles"]}]
                 and apres["requetes"] == [eh.FOND_CARTE] and apres["maplibre_charge"], apres)
        carte = r["recu"]["cartes"][0] if r["recu"]["cartes"] else {}
        verifier("Node : carte construite dans #carte, cadrée sur l'emprise du département, "
                 "carte visible, aucun message",
                 carte.get("conteneur") and carte.get("bounds") == json.loads(d44["emprise"])
                 and carte.get("style") == {"version": 8, "sources": {}, "layers": []}
                 and not apres["carte_cachee"] and apres["etat_cache"], carte)
        verifier("Node : attribution IGN passée à MapLibre",
                 {"type": "attribution", "options": {
                     "compact": False, "customAttribution": d44["attribution"]}}
                 in r["recu"]["controles"], r["recu"]["controles"])
        verifier("Node : protocole pmtiles, source = archive en URL absolue, couche du contrat C",
                 r["recu"]["protocoles"] == [{"nom": "pmtiles", "fonction": "function"}]
                 and r["recu"]["sources"] == [{
                     "id": "etablissements", "type": "vector",
                     "url": "pmtiles://http://site.test/tuiles/etablissements.pmtiles"}]
                 and r["recu"]["calques"][0]["source-layer"] == eh.COUCHE_TUILES,
                 r["recu"]["sources"])
        verifier("Node : carte départementale filtrée sur dep",
                 r["recu"]["calques"][0].get("filter") == ["==", ["get", "dep"], "44"],
                 r["recu"]["calques"][0].get("filter"))
        fenetre = r["recu"]["fenetres"][0] if r["recu"]["fenetres"] else {}
        pr = point_44["properties"]
        verifier("Node : clic sur un point -> fenêtre nom, libellé de catégorie, lien vers la fiche",
                 pr["nom"] in fenetre.get("texte", "")
                 and libelles[pr["categorie"]] in fenetre.get("texte", "")
                 and fenetre.get("liens") == ["../" + pr["lien"]]
                 and (site / "carte" / fenetre["liens"][0].split("#")[0]).resolve().is_file(), fenetre)
    r = executer(eh.PAGE_CARTE)
    if r:
        verifier("Node : carte nationale sans filtre, archive résolue depuis la racine",
                 r["recu"]["calques"] and "filter" not in r["recu"]["calques"][0]
                 and r["recu"]["sources"][0]["url"]
                 == "pmtiles://http://site.test/tuiles/etablissements.pmtiles"
                 and r["recu"]["fenetres"][0]["liens"] == [point_44["properties"]["lien"]],
                 r["recu"]["calques"][:1])
    r = executer("carte/44.html", scripts_en_echec=[d44["maplibre"]], clics_bouton=2)
    if r:
        un, deux = r["apres_clics"]
        verifier("Node : MapLibre introuvable -> message visible, carte jamais montrée, bouton "
                 "rendu pour réessayer",
                 not un["etat_cache"] and "n'a pas pu être affichée" in un["etat_texte"]
                 and d44["maplibre"] in un["etat_texte"] and un["carte_cachee"]
                 and not un["commande_cachee"] and not un["bouton_desactive"]
                 and un["cartes"] == 0, un)
        verifier("Node : second clic -> nouvelle tentative, un seul message affiché",
                 len(deux["injectes"]) == 6 and deux["messages"] == 1 and deux["carte_cachee"], deux)
    r = executer("carte/44.html", fond={"statut": 503})
    if r:
        apres = r["apres_clics"][0]
        verifier("Node : style IGN en échec (HTTP 503) -> fond neutre, message, points quand même",
                 r["recu"]["cartes"] and r["recu"]["cartes"][0]["style"] == "neutre"
                 and "Fond de carte IGN indisponible (HTTP 503)" in apres["etat_texte"]
                 and not apres["etat_cache"] and r["recu"]["sources"], apres)
    r = executer("carte/44.html", fond={"reseau": True})
    if r:
        verifier("Node : style IGN injoignable (réseau) -> fond neutre et message",
                 "Fond de carte IGN indisponible" in r["apres_clics"][0]["etat_texte"]
                 and r["recu"]["cartes"][0]["style"] == "neutre")
    r = executer("carte/44.html", evenements=[
        {"sourceId": "etablissements", "message": "HTTP 404"},
        {"sourceId": "etablissements", "message": "HTTP 404"},
        {"sourceId": "plan_ign", "message": "HTTP 500"}])
    if r:
        apres = r["apres_clics"][0]
        verifier("Node : archive en échec -> message visible (une fois), fond en échec -> message",
                 "n'ont pas pu être chargés depuis l'archive (HTTP 404)" in apres["etat_texte"]
                 and "partie du fond de carte" in apres["etat_texte"]
                 and apres["messages"] == 2 and not apres["etat_cache"], apres)
    r = executer("carte/44.html", webgl=False)
    if r:
        apres = r["apres_clics"][0]
        verifier("Node : carte impossible à construire (WebGL) -> message, cadre caché",
                 "WebGL indisponible" in apres["etat_texte"] and apres["carte_cachee"]
                 and not apres["etat_cache"], apres)


with tempfile.TemporaryDirectory(prefix="test_export_html_") as temporaire:
    TMP = Path(temporaire)

    # -----------------------------------------------------------------------
    print("1. Rendu de bout en bout sur l'échantillon versionné (découpage départemental)")
    site = TMP / "site"
    site_defaut = TMP / "site_defaut"
    site_national = TMP / "site_national"
    with Entrepot(TMP / "echantillon.db") as e:
        e.creer()
        charger(e, SourceFinessStructures(), S, controle=CONTROLE_MINIMAL)
        charger(e, SourceFinessActivites(), A, controle=CONTROLE_MINIMAL)
        bilan = eh.rendre(e, GABARITS, site, lignes_par_sous_page=BORNE)
        bilan_defaut = eh.rendre(e, GABARITS, site_defaut)
        bilan_national = eh.rendre(e, GABARITS, site_national, decoupage="national")
        geo = export_geo.exporter(e, TMP / "etablissements.geojson", lignes_par_sous_page=BORNE)

        # Références indépendantes : les couches qu'export_html dit relire.
        etablissements = etablissements_bruts(e)
        activites = activites_par_etablissement(e)
        resultat = indicateur_departement_categorie(e)

    # Découpage attendu, recalculé ici sans passer par export_html : les
    # établissements de chaque département par numéro FINESS croissant, en
    # tranches consécutives de BORNE, au moins une par département.
    par_code = {c: [] for c in CODES}
    for x in etablissements:
        code = (x["code_departement"] if x["code_departement"] in DEPARTEMENTS
                else eh.PAGE_INDETERMINEE)
        par_code[code].append(x["num_finess_et"])
    tranches = {c: [nums[i:i + BORNE] for i in range(0, len(nums), BORNE)] or [[]]
                for c, nums in par_code.items()}
    attendu_par_page = {f"departement/{c}/{n}.html": tranche
                        for c, liste in tranches.items() for n, tranche in enumerate(liste, 1)}
    fragment_de = {f"departement/{c}/{n}.html": f"donnees/activites/{c}/{n}.json"
                   for c, liste in tranches.items() for n in range(1, len(liste) + 1)}
    SOUS_PAGES = list(attendu_par_page)
    groupes = {}
    for d, c, n in resultat.lignes_triees():
        groupes.setdefault(d, []).append((c, n))
    PAGES_IND = [f"indicateur/{d}.html" for d in groupes]

    ordre = [p for c in CODES for p in [eh.chemin_page_departement(c)]
             + [eh.chemin_sous_page(c, n) for n in range(1, len(tranches[c]) + 1)]]
    CARTES = [eh.PAGE_CARTE] + [eh.chemin_carte_departement(c) for c in DEPARTEMENTS]
    attendues = list(eh.PAGES_NATIONALES["departement"]) + PAGES_IND + ordre + CARTES
    verifier("millésime de l'échantillon (202607)", bilan["millesime"] == "202607", bilan["millesime"])
    verifier("découpage par défaut : departement", bilan["decoupage"] == "departement",
             bilan["decoupage"])
    verifier("pages écrites : accueil, indicateur, pages d'indicateur, puis chaque page "
             "départementale suivie de ses sous-pages",
             bilan["pages_ecrites"] == attendues and len(PAGES_DEP) == 102,
             bilan["pages_ecrites"][:5])
    manquantes = [p for p in attendues
                  if not (site / p).is_file() or (site / p).stat().st_size != bilan["octets"][p]]
    verifier("chaque page présente sur disque, taille = octets annoncés", not manquantes,
             manquantes[:5])
    fichiers = sorted((site / "departement").glob("*.html"))
    verifier("102 pages de département dans departement/ (101 + indetermine.html)",
             len(fichiers) == 102, len(fichiers))
    verifier("sous-pages sur disque = sous-pages attendues",
             sorted(p.relative_to(site).as_posix()
                    for p in (site / "departement").glob("*/*.html")) == sorted(SOUS_PAGES))
    verifier("pagination exercée : 44 en 4 sous-pages (100, 100, 100, 14), 01 en 2",
             bilan["sous_pages_departement"]["44"] == [100, 100, 100, 14]
             and len(bilan["sous_pages_departement"]["01"]) == 2,
             (bilan["sous_pages_departement"]["44"], bilan["sous_pages_departement"]["01"]))
    verifier("aucune sous-page au-delà de la borne",
             all(n <= BORNE for l in bilan["sous_pages_departement"].values() for n in l)
             and bilan["lignes_par_sous_page"] == BORNE)
    verifier("département sans établissement : une sous-page quand même (pas de cas "
             "particulier)", all(bilan["sous_pages_departement"][c] == [0]
                                 for c in CODES if not par_code[c]))
    verifier("liste.html non produite en découpage départemental",
             not (site / "liste.html").exists())
    verifier("codes corses en texte : 2A.html et 2B.html, clés « 2A »/« 2B »",
             (site / "departement/2A.html").is_file() and (site / "departement/2B.html").is_file()
             and (site / "departement/2A/1.html").is_file()
             and "2A" in bilan["pages_departement"] and "2B" in bilan["pages_departement"])
    verifier("zéro de tête conservé : 01.html et 01/1.html, pas de 1.html",
             (site / "departement/01.html").is_file() and (site / "departement/01/1.html").is_file()
             and not (site / "departement/1.html").exists())

    verifier("nombre_etablissements = export_front.etablissements_bruts",
             bilan["nombre_etablissements"] == len(etablissements) > 0,
             (bilan["nombre_etablissements"], len(etablissements)))
    verifier("somme des pages départementales = total des établissements",
             sum(bilan["pages_departement"].values()) == len(etablissements),
             sum(bilan["pages_departement"].values()))
    verifier("somme des sous-pages = total des établissements (D6)",
             sum(sum(l) for l in bilan["sous_pages_departement"].values()) == len(etablissements))
    verifier("activites_total = export_front.activites_par_etablissement",
             bilan["activites_total"] == sum(len(l) for l in activites.values()) > 0,
             bilan["activites_total"])
    verifier("etablissements_avec_activites = export_front",
             bilan["etablissements_avec_activites"] == len(activites), bilan)
    verifier("categorie_non_resolue = recomptée sur export_front",
             bilan["categorie_non_resolue"] == sum(
                 1 for x in etablissements
                 if x["code_categorie"] is not None and x["libelle_categorie"] is None), bilan)
    verifier("nature_non_resolue = activites_total (aucune nomenclature de nature)",
             bilan["nature_non_resolue"] == bilan["activites_total"], bilan)
    verifier("indicateur_lignes = indicateurs.lignes_triees()",
             bilan["indicateur_lignes"] == len(resultat.lignes_triees()) > 0, bilan)
    verifier("indicateur : une page par département du tableau, cases réparties sans perte",
             bilan["indicateur_pages"] == len(groupes) == bilan["lignes_rendues"]["indicateur.html"]
             and sum(bilan["pages_indicateur"].values()) == bilan["indicateur_lignes"], bilan)
    verifier("indicateur_total_actifs / exclus = Resultat",
             bilan["indicateur_total_actifs"] == resultat.total_actifs
             and bilan["indicateur_exclus"] == resultat.exclus(), bilan)
    verifier("accueil : départements / catégories = marges de Resultat",
             bilan["accueil_departements"] == len(resultat.par_departement())
             and bilan["accueil_categories"] == len(resultat.par_categorie()), bilan)

    # Borne par défaut : sur l'échantillon, chaque département tient en une
    # sous-page, mais la structure est la même.
    verifier("borne par défaut = LIGNES_PAR_SOUS_PAGE (1000), une sous-page par département "
             "sur l'échantillon, mêmes établissements",
             bilan_defaut["lignes_par_sous_page"] == eh.LIGNES_PAR_SOUS_PAGE == 1000
             and all(l == [bilan_defaut["pages_departement"][c]]
                     for c, l in bilan_defaut["sous_pages_departement"].items())
             and bilan_defaut["pages_departement"] == bilan["pages_departement"])

    # Chaque sous-page n'embarque que sa tranche — un établissement, une seule
    # sous-page.
    pages = {p: lire(site, p) for p in SOUS_PAGES}
    sommaires = {p: lire(site, p) for p in PAGES_DEP}
    lignes_par_page = {p: _LIGNE.findall(contenu) for p, contenu in pages.items()}
    verifier("chaque sous-page porte exactement sa tranche d'établissements",
             lignes_par_page == attendu_par_page,
             [p for p in SOUS_PAGES if lignes_par_page[p] != attendu_par_page[p]][:5])
    verifier("lignes_rendues = effectif de chaque sous-page",
             all(bilan["lignes_rendues"][eh.chemin_sous_page(c, n)] == k
                 for c, l in bilan["sous_pages_departement"].items()
                 for n, k in enumerate(l, 1)))
    verifier("page de département : aucune fiche, seulement le sommaire",
             all(not _LIGNE.search(c) and "<details" not in c for c in sommaires.values()))
    liens_ok = []
    for c in CODES:
        sommaire = sommaires[eh.chemin_page_departement(c)]
        liens = re.findall(r'<tr><td><a href="([^"]+)">Sous-page (\d+)</a></td>'
                           r'<td class="effectif">(\d+)</td>', sommaire)
        attendu = [(f"{c}/{n}.html", str(n), str(len(t)))
                   for n, t in enumerate(tranches[c], 1)]
        if liens != attendu:
            liens_ok.append((c, liens[:2], attendu[:2]))
    verifier("page de département : lien HTML relatif vers chaque sous-page, avec son effectif "
             "(D10)", not liens_ok, liens_ok[:3])
    sommaire_44 = sommaires["departement/44.html"]
    verifier("page de département : plage de numéros FINESS de chaque sous-page, total",
             f"<td>{tranches['44'][1][0]}</td><td>{tranches['44'][1][-1]}</td>" in sommaire_44
             and '<td>Total</td><td class="effectif">314</td>' in sommaire_44)
    page_44_2 = pages["departement/44/2.html"]
    verifier("sous-page : limite des filtres écrite, plage et lien vers le sommaire",
             'id="limite">Sous-page 2 sur 4 du département : fiches 101 à 200 sur 314' in page_44_2
             and "La recherche et les filtres ne portent que sur cette sous-page" in page_44_2
             and '<a href="../44.html">page du département</a>' in page_44_2)
    verifier("sous-page : liens précédente / suivante relatifs, absents aux extrémités",
             '<a href="1.html" rel="prev">' in page_44_2 and '<a href="3.html" rel="next">' in page_44_2
             and 'rel="prev"' not in pages["departement/44/1.html"]
             and 'rel="next"' not in pages["departement/44/4.html"])
    verifier("titre de sous-page : libellé, code et rang",
             "<h1>Loire-Atlantique (44) — sous-page 2 sur 4</h1>" in page_44_2)
    verifier("un <details data-finess> par établissement ayant des activités, sur l'ensemble "
             "des sous-pages", sum(c.count("<details data-finess=") for c in pages.values())
             == bilan["etablissements_avec_activites"])
    vides = [p for p in SOUS_PAGES if not attendu_par_page[p]]
    verifier("l'échantillon laisse des départements sans établissement (prérequis)", len(vides) > 0)
    verifier("département sans établissement : sous-page explicite, message « aucun »",
             all('id="aucun"' in pages[p] and "<table" not in pages[p]
                 and "qui ne compte aucune fiche" in pages[p] for p in vides), vides[:5])
    verifier("titre de page = libellé et code du référentiel (2A)",
             "<h1>Corse-du-Sud (2A)</h1>" in sommaires["departement/2A.html"])
    verifier("rappel de périmètre en tête de chaque page et sous-page départementale",
             all('<main>\n<p class="perimetre" id="perimetre">' in c
                 and "la qualification enfance/adolescents n'est pas encore appliquée" in c
                 for c in list(pages.values()) + list(sommaires.values())))
    verifier("pages départementales : style et navigation relatifs (../)",
             all('href="../actifs/ooms.css"' in c and 'href="../index.html"' in c
                 and 'href="../indicateur.html"' in c for c in sommaires.values()))
    verifier("sous-pages : style et navigation relatifs (../../)",
             all('href="../../actifs/ooms.css"' in c and 'href="../../index.html"' in c
                 and 'href="../../indicateur.html"' in c for c in pages.values()))
    verifier("sous-page non vide : îlot filtres.js chargé en relatif",
             'src="../../actifs/filtres.js"' in pages["departement/01/1.html"])

    indicateur = lire(site, "indicateur.html")
    accueil = lire(site, "index.html")

    liens = re.findall(r'<tr><td><a href="(indicateur/[^"]+)">([^<]*)</a></td>'
                       r'<td class="effectif" data-valeur="(\d+)">\d+</td>'
                       r'<td class="effectif" data-valeur="(\d+)">', indicateur)
    verifier("indicateur.html : une ligne liée par département, cases et effectif du département",
             liens == [(f"indicateur/{d}.html", html.escape(d), str(len(l)), str(sum(n for _, n in l)))
                       for d, l in groupes.items()], liens[:3])
    verifier("indicateur.html : total du pied de tableau = dans_tableau",
             f'id="total">{resultat.dans_tableau()}</td>' in indicateur)
    rendues = []
    for p in PAGES_IND:
        contenu = lire(site, p)
        d = Path(p).stem
        rendues += [(d, c, n) for c, n in re.findall(
            r'<tr><td>([^<]*)</td><td class="effectif" data-valeur="(\d+)"', contenu)]
    attendues_ind = [(html.escape(d), html.escape(c), str(n)) for d, c, n in resultat.lignes_triees()]
    verifier("indicateur/<code>.html : cases identiques et dans l'ordre de "
             "Resultat.lignes_triees", rendues == attendues_ind, (rendues[:3], attendues_ind[:3]))
    ind_44 = lire(site, "indicateur/44.html")
    verifier("indicateur/44.html : total = marge du département, navigation relative (../)",
             f'id="total">{dict(resultat.par_departement())["44"]}</td>' in ind_44
             and 'href="../indicateur.html"' in ind_44 and 'src="../actifs/filtres.js"' in ind_44)

    verifier("index.html : mention de périmètre présente",
             'id="perimetre"' in accueil
             and "La qualification enfance/adolescents n'est pas encore appliquée" in accueil)
    verifier("index.html : mention de périmètre avant le premier chiffre clé",
             accueil.index('id="perimetre"') < accueil.index("Chiffres clés"))
    verifier("index.html : total actifs de la couche 5 affiché",
             f"<strong>{resultat.total_actifs}</strong>" in accueil)
    liens = re.findall(r'<a href="(departement/[^"]+)">', accueil)
    verifier("index.html : un lien relatif vers chaque page départementale, dans l'ordre",
             liens == PAGES_DEP, liens[:5])
    effectifs = [int(n) for n in re.findall(
        r'<a href="departement/[^"]+">[^<]*</a></td><td class="effectif">(\d+)</td>', accueil)]
    verifier("index.html : effectifs par département totalisent Resultat.dans_tableau()",
             len(effectifs) == 102 and sum(effectifs) == resultat.dans_tableau(), sum(effectifs))
    verifier("index.html : une ligne par page départementale et par catégorie",
             accueil.count('<td class="effectif">') == 102 + len(resultat.par_categorie()))
    verifier("index.html : lots de provenance listés (Structures et Activités)",
             "finess_structures" in accueil and "finess_activites" in accueil)
    verifier("index.html : pas de lien vers liste.html en découpage départemental",
             "liste.html" not in accueil)

    defauts = {}
    for page in bilan["pages_ecrites"]:
        contenu = lire(site, page)
        propre = {"../../" + fragment_de[page]} if page in fragment_de else set()
        if _TROU.search(contenu): defauts[page] = f"$ non substitué {_TROU.findall(contenu)[:3]}"
        elif "<!-- BLOC" in contenu or "<!-- FIN" in contenu: defauts[page] = "commentaire de gabarit"
        elif "ooms.css" not in contenu: defauts[page] = "feuille de style absente"
        elif _ABSOLU.search(contenu): defauts[page] = "lien absolu"
        elif {j for j in re.findall(r'[^"\s>]*\.json', contenu) if "://" not in j} - propre:
            defauts[page] = "cite un JSON autre que son propre fragment"
    verifier("toutes les pages : aucun $ non substitué, aucun commentaire de gabarit, "
             "feuille de style liée, aucun lien absolu, aucun JSON du site cité hors fragment "
             "propre (le style du fond IGN est externe)",
             not defauts, list(defauts.items())[:3])
    # Pied de page commun (OOM-55) : sur chaque type de page, valeurs du
    # module (jamais écrites dans un gabarit, D7), sans script (D10).
    depot = "https://github.com/mThorlak/observatoire-offre-medicosociale-enfance"
    verifier("MENTIONS_PIED : dépôt, licence EUPL 1.2 et statut non officiel",
             eh.DEPOT == depot and eh.MENTIONS_PIED["lien_depot"] == depot
             and eh.MENTIONS_PIED["licence_code"] == "EUPL 1.2"
             and eh.MENTIONS_PIED["lien_licence"] == depot + "/blob/main/LICENSE"
             and "pas une donnée officielle de l'administration"
             in eh.MENTIONS_PIED["statut_donnees"], eh.MENTIONS_PIED)
    verifier("gabarits : aucune valeur du pied écrite en dur (D7)",
             all(depot not in g.read_text(encoding="utf-8") and "EUPL" not in
                 g.read_text(encoding="utf-8") for g in GABARITS.glob("*.html")))
    attendu_pied = [f'<a href="{depot}">{depot}</a>',
                    f'sous licence <a href="{depot}/blob/main/LICENSE">EUPL 1.2</a>',
                    html.escape(eh.MENTIONS_PIED["statut_donnees"]),
                    html.escape(eh.MENTIONS_PIED["attribution_source"])]

    def pied(contenu):
        trouve = re.search(r"<footer>(.*?)</footer>", contenu, re.DOTALL)
        return trouve.group(1) if trouve else ""

    sans_pied = [p for p in bilan["pages_ecrites"]
                 if not all(a in pied(lire(site, p)) for a in attendu_pied)
                 or "<script" in pied(lire(site, p))]
    verifier("pied commun (dépôt, statut non officiel, source, licence du code), sans script, "
             "sur chaque page écrite", not sans_pied, sans_pied[:5])
    types = {"accueil": "index.html", "indicateur": "indicateur.html",
             "page d'indicateur par département": "indicateur/44.html",
             "page départementale": "departement/44.html",
             "sous-page départementale": "departement/44/2.html",
             "page indéterminée": "departement/indetermine.html",
             "sous-page vide": vides[0]}
    for nom, page in types.items():
        verifier(f"pied commun présent : {nom} ({page})",
                 page in bilan["pages_ecrites"] and page not in sans_pied
                 and pied(lire(site, page)).count('id="mentions"') == 1)
    verifier("pied commun présent : liste.html (découpage national)",
             all(a in pied(lire(site_national, "liste.html")) for a in attendu_pied))
    verifier("index.html : « Méthode et reproductibilité » dans « Source et licence », "
             "après la mention de périmètre",
             accueil.index('id="source"') < accueil.index('id="methode"')
             and accueil.index('id="perimetre"') < accueil.index('id="methode"')
             and "fermés sont conservés dans l'entrepôt mais exclus des comptages" in accueil
             and "n'est pas encore qualifié" in accueil
             and f'<a href="{depot}#readme">README du dépôt</a>' in accueil)
    verifier("index.html : la mention de périmètre reste la première section du contenu",
             '<main>\n<section class="perimetre" id="perimetre">' in accueil)

    cassés = []
    for page in bilan["pages_ecrites"]:
        for cible in re.findall(r'<a href="([^"#]+)', lire(site, page)):
            if "://" in cible or cible.startswith("mailto:"):
                continue
            if not (site / page).parent.joinpath(cible).resolve().is_file():
                cassés.append((page, cible))
    verifier("tous les liens <a> internes pointent vers un fichier écrit", not cassés, cassés[:3])
    octets_actifs = sum(p.stat().st_size for p in ACTIFS.iterdir() if p.is_file())
    verifier("D9 : aucune page de l'échantillon au-delà de 500 Ko, actifs compris",
             max(bilan["octets"].values()) + octets_actifs <= eh.BUDGET_PAGE == 500 * 1024,
             max(bilan["octets"].values()))

    attendus = sorted(p.name for p in ACTIFS.iterdir() if p.is_file())
    verifier("actifs copiés = contenu de front/actifs/",
             bilan["actifs_copies"] == attendus and attendus, bilan["actifs_copies"])
    verifier("actifs copiés à l'identique (octets)",
             all((site / "actifs" / n).read_bytes() == (ACTIFS / n).read_bytes()
                 for n in attendus))

    # Budget D9 garanti par le code, pas par la distribution des départements :
    # un budget abaissé sous la page la plus lourde lève, rien n'est écrit.
    budget = eh.BUDGET_PAGE
    eh.BUDGET_PAGE = max(bilan["octets"].values()) + octets_actifs - 1
    sortie = TMP / "site_hors_budget"
    try:
        with Entrepot(TMP / "echantillon.db") as e:
            eh.rendre(e, GABARITS, sortie, lignes_par_sous_page=BORNE)
        verifier("page au-delà du budget -> ErreurExportHtml", False)
    except eh.ErreurExportHtml as erreur:
        lourde = max(bilan["octets"], key=bilan["octets"].get)
        verifier("page au-delà du budget -> ErreurExportHtml nommant la page, rien d'écrit",
                 "budget D9" in str(erreur) and lourde in str(erreur) and not sortie.exists(),
                 str(erreur))
    finally:
        eh.BUDGET_PAGE = budget
    try:
        with Entrepot(TMP / "echantillon.db") as e:
            eh.rendre(e, GABARITS, TMP / "site_borne_nulle", lignes_par_sous_page=0)
        verifier("borne de pagination nulle -> ErreurExportHtml", False)
    except eh.ErreurExportHtml:
        verifier("borne de pagination nulle -> ErreurExportHtml, rien d'écrit",
                 not (TMP / "site_borne_nulle").exists())

    verifier_activites_a_la_demande(site, bilan, activites, attendu_par_page, fragment_de, pages)
    verifier_cartes(site, bilan, geo, TMP / "etablissements.geojson", etablissements, pages)
    verifier_couverture(site, bilan, geo)

    # D6 : un bandeau qui ne compterait pas les établissements du site lève.
    couverture = export_geo.couverture

    def couverture_faussee(entrepot, departements):
        resultat = couverture(entrepot, departements)
        resultat["par_departement"]["44"]["total"] += 1
        return resultat

    export_geo.couverture = couverture_faussee
    try:
        with Entrepot(TMP / "echantillon.db") as e:
            eh.rendre(e, GABARITS, TMP / "site_couverture_faussee", lignes_par_sous_page=BORNE)
        verifier("bandeau incohérent avec le site -> ErreurExportHtml", False)
    except eh.ErreurExportHtml as erreur:
        verifier("bandeau incohérent avec le site -> ErreurExportHtml nommant la carte, rien "
                 "d'écrit", "couverture incohérente pour la carte 44" in str(erreur)
                 and not (TMP / "site_couverture_faussee").exists(), str(erreur))
    finally:
        export_geo.couverture = couverture

    # -----------------------------------------------------------------------
    print("\n1 bis. Découpage national (decoupage=\"national\")")
    verifier("les trois pages nationales écrites, dans l'ordre de PAGES, puis les pages "
             "d'indicateur (découpées aussi en national)",
             bilan_national["pages_ecrites"] == list(eh.PAGES) + PAGES_IND,
             bilan_national["pages_ecrites"][:5])
    verifier("aucune carte en national (les liens des points visent les sous-pages "
             "départementales), aucune dépendance vendorisée copiée",
             not (site_national / eh.PAGE_CARTE).exists()
             and not (site_national / eh.DOSSIER_CARTE).exists()
             and not (site_national / eh.DOSSIER_VENDOR).exists()
             and bilan_national["pages_carte"] == {} and bilan_national["vendor_copies"] == [])
    verifier("aucune page départementale en national",
             not (site_national / "departement").exists()
             and bilan_national["pages_departement"] == {}
             and bilan_national["sous_pages_departement"] == {}
             and bilan_national["fragments_ecrits"] == [])
    liste = lire(site_national, "liste.html")
    verifier("liste.html : une ligne <tr data-dep> par établissement",
             liste.count('<tr data-dep="') == bilan_national["nombre_etablissements"]
             == len(etablissements), liste.count('<tr data-dep="'))
    verifier("liste.html : un <details> par établissement ayant des activités",
             liste.count("<details>") == bilan_national["etablissements_avec_activites"],
             liste.count("<details>"))
    verifier("liste.html : chaque numéro FINESS présent",
             all(f"<td>{x['num_finess_et']}</td>" in liste for x in etablissements))
    verifier("somme des pages départementales = total de la liste nationale",
             sum(bilan["pages_departement"].values()) == liste.count('<tr data-dep="'))
    accueil_national = lire(site_national, "index.html")
    verifier("index.html national : lien vers liste.html, aucun vers departement/",
             'href="liste.html"' in accueil_national and "departement/" not in accueil_national)
    verifier("index.html national : une ligne par département et par catégorie",
             accueil_national.count('<td class="effectif">') ==
             len(resultat.par_departement()) + len(resultat.par_categorie()))
    try:
        with Entrepot(TMP / "echantillon.db") as e:
            eh.rendre(e, GABARITS, TMP / "site_decoupage_inconnu", decoupage="region")
        verifier("découpage inconnu -> ErreurExportHtml", False)
    except eh.ErreurExportHtml:
        verifier("découpage inconnu -> ErreurExportHtml, rien d'écrit",
                 not (TMP / "site_decoupage_inconnu").exists())

    # -----------------------------------------------------------------------
    print("\n2. Codes hors référentiel -> repli visible, jamais un libellé inventé ni un écart")
    try:
        resoudre_categorie("Z99")
        verifier("prérequis : Z99 absent du référentiel", False)
    except CodeCategorieInconnu:
        verifier("prérequis : Z99 absent du référentiel", True)
    verifier("prérequis : 975 absent du référentiel des départements", "975" not in DEPARTEMENTS)

    site_inconnu = TMP / "site_inconnu"
    with Entrepot(TMP / "inconnu.db") as e:
        e.creer()
        c = e.connexion
        inserer(c, "entete", **LOT)
        inserer(c, "entite_juridique", **EJ)
        inserer(c, "etablissement", **etablissement("010000020", "G0", "183", "IME Connu"))
        inserer(c, "etablissement", **etablissement("010000021", "G1", "Z99", "Catégorie Inconnue"))
        inserer(c, "etablissement", **etablissement("2A0000022", "G2", "183", "IME Corse"))
        inserer(c, "etablissement", **etablissement("010000023", "G3", "183", "Sans Adresse"))
        inserer(c, "etablissement", **etablissement("010000024", "G4", "183", "Commune Illisible"))
        inserer(c, "etablissement", **etablissement("970000025", "G5", "183", "Saint-Pierre"))
        inserer(c, "adresse", **adresse("G0", "01053"))
        inserer(c, "adresse", **adresse("G1", "01053"))
        inserer(c, "adresse", **adresse("G2", "2A004"))
        inserer(c, "adresse", **adresse("G4", "ABCDE"))
        inserer(c, "adresse", **adresse("G5", "97502"))
        try:
            bilan_inconnu = eh.rendre(e, GABARITS, site_inconnu)
            verifier("rendre ne plante pas sur des codes hors référentiel", True)
        except Exception as erreur:  # noqa: BLE001 — le test veut justement tout attraper
            bilan_inconnu = None
            verifier("rendre ne plante pas sur des codes hors référentiel", False, repr(erreur))

    if bilan_inconnu is not None:
        page_01 = lire(site_inconnu, "departement/01/1.html")
        ligne = next((l for l in page_01.splitlines() if "<td>010000021</td>" in l), "")
        verifier("compteur : 1 catégorie non résolue", bilan_inconnu["categorie_non_resolue"] == 1,
                 bilan_inconnu)
        verifier("01.html : repli « [non résolu] » sur la ligne de l'établissement",
                 "[non résolu]" in ligne, ligne)
        verifier("01.html : code brut Z99 affiché", "(Z99)" in ligne, ligne)
        verifier("01.html : aucun libellé inventé (data-cat vide)", 'data-cat=""' in ligne, ligne)
        verifier("01.html : l'établissement connu garde son libellé",
                 "Institut Médico-Educatif (I.M.E.)" in page_01)
        verifier("01.html : Z99 n'apparaît pas comme option de catégorie",
                 '<option value="Z99">' not in page_01
                 and '<option value="[non résolu]">' not in page_01)

        verifier("Corse : l'établissement de 2A004 est dans 2A.html",
                 bilan_inconnu["pages_departement"]["2A"] == 1
                 and "<td>2A0000022</td>" in lire(site_inconnu, "departement/2A/1.html"))
        indeterminee = lire(site_inconnu, "departement/indetermine/1.html")
        verifier("page indéterminée : les trois établissements sans département déterminé",
                 bilan_inconnu["pages_departement"][eh.PAGE_INDETERMINEE] == 3
                 and all(f"<td>{n}</td>" in indeterminee
                         for n in ("010000023", "010000024", "970000025")),
                 bilan_inconnu["pages_departement"][eh.PAGE_INDETERMINEE])
        verifier("page indéterminée : chaque motif affiché ([absent], [non résolu], 975 hors référentiel)",
                 "<td>[absent]</td>" in indeterminee and "<td>[non résolu]</td>" in indeterminee
                 and "<td>975 [hors référentiel]</td>" in indeterminee)
        verifier("compteurs : 1 sans adresse, 1 non résolu, 1 hors référentiel",
                 bilan_inconnu["sans_adresse_principale"] == 1
                 and bilan_inconnu["departement_non_resolu"] == 1
                 and bilan_inconnu["departement_hors_referentiel"] == 1, bilan_inconnu)
        verifier("aucun établissement écarté : somme des pages = 6",
                 sum(bilan_inconnu["pages_departement"].values()) == 6
                 == bilan_inconnu["nombre_etablissements"])
        verifier("aucune page départementale 975 inventée",
                 not (site_inconnu / "departement/975.html").exists()
                 and not (site_inconnu / "departement/975").exists())
        verifier("page indéterminée : sommaire liant sa sous-page, avec ses 3 fiches",
                 '<a href="indetermine/1.html">Sous-page 1</a></td><td class="effectif">3</td>'
                 in lire(site_inconnu, "departement/indetermine.html"))

        verifier("indicateur : Z99 et les 2 actifs sans département comptés en exclusion",
                 bilan_inconnu["indicateur_exclus"] == 3
                 and bilan_inconnu["indicateur_total_actifs"] == 6, bilan_inconnu)
        indicateur = lire(site_inconnu, "indicateur.html")
        verifier("indicateur.html : pied signale 1 catégorie non résolue",
                 "1 avec catégorie non résolue" in indicateur)
        pages_ind = [lire(site_inconnu, p) for p in bilan_inconnu["pages_ecrites"]
                     if p.startswith("indicateur/")]
        verifier("indicateur : la case de 975 (hors référentiel des départements, mais dans "
                 "le tableau) a sa page, comme les autres",
                 (site_inconnu / "indicateur/975.html").is_file() and len(pages_ind) == 3,
                 len(pages_ind))
        accueil = lire(site_inconnu, "index.html")
        verifier("index.html : 3 actifs non répartis affichés",
                 "<strong>3</strong><span>actifs non répartis" in accueil)
        verifier("index.html : la ligne « indéterminé » porte l'actif de 975 et ses 3 fiches",
                 '<a href="departement/indetermine.html">Département indéterminé</a></td>'
                 '<td class="effectif">1</td><td class="fiches">3</td>' in accueil)
        bandeau = _bandeau(lire(site_inconnu, eh.PAGE_CARTE))
        verifier("carte.html : bandeau à 0,0 % (aucune coordonnée), les 3 sans département "
                 "déterminé comptés et liés à la page indéterminée, sans phrase d'invalides",
                 "0,0 % des établissements du répertoire FINESS" in bandeau
                 and "0 sur 6." in bandeau and "6 n'y figurent pas : 6 sans coordonnées" in bandeau
                 and '<a href="departement/indetermine.html">3 établissement(s) sans département '
                     'déterminé</a>, dont 0 localisé(s)' in bandeau
                 and "interverties" not in bandeau, bandeau)
        verifier("carte départementale : pas de phrase sur les indéterminés",
                 "sans département déterminé" not in _bandeau(lire(site_inconnu, "carte/01.html")))
        verifier("somme des bandeaux départementaux + indéterminés = national (6)",
                 sum(bilan_inconnu["couverture_cartes"][c]["total"] for c in DEPARTEMENTS) + 3
                 == bilan_inconnu["couverture_cartes"][""]["total"] == 6)
        verifier("aucune page ne cite Z99 ailleurs que sur la page de son département",
                 "Z99" not in indicateur and "Z99" not in accueil
                 and all("Z99" not in c for c in pages_ind))

    # -----------------------------------------------------------------------
    print("\n3. Gabarit manquant -> échec bruyant, rien d'écrit")
    with Entrepot(TMP / "echantillon.db") as e:
        for manquant, decoupage in ((eh.GABARIT_BASE, "departement"),
                                    ("accueil.html", "departement"),
                                    ("indicateur.html", "departement"),
                                    (eh.GABARIT_DEPARTEMENT, "departement"),
                                    (eh.GABARIT_SOUS_PAGE, "departement"),
                                    (eh.GABARIT_CARTE, "departement"),
                                    (eh.GABARIT_INDICATEUR_DEPARTEMENT, "national"),
                                    ("liste.html", "national")):
            gabarits = TMP / f"gabarits_sans_{manquant}" / "gabarits"
            shutil.copytree(GABARITS, gabarits)
            shutil.copytree(ACTIFS, gabarits.parent / "actifs")
            shutil.copytree(VENDOR, gabarits.parent / "vendor")
            (gabarits / manquant).unlink()
            sortie = TMP / f"sortie_sans_{manquant}"
            try:
                eh.rendre(e, gabarits, sortie, decoupage=decoupage)
                verifier(f"{manquant} absent : ErreurExportHtml levée", False)
            except eh.ErreurExportHtml as erreur:
                verifier(f"{manquant} absent : ErreurExportHtml levée", True)
                verifier(f"{manquant} absent : chemin attendu dans le message",
                         str(gabarits / manquant) in str(erreur), str(erreur))
            verifier(f"{manquant} absent : dossier de sortie non créé", not sortie.exists())

        # Même garantie sur un site déjà rendu : un gabarit manquant ne le
        # régénère pas à moitié.
        avant = {p: (site / p).read_bytes() for p in bilan["pages_ecrites"]}
        gabarits = TMP / "gabarits_sans_departement_site_existant" / "gabarits"
        shutil.copytree(GABARITS, gabarits)
        shutil.copytree(ACTIFS, gabarits.parent / "actifs")
        shutil.copytree(VENDOR, gabarits.parent / "vendor")
        (gabarits / eh.GABARIT_DEPARTEMENT).unlink()
        try:
            eh.rendre(e, gabarits, site)
            verifier("site existant : ErreurExportHtml levée", False)
        except eh.ErreurExportHtml:
            verifier("site existant : ErreurExportHtml levée", True)
        verifier("site existant : aucune page réécrite",
                 all((site / p).read_bytes() == avant[p] for p in avant))

        # Bloc obligatoire absent : même politique, le chemin est cité.
        gabarits = TMP / "gabarits_bloc_absent" / "gabarits"
        shutil.copytree(GABARITS, gabarits)
        shutil.copytree(ACTIFS, gabarits.parent / "actifs")
        shutil.copytree(VENDOR, gabarits.parent / "vendor")
        cible = gabarits / "indicateur.html"
        cible.write_text(re.sub(r"<!-- BLOC contenu -->.*?<!-- FIN contenu -->", "",
                                cible.read_text(encoding="utf-8"), flags=re.DOTALL),
                         encoding="utf-8")
        sortie = TMP / "sortie_bloc_absent"
        try:
            eh.rendre(e, gabarits, sortie)
            verifier("bloc « contenu » absent : ErreurExportHtml levée", False)
        except eh.ErreurExportHtml as erreur:
            verifier("bloc « contenu » absent : ErreurExportHtml levée",
                     str(cible) in str(erreur) and "contenu" in str(erreur), str(erreur))
        verifier("bloc « contenu » absent : dossier de sortie non créé", not sortie.exists())

        # Dépendance vendorisée absente (OOM-113) : la carte échouerait au
        # clic sur un 404 — l'export refuse avant d'écrire.
        for absent in ("vendor", eh.VENDOR_CARTE["maplibre"], eh.VENDOR_CARTE["pmtiles"]):
            racine = TMP / f"vendor_absent_{absent.replace('/', '_')}"
            gabarits = racine / "gabarits"
            shutil.copytree(GABARITS, gabarits)
            shutil.copytree(ACTIFS, racine / "actifs")
            shutil.copytree(VENDOR, racine / "vendor")
            cible = racine / absent
            shutil.rmtree(cible) if cible.is_dir() else cible.unlink()
            sortie = TMP / f"sortie_{racine.name}"
            try:
                eh.rendre(e, gabarits, sortie)
                verifier(f"{absent} absent : ErreurExportHtml levée", False)
            except eh.ErreurExportHtml as erreur:
                verifier(f"{absent} absent : ErreurExportHtml, chemin cité, rien d'écrit",
                         str(cible) in str(erreur) and not sortie.exists(), str(erreur))

print(f"\n{ok} OK, {ko} ÉCHEC(s)")
sys.exit(1 if ko else 0)
