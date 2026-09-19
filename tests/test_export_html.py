"""test_export_html.py — Critère de sortie d'OOM-104 (rendu du site par gabarits).

Vérifie `export_html.rendre` (contrat A, OOM-100) :

1. de bout en bout sur l'échantillon FINESS versionné (Structures + Activités),
   chargé dans un dossier temporaire : les trois pages, leurs compteurs
   confrontés à `export_front`/`indicateurs`, la mention de périmètre de
   l'accueil, les actifs copiés, aucun `$` laissé non substitué ;
2. un code de catégorie hors référentiel : repli visible (`[non résolu]` et
   code brut), jamais un plantage ni un libellé inventé (D4, D6) ;
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
import export_html as eh

ECHANTILLON = Path(__file__).resolve().parent / "echantillon"
S = ECHANTILLON / "finess-structures-mensuel-202607-echantillon_json.gz"
A = ECHANTILLON / "finess-activites-mensuel-202607-echantillon_json.gz"
GABARITS = eh.DOSSIER_GABARITS
ACTIFS = GABARITS.parent / "actifs"

# Un `$` suivi d'un identifiant ou d'une accolade : trou de gabarit non rempli.
_TROU = re.compile(r"\$[A-Za-z_{]")

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
    print("1. Rendu de bout en bout sur l'échantillon versionné")
    site = TMP / "site"
    with Entrepot(TMP / "echantillon.db") as e:
        e.creer()
        charger(e, SourceFinessStructures(), S, controle=CONTROLE_MINIMAL)
        charger(e, SourceFinessActivites(), A, controle=CONTROLE_MINIMAL)
        bilan = eh.rendre(e, GABARITS, site)

        # Références indépendantes : les couches qu'export_html dit relire.
        etablissements = etablissements_bruts(e)
        activites = activites_par_etablissement(e)
        resultat = indicateur_departement_categorie(e)

    verifier("millésime de l'échantillon (202607)", bilan["millesime"] == "202607", bilan["millesime"])
    verifier("les trois pages écrites, dans l'ordre de PAGES",
             bilan["pages_ecrites"] == list(eh.PAGES), bilan["pages_ecrites"])
    for page in eh.PAGES:
        verifier(f"{page} présent sur disque, taille = octets annoncés",
                 (site / page).is_file()
                 and (site / page).stat().st_size == bilan["octets"][page], bilan["octets"])

    verifier("nombre_etablissements = export_front.etablissements_bruts",
             bilan["nombre_etablissements"] == len(etablissements) > 0,
             (bilan["nombre_etablissements"], len(etablissements)))
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

    liste = lire(site, "liste.html")
    indicateur = lire(site, "indicateur.html")
    accueil = lire(site, "index.html")

    verifier("liste.html : une ligne <tr data-dep> par établissement",
             liste.count('<tr data-dep="') == bilan["nombre_etablissements"],
             liste.count('<tr data-dep="'))
    verifier("liste.html : un <details> par établissement ayant des activités",
             liste.count("<details>") == bilan["etablissements_avec_activites"],
             liste.count("<details>"))
    verifier("liste.html : chaque numéro FINESS présent",
             all(f"<td>{x['num_finess_et']}</td>" in liste for x in etablissements))
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
    verifier("index.html : une ligne par département et par catégorie",
             accueil.count('<td class="effectif">') ==
             len(resultat.par_departement()) + len(resultat.par_categorie()))
    verifier("index.html : lots de provenance listés (Structures et Activités)",
             "finess_structures" in accueil and "finess_activites" in accueil)

    for page in eh.PAGES:
        contenu = lire(site, page)
        verifier(f"{page} : aucun $ non substitué",
                 not _TROU.search(contenu), _TROU.findall(contenu)[:5])
        verifier(f"{page} : aucun commentaire de gabarit publié",
                 "<!-- BLOC" not in contenu and "<!-- FIN" not in contenu)
        verifier(f"{page} : lien vers la feuille de style commune",
                 'href="actifs/ooms.css"' in contenu)

    attendus = sorted(p.name for p in ACTIFS.iterdir() if p.is_file())
    verifier("actifs copiés = contenu de front/actifs/",
             bilan["actifs_copies"] == attendus and attendus, bilan["actifs_copies"])
    verifier("actifs copiés à l'identique (octets)",
             all((site / "actifs" / n).read_bytes() == (ACTIFS / n).read_bytes()
                 for n in attendus))

    # -----------------------------------------------------------------------
    print("\n2. Code de catégorie hors référentiel -> repli visible, pas de libellé inventé")
    try:
        resoudre_categorie("Z99")
        verifier("prérequis : Z99 absent du référentiel", False)
    except CodeCategorieInconnu:
        verifier("prérequis : Z99 absent du référentiel", True)

    site_inconnu = TMP / "site_inconnu"
    with Entrepot(TMP / "inconnu.db") as e:
        e.creer()
        c = e.connexion
        inserer(c, "entete", **LOT)
        inserer(c, "entite_juridique", **EJ)
        inserer(c, "etablissement", **etablissement("010000020", "G0", "183", "IME Connu"))
        inserer(c, "etablissement", **etablissement("010000021", "G1", "Z99", "Catégorie Inconnue"))
        inserer(c, "adresse", **adresse("G0", "01053"))
        inserer(c, "adresse", **adresse("G1", "01053"))
        try:
            bilan_inconnu = eh.rendre(e, GABARITS, site_inconnu)
            verifier("rendre ne plante pas sur un code hors référentiel", True)
        except Exception as erreur:  # noqa: BLE001 — le test veut justement tout attraper
            bilan_inconnu = None
            verifier("rendre ne plante pas sur un code hors référentiel", False, repr(erreur))

    if bilan_inconnu is not None:
        liste = lire(site_inconnu, "liste.html")
        ligne = next((l for l in liste.splitlines() if "<td>010000021</td>" in l), "")
        verifier("compteur : 1 catégorie non résolue", bilan_inconnu["categorie_non_resolue"] == 1,
                 bilan_inconnu)
        verifier("liste.html : repli « [non résolu] » sur la ligne de l'établissement",
                 "[non résolu]" in ligne, ligne)
        verifier("liste.html : code brut Z99 affiché", "(Z99)" in ligne, ligne)
        verifier("liste.html : aucun libellé inventé (data-cat vide)",
                 'data-cat=""' in ligne, ligne)
        verifier("liste.html : l'établissement connu garde son libellé",
                 "Institut Médico-Educatif (I.M.E.)" in liste)
        verifier("liste.html : Z99 n'apparaît pas comme option de catégorie",
                 '<option value="Z99">' not in liste and '<option value="[non résolu]">' not in liste)
        verifier("indicateur : l'actif hors référentiel est compté en exclusion",
                 bilan_inconnu["indicateur_exclus"] == 1
                 and bilan_inconnu["indicateur_total_actifs"] == 2, bilan_inconnu)
        indicateur = lire(site_inconnu, "indicateur.html")
        verifier("indicateur.html : pied signale 1 catégorie non résolue",
                 "1 avec catégorie non résolue" in indicateur)
        accueil = lire(site_inconnu, "index.html")
        verifier("index.html : 1 actif non réparti affiché", "<strong>1</strong><span>actifs non répartis" in accueil)
        verifier("aucune page ne cite Z99 ailleurs que dans la liste",
                 "Z99" not in indicateur and "Z99" not in accueil)

    # -----------------------------------------------------------------------
    print("\n3. Gabarit manquant -> échec bruyant, rien d'écrit")
    with Entrepot(TMP / "echantillon.db") as e:
        for manquant in (eh.GABARIT_BASE, "accueil.html", "liste.html", "indicateur.html"):
            gabarits = TMP / f"gabarits_sans_{manquant}" / "gabarits"
            shutil.copytree(GABARITS, gabarits)
            shutil.copytree(ACTIFS, gabarits.parent / "actifs")
            (gabarits / manquant).unlink()
            sortie = TMP / f"sortie_sans_{manquant}"
            try:
                eh.rendre(e, gabarits, sortie)
                verifier(f"{manquant} absent : ErreurExportHtml levée", False)
            except eh.ErreurExportHtml as erreur:
                verifier(f"{manquant} absent : ErreurExportHtml levée", True)
                verifier(f"{manquant} absent : chemin attendu dans le message",
                         str(gabarits / manquant) in str(erreur), str(erreur))
            verifier(f"{manquant} absent : dossier de sortie non créé", not sortie.exists())

        # Même garantie sur un site déjà rendu : un gabarit manquant ne le
        # régénère pas à moitié.
        avant = {p: (site / p).read_bytes() for p in eh.PAGES}
        gabarits = TMP / "gabarits_sans_liste_site_existant" / "gabarits"
        shutil.copytree(GABARITS, gabarits)
        shutil.copytree(ACTIFS, gabarits.parent / "actifs")
        (gabarits / "liste.html").unlink()
        try:
            eh.rendre(e, gabarits, site)
            verifier("site existant : ErreurExportHtml levée", False)
        except eh.ErreurExportHtml:
            verifier("site existant : ErreurExportHtml levée", True)
        verifier("site existant : aucune page réécrite",
                 all((site / p).read_bytes() == avant[p] for p in eh.PAGES))

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
