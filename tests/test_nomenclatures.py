"""test_nomenclatures.py — Critère de sortie de OOM-12 (résolution categorie)."""
from __future__ import annotations
import csv
import importlib.util
import sys
import tempfile
from pathlib import Path

import nomenclatures as n

ok = ko = 0
def verifier(intitule, condition, detail=""):
    global ok, ko
    if condition: ok += 1; print(f"  OK    {intitule}")
    else: ko += 1; print(f"  ECHEC {intitule} — {detail}")


print("1. Le référentiel par défaut se charge et respecte sa propre provenance")
categories = n.charger_categories()
verifier("référentiel non vide", len(categories) > 0, len(categories))
verifier("322 codes, ceux de TRE_R66 version 20260505120000 (OOM-118)",
         len(categories) == 322, len(categories))
verifier("aucun libellé vide", all(lib.strip() for lib in categories.values()))
verifier("aucun code vide", all(code.strip() for code in categories))


print("2. Résolution de codes réels connus (extrait FINESS-Structures 202607)")
# Ces couples code -> libellé proviennent de la source qui fait foi, ANS NOS
# TRE_R66 (cf. en-tête de referentiels/nomenclature_categorie_finess.csv),
# et correspondent aux codes effectivement observés dans l'entrepôt réel.
attendus = {
    "183": "Institut Médico-Educatif (I.M.E.)",
    "186": "Institut Thérapeutique Éducatif et Pédagogique (I.T.E.P.)",
    "177": "Maison d'Enfants à Caractère Social",
    "182": "Service d'Éducation Spéciale et de Soins à Domicile",
    "190": "Centre Action Médico-Sociale Précoce (C.A.M.S.P.)",
    "620": "Pharmacie d'Officine",
}
for code, libelle_attendu in attendus.items():
    obtenu = n.resoudre_categorie(code)
    verifier(f"code {code} -> {libelle_attendu!r}", obtenu == libelle_attendu,
             f"obtenu {obtenu!r}")

print("3. categorie_connue reflète le référentiel sans lever d'exception")
verifier("code connu (183) déclaré connu", n.categorie_connue("183") is True)
verifier("code inconnu (999) déclaré inconnu", n.categorie_connue("999") is False)


print("4. Code absent du référentiel : signalement explicite, jamais silencieux")
# 999 n'existe dans aucune nomenclature FINESS publiée : code de test sûr.
try:
    resultat = n.resoudre_categorie("999")
    verifier("lève CodeCategorieInconnu plutôt que de retourner une valeur", False,
             f"a retourné {resultat!r} au lieu de lever")
except n.CodeCategorieInconnu as erreur:
    verifier("lève précisément CodeCategorieInconnu", True)
    verifier("l'exception porte le code fautif", erreur.code == "999", erreur.code)
    verifier("le message ne recopie pas un libellé inventé",
             "999" in str(erreur) and "inconnu" in str(erreur).lower(), str(erreur))
except Exception as erreur:  # tout autre type serait un échec non contrôlé
    verifier("lève précisément CodeCategorieInconnu", False,
             f"a levé {type(erreur).__name__} au lieu de CodeCategorieInconnu")

verifier("CodeCategorieInconnu hérite de ErreurNomenclature",
         issubclass(n.CodeCategorieInconnu, n.ErreurNomenclature))


print("4 bis. Codes ajoutés par OOM-117 (ANS, NOS TRE_R66, version 20260505)")
# Ces codes, observés dans les extraits 202607 et 202609, manquaient aux
# documents DREES/DMSI de 2021. Les libellés sont le « Libellé long » de
# TRE_R66 (cf. en-tête de referentiels/nomenclature_categorie_finess.csv).
ajoutes = {
    "259": "Autres résidences sociales",
    "601": "Cabinet Libéral Médical",
    "640": "Service d'aide et d'accompagnement à domicile aux familles (SAADF)",
    "650": "Dispositifs Spécifiques Régionaux en périnatalité",
}
for code, libelle_attendu in ajoutes.items():
    obtenu = n.resoudre_categorie(code)
    verifier(f"code {code} -> {libelle_attendu!r}", obtenu == libelle_attendu,
             f"obtenu {obtenu!r}")


print("4 ter. TRE_R66 fait foi pour tout le référentiel (OOM-118)")
# Libellés renommés par TRE_R66 depuis les PDF DREES/DMSI de 2021, et
# catégories ajoutées par la version 20260505120000.
renommes = {
    "209": "Service autonomie aide et soins (SAAS)",
    "460": "Service autonomie aide (SAA)",
    "228": "Centre de Santé Sexuelle",
    "701": "Maison des adolescents (MDA)",
}
for code, libelle_attendu in renommes.items():
    obtenu = n.resoudre_categorie(code)
    verifier(f"code {code} -> {libelle_attendu!r}", obtenu == libelle_attendu,
             f"obtenu {obtenu!r}")
with open(n.CHEMIN_REFERENTIEL_CATEGORIE, encoding="utf-8", newline="") as f:
    lignes = list(csv.DictReader((l for l in f if not l.startswith("#")), delimiter=";"))
par_code = {l["code"]: l for l in lignes}
verifier("chaque ligne indique son origine (colonne source)",
         all(l.get("source") for l in lignes))
verifier("toutes les lignes viennent de TRE_R66 (aucun code hors source à ce jour)",
         all(l["source"] == "ANS_TRE_R66" for l in lignes))
verifier("159 fermée le 2016-05-05 selon TRE_R66",
         (par_code["159"]["statut"], par_code["159"]["date_fermeture"]) == ("fermee", "2016-05-05"),
         par_code["159"])
verifier("date de fin présente <=> catégorie fermée",
         all((l["statut"] == "fermee") == bool(l["date_fermeture"]) for l in lignes))
with open(n.CHEMIN_REFERENTIEL_CATEGORIE, encoding="utf-8") as f:
    en_tete = "".join(l for l in f if l.startswith("#"))
verifier("en-tête : version de TRE_R66 notée", "version 20260505120000" in en_tete)


print("4 quater. Script de mise à jour : aucun code retiré, origine conservée")
spec = importlib.util.spec_from_file_location(
    "maj_nomenclature_categories",
    Path(__file__).resolve().parent.parent / "scripts" / "maj_nomenclature_categories.py")
maj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maj)
tabs = "\n".join([
    "<OID>;<Type fichier>;<Nom fichier>;<Description>;<URL fichier>;<Date valid>;<Date fin>;<Date MàJ>",
    f"{maj.OID};TRE;TRE_R66_CategorieEtablissement.tabs;Test;url;19790101000000;;20990101000000",
    "<OID>;<Code>;<Libellé adapté>;<Libellé court>;<Libellé long>;<Date valid>;<Date fin>;<Date MàJ> ",
    f"{maj.OID};Z1;adapté;court;Libellé long Z1;19790101000000;;19790101000000",
    f"{maj.OID};Z2;adapté;court;Libellé long Z2;19790101000000;20200101000000;19790101000000",
    f"{maj.OID};Z3;adapté;court;Libellé long Z3;19790101000000;20990101000000;19790101000000",
]) + "\n"
meta, concepts = maj.lire_tabs(tabs.encode("utf-8"))
verifier("version lue dans l'en-tête .tabs", meta["date_maj"] == "20990101000000", meta)
actuel = {
    "Z1": {"code": "Z1", "libelle": "Ancien Z1", "statut": "ouverte", "date_fermeture": ""},
    "Z9": {"code": "Z9", "libelle": "Code absent de la source", "statut": "ouverte",
           "date_fermeture": ""},
}
nouvelles = {l["code"]: l for l in maj.construire(concepts, actuel, "2026-09-29")}
verifier("libellé long de la source retenu", nouvelles["Z1"]["libelle"] == "Libellé long Z1")
verifier("date de fin passée -> fermée",
         (nouvelles["Z2"]["statut"], nouvelles["Z2"]["date_fermeture"]) == ("fermee", "2020-01-01"))
verifier("date de fin future -> encore ouverte", nouvelles["Z3"]["statut"] == "ouverte")
verifier("code absent de la source conservé, jamais retiré",
         nouvelles.get("Z9", {}).get("libelle") == "Code absent de la source", nouvelles.get("Z9"))
verifier("origine indiquée pour le code conservé",
         nouvelles.get("Z9", {}).get("source") == "hors_TRE_R66", nouvelles.get("Z9"))
try:
    doublon = f"{maj.OID};Z1;adapté;court;Doublon;19790101000000;;19790101000000"
    maj.lire_tabs((tabs + doublon).encode("utf-8"))
    verifier("source malformée (code en double) -> erreur explicite", False, "aucune exception")
except maj.ErreurSource:
    verifier("source malformée (code en double) -> erreur explicite", True)


print("5. Un référentiel explicite peut être injecté (appel en masse, tests)")
petit_referentiel = {"A1": "Libellé de test A1"}
verifier("résolution via référentiel injecté",
         n.resoudre_categorie("A1", categories=petit_referentiel) == "Libellé de test A1")
try:
    n.resoudre_categorie("183", categories=petit_referentiel)
    verifier("référentiel injecté isole du référentiel par défaut", False,
             "183 n'aurait pas dû résoudre via petit_referentiel")
except n.CodeCategorieInconnu:
    verifier("référentiel injecté isole du référentiel par défaut", True)


print("6. Garde-fous de chargement")
dossier_temp = Path(tempfile.gettempdir()) / "tests_nomenclatures"
dossier_temp.mkdir(exist_ok=True)

chemin_absent = dossier_temp / "n_existe_pas.csv"
try:
    n.charger_categories(chemin_absent)
    verifier("fichier référentiel absent -> erreur explicite", False,
             "aucune exception levée")
except n.ErreurNomenclature:
    verifier("fichier référentiel absent -> erreur explicite", True)

chemin_incoherent = dossier_temp / "incoherent.csv"
chemin_incoherent.write_text(
    "# commentaire de provenance ignoré par le chargeur\n"
    "code;libelle;statut;date_fermeture\n"
    "Z1;Premier libellé;ouverte;\n"
    "Z1;Second libellé différent;ouverte;\n",
    encoding="utf-8",
)
try:
    n.charger_categories(chemin_incoherent)
    verifier("code en double avec libellés divergents -> erreur explicite", False,
             "aucune exception levée")
except n.ErreurNomenclature:
    verifier("code en double avec libellés divergents -> erreur explicite", True)

chemin_valide = dossier_temp / "valide.csv"
chemin_valide.write_text(
    "# commentaire de provenance ignoré par le chargeur\n"
    "code;libelle;statut;date_fermeture\n"
    "Z1;Un libellé;ouverte;\n"
    "Z2;Un autre libellé;fermee;2020-01-01\n",
    encoding="utf-8",
)
categories_test = n.charger_categories(chemin_valide)
verifier("chargement d'un référentiel minimal valide",
         categories_test == {"Z1": "Un libellé", "Z2": "Un autre libellé"},
         categories_test)


print(f"\n{ok} tests réussis, {ko} échecs")
sys.exit(1 if ko else 0)
