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
2. codes hors référentiel : catégorie `Z99` (repli `[non résolu]`, jamais un
   libellé inventé), et départements indéterminés (adresse absente, commune
   non résolue, collectivité `975` hors référentiel) rangés visiblement en
   page indéterminée, Corse en `2A.html` (D4, D6) ;
3. un gabarit manquant : échec bruyant, chemin dans le message, rien d'écrit.
"""
from __future__ import annotations
import html, re, shutil, sys, tempfile
from pathlib import Path

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
    verifier("un <details> par établissement ayant des activités, sur l'ensemble des pages",
             sum(c.count("<details>") for c in pages.values())
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
        elif ".json" in contenu: defauts[page] = "charge un JSON"
    verifier("toutes les pages : aucun $ non substitué, aucun commentaire de gabarit, "
             "feuille de style liée, aucun lien absolu, aucun JSON chargé",
             not defauts, list(defauts.items())[:3])
    verifier("D9 : aucune page de l'échantillon au-delà de 500 Ko",
             max(bilan["octets"].values()) <= 500 * 1024, max(bilan["octets"].values()))

    attendus = sorted(p.name for p in ACTIFS.iterdir() if p.is_file())
    verifier("actifs copiés = contenu de front/actifs/",
             bilan["actifs_copies"] == attendus and attendus, bilan["actifs_copies"])
    verifier("actifs copiés à l'identique (octets)",
             all((site / "actifs" / n).read_bytes() == (ACTIFS / n).read_bytes()
                 for n in attendus))

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
