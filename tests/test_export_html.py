"""test_export_html.py — Critères de sortie d'OOM-104 et OOM-106 (rendu du site
par gabarits, une page par département).

Vérifie `export_html.rendre` (contrats A et B) :

1. de bout en bout sur l'échantillon FINESS versionné (Structures + Activités),
   chargé dans un dossier temporaire, en découpage départemental (défaut) :
   accueil, indicateur, 101 pages départementales + la page indéterminée,
   chacune ne portant que ses établissements (somme = total), liens relatifs,
   aucun JSON chargé, mention de périmètre, actifs copiés, aucun `$` non
   substitué ;
1 bis. le découpage national : `liste.html` et ses compteurs, comme avant ;
1 ter. les activités chargées à la demande (OOM-107) : un fragment
   `donnees/activites/<code>.json` par page, de même structure
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
"""
from __future__ import annotations
import functools, html, http.server, json, re, shutil, subprocess, sys, tempfile, threading
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
import export_html as eh

ECHANTILLON = Path(__file__).resolve().parent / "echantillon"
S = ECHANTILLON / "finess-structures-mensuel-202607-echantillon_json.gz"
A = ECHANTILLON / "finess-activites-mensuel-202607-echantillon_json.gz"
GABARITS = eh.DOSSIER_GABARITS
ACTIFS = GABARITS.parent / "actifs"

# Un `$` suivi d'un identifiant ou d'une accolade : trou de gabarit non rempli.
_TROU = re.compile(r"\$[A-Za-z_{]")
# Un lien ou une ressource à chemin absolu : interdit, le site est servi sous
# un sous-chemin GitHub Pages.
_ABSOLU = re.compile(r'(?:href|src)="/')
DEPARTEMENTS = charger_departements()
PAGES_DEP = [eh.chemin_page_departement(c) for c in list(DEPARTEMENTS) + [eh.PAGE_INDETERMINEE]]

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


def verifier_activites_a_la_demande(site, bilan, activites, attendu_par_page, pages):
    print("\n1 ter. Activités à la demande (OOM-107)")
    codes = list(DEPARTEMENTS) + [eh.PAGE_INDETERMINEE]
    attendus = [eh.chemin_fragment_activites(c) for c in codes]
    verifier("un fragment par page départementale, au chemin du contrat B",
             bilan["fragments_ecrits"] == attendus
             and attendus[:1] == ["donnees/activites/01.json"], bilan["fragments_ecrits"][:3])
    verifier("chaque fragment sur disque, taille = octets annoncés",
             all((site / f).stat().st_size == bilan["octets_fragments"][f] for f in attendus))
    fragments = {f: json.loads(lire(site, f)) for f in attendus}
    attendu = {eh.chemin_fragment_activites(Path(p).stem):
               {n: activites[n] for n in nums if n in activites}
               for p, nums in attendu_par_page.items()}
    verifier("chaque fragment = activites_par_etablissement restreint à sa page "
             "(structure inchangée)", fragments == attendu,
             [f for f in attendus if fragments[f] != attendu[f]][:3])
    verifier("activités des fragments = activites_total, 0 orpheline sur l'échantillon",
             bilan["activites_fragments"] == bilan["activites_total"]
             and bilan["activites_orphelines"] == 0, bilan["activites_fragments"])
    toutes = [a for f in fragments.values() for lignes in f.values() for a in lignes]
    verifier("code_nature brut, libelle_nature None partout (aucune nomenclature, OOM-29)",
             toutes and all(a["libelle_nature"] is None and a["code_nature"] for a in toutes))
    verifier("page vide : fragment « {} »",
             all(fragments[eh.chemin_fragment_activites(Path(p).stem)] == {}
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
    page = pages["departement/44.html"]
    verifier("table : data-fragment relatif vers son fragment",
             'data-fragment="../donnees/activites/44.json"' in page)
    verifier("sans JS : lien <noscript> vers le fragment (D10)",
             '<noscript><p class="alerte">' in page
             and 'href="../donnees/activites/44.json"' in page)
    verifier("îlot activites.js chargé en relatif, aucun script inline",
             'src="../actifs/activites.js"' in page and "<script>" not in page)
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
        url_page = urljoin(base, "departement/44.html")
        with urlopen(url_page) as r:
            servie = r.read().decode("utf-8")
        for ressource in _sous_ressources(servie):
            with urlopen(urljoin(url_page, ressource)) as r:
                r.read()
        initial = list(_Journal.journal)
        verifier("chargement initial servi : page, feuille de style, deux îlots, "
                 "aucune requête d'activités", initial == [
                     "/departement/44.html", "/actifs/ooms.css", "/actifs/filtres.js",
                     "/actifs/activites.js"], initial)
        url_fragment = urljoin(url_page, re.search(r'data-fragment="([^"]+)"', servie).group(1))
        with urlopen(url_fragment) as r:
            servi = json.loads(r.read().decode("utf-8"))
        verifier("« clic » : le fragment est servi au chemin annoncé, contenu attendu",
                 _Journal.journal[len(initial):] == ["/donnees/activites/44.json"]
                 and servi == fragments["donnees/activites/44.json"], _Journal.journal)
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
            {"fragment": urljoin(base, "donnees/activites/44.json"),
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
    attendu_0 = fragments["donnees/activites/44.json"][avec[0]["finess"]]
    verifier("Node : aucune requête au chargement de la page", r["requetes_initiales"] == [],
             r["requetes_initiales"])
    verifier("Node : premier clic -> une requête, vers le fragment de la page",
             n[0] == 1 and r["requetes"][0].endswith("/donnees/activites/44.json"), r["requetes"])
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


with tempfile.TemporaryDirectory(prefix="test_export_html_") as temporaire:
    TMP = Path(temporaire)

    # -----------------------------------------------------------------------
    print("1. Rendu de bout en bout sur l'échantillon versionné (découpage départemental)")
    site = TMP / "site"
    site_national = TMP / "site_national"
    with Entrepot(TMP / "echantillon.db") as e:
        e.creer()
        charger(e, SourceFinessStructures(), S, controle=CONTROLE_MINIMAL)
        charger(e, SourceFinessActivites(), A, controle=CONTROLE_MINIMAL)
        bilan = eh.rendre(e, GABARITS, site)
        bilan_national = eh.rendre(e, GABARITS, site_national, decoupage="national")

        # Références indépendantes : les couches qu'export_html dit relire.
        etablissements = etablissements_bruts(e)
        activites = activites_par_etablissement(e)
        resultat = indicateur_departement_categorie(e)

    attendues = list(eh.PAGES_NATIONALES["departement"]) + PAGES_DEP
    verifier("millésime de l'échantillon (202607)", bilan["millesime"] == "202607", bilan["millesime"])
    verifier("découpage par défaut : departement", bilan["decoupage"] == "departement",
             bilan["decoupage"])
    verifier("pages écrites : accueil, indicateur, puis 101 départements + indéterminé",
             bilan["pages_ecrites"] == attendues and len(PAGES_DEP) == 102,
             bilan["pages_ecrites"][:5])
    manquantes = [p for p in attendues
                  if not (site / p).is_file() or (site / p).stat().st_size != bilan["octets"][p]]
    verifier("chaque page présente sur disque, taille = octets annoncés", not manquantes,
             manquantes[:5])
    fichiers = sorted((site / "departement").glob("*.html"))
    verifier("102 fichiers dans departement/ (101 + indetermine.html)", len(fichiers) == 102,
             len(fichiers))
    verifier("liste.html non produite en découpage départemental",
             not (site / "liste.html").exists())
    verifier("codes corses en texte : 2A.html et 2B.html, clés « 2A »/« 2B »",
             (site / "departement/2A.html").is_file() and (site / "departement/2B.html").is_file()
             and "2A" in bilan["pages_departement"] and "2B" in bilan["pages_departement"])
    verifier("zéro de tête conservé : 01.html, pas de 1.html",
             (site / "departement/01.html").is_file()
             and not (site / "departement/1.html").exists())

    verifier("nombre_etablissements = export_front.etablissements_bruts",
             bilan["nombre_etablissements"] == len(etablissements) > 0,
             (bilan["nombre_etablissements"], len(etablissements)))
    verifier("somme des pages départementales = total des établissements",
             sum(bilan["pages_departement"].values()) == len(etablissements),
             sum(bilan["pages_departement"].values()))
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
    verifier("indicateur_total_actifs / exclus = Resultat",
             bilan["indicateur_total_actifs"] == resultat.total_actifs
             and bilan["indicateur_exclus"] == resultat.exclus(), bilan)
    verifier("accueil : départements / catégories = marges de Resultat",
             bilan["accueil_departements"] == len(resultat.par_departement())
             and bilan["accueil_categories"] == len(resultat.par_categorie()), bilan)

    # Chaque page n'embarque que ses établissements, chacun dans la page de son
    # département — un établissement, une seule page.
    pages = {p: lire(site, p) for p in PAGES_DEP}
    lignes_par_page = {p: re.findall(r'<tr data-dep="[^"]*" data-cat="[^"]*" data-etat="[^"]*">'
                                     r'<td>([^<]*)</td>', contenu)
                       for p, contenu in pages.items()}
    attendu_par_page = {p: [] for p in PAGES_DEP}
    for x in etablissements:
        code = (x["code_departement"] if x["code_departement"] in DEPARTEMENTS
                else eh.PAGE_INDETERMINEE)
        attendu_par_page[eh.chemin_page_departement(code)].append(x["num_finess_et"])
    verifier("chaque page départementale porte exactement ses établissements",
             lignes_par_page == attendu_par_page,
             [p for p in PAGES_DEP if lignes_par_page[p] != attendu_par_page[p]][:5])
    verifier("lignes_rendues = pages_departement pour chaque page",
             all(bilan["lignes_rendues"][eh.chemin_page_departement(c)] == n
                 for c, n in bilan["pages_departement"].items()))
    verifier("un <details data-finess> par établissement ayant des activités, sur l'ensemble "
             "des pages", sum(c.count("<details data-finess=") for c in pages.values())
             == bilan["etablissements_avec_activites"])
    vides = [p for p in PAGES_DEP if not attendu_par_page[p]]
    verifier("l'échantillon laisse des départements sans établissement (prérequis)", len(vides) > 0)
    verifier("département sans établissement : page explicite, message « aucun »",
             all('id="aucun"' in pages[p] and "<table" not in pages[p] for p in vides), vides[:5])
    verifier("titre de page = libellé et code du référentiel (2A)",
             "<h1>Corse-du-Sud (2A)</h1>" in pages["departement/2A.html"])
    verifier("rappel de périmètre en tête de chaque page départementale",
             all('<main>\n<p class="perimetre" id="perimetre">' in c
                 and "la qualification enfance/adolescents n'est pas encore appliquée" in c
                 for c in pages.values()))
    verifier("pages départementales : style et navigation relatifs (../)",
             all('href="../actifs/ooms.css"' in c and 'href="../index.html"' in c
                 and 'href="../indicateur.html"' in c for c in pages.values()))
    verifier("page non vide : îlot filtres.js chargé en relatif",
             'src="../actifs/filtres.js"' in pages["departement/01.html"])

    indicateur = lire(site, "indicateur.html")
    accueil = lire(site, "index.html")

    verifier("indicateur.html : une ligne par case du tableau",
             indicateur.count('<tr data-dep="') == bilan["indicateur_lignes"],
             indicateur.count('<tr data-dep="'))
    verifier("indicateur.html : total du pied de tableau = dans_tableau",
             f'id="total">{resultat.dans_tableau()}</td>' in indicateur)
    rendues = re.findall(r'<tr data-dep="[^"]*"><td>([^<]*)</td><td>([^<]*)</td>'
                         r'<td class="effectif" data-valeur="(\d+)"', indicateur)
    attendues = [(html.escape(d), html.escape(c), str(n)) for d, c, n in resultat.lignes_triees()]
    verifier("indicateur.html : lignes identiques et dans l'ordre de Resultat.lignes_triees",
             rendues == attendues, (rendues[:3], attendues[:3]))

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
        if _TROU.search(contenu): defauts[page] = f"$ non substitué {_TROU.findall(contenu)[:3]}"
        elif "<!-- BLOC" in contenu or "<!-- FIN" in contenu: defauts[page] = "commentaire de gabarit"
        elif "ooms.css" not in contenu: defauts[page] = "feuille de style absente"
        elif _ABSOLU.search(contenu): defauts[page] = "lien absolu"
        elif set(re.findall(r'[^"\s>]*\.json', contenu)) - {
                "../" + eh.chemin_fragment_activites(Path(page).stem)}:
            defauts[page] = "cite un JSON autre que son propre fragment"
    verifier("toutes les pages : aucun $ non substitué, aucun commentaire de gabarit, "
             "feuille de style liée, aucun lien absolu, aucun JSON cité hors fragment propre",
             not defauts, list(defauts.items())[:3])
    verifier("D9 : aucune page de l'échantillon au-delà de 500 Ko",
             max(bilan["octets"].values()) <= 500 * 1024, max(bilan["octets"].values()))

    attendus = sorted(p.name for p in ACTIFS.iterdir() if p.is_file())
    verifier("actifs copiés = contenu de front/actifs/",
             bilan["actifs_copies"] == attendus and attendus, bilan["actifs_copies"])
    verifier("actifs copiés à l'identique (octets)",
             all((site / "actifs" / n).read_bytes() == (ACTIFS / n).read_bytes()
                 for n in attendus))

    verifier_activites_a_la_demande(site, bilan, activites, attendu_par_page, pages)

    # -----------------------------------------------------------------------
    print("\n1 bis. Découpage national (decoupage=\"national\")")
    verifier("les trois pages nationales écrites, dans l'ordre de PAGES",
             bilan_national["pages_ecrites"] == list(eh.PAGES), bilan_national["pages_ecrites"])
    verifier("aucune page départementale en national",
             not (site_national / "departement").exists()
             and bilan_national["pages_departement"] == {})
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
        page_01 = lire(site_inconnu, "departement/01.html")
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
                 and "<td>2A0000022</td>" in lire(site_inconnu, "departement/2A.html"))
        indeterminee = lire(site_inconnu, "departement/indetermine.html")
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
        verifier("aucun fichier 975.html inventé",
                 not (site_inconnu / "departement/975.html").exists())

        verifier("indicateur : Z99 et les 2 actifs sans département comptés en exclusion",
                 bilan_inconnu["indicateur_exclus"] == 3
                 and bilan_inconnu["indicateur_total_actifs"] == 6, bilan_inconnu)
        indicateur = lire(site_inconnu, "indicateur.html")
        verifier("indicateur.html : pied signale 1 catégorie non résolue",
                 "1 avec catégorie non résolue" in indicateur)
        accueil = lire(site_inconnu, "index.html")
        verifier("index.html : 3 actifs non répartis affichés",
                 "<strong>3</strong><span>actifs non répartis" in accueil)
        verifier("index.html : la ligne « indéterminé » porte l'actif de 975 et ses 3 fiches",
                 '<a href="departement/indetermine.html">Département indéterminé</a></td>'
                 '<td class="effectif">1</td><td class="fiches">3</td>' in accueil)
        verifier("aucune page ne cite Z99 ailleurs que sur la page de son département",
                 "Z99" not in indicateur and "Z99" not in accueil)

    # -----------------------------------------------------------------------
    print("\n3. Gabarit manquant -> échec bruyant, rien d'écrit")
    with Entrepot(TMP / "echantillon.db") as e:
        for manquant, decoupage in ((eh.GABARIT_BASE, "departement"),
                                    ("accueil.html", "departement"),
                                    ("indicateur.html", "departement"),
                                    (eh.GABARIT_DEPARTEMENT, "departement"),
                                    ("liste.html", "national")):
            gabarits = TMP / f"gabarits_sans_{manquant}" / "gabarits"
            shutil.copytree(GABARITS, gabarits)
            shutil.copytree(ACTIFS, gabarits.parent / "actifs")
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

print(f"\n{ok} OK, {ko} ÉCHEC(s)")
sys.exit(1 if ko else 0)
