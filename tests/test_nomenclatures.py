"""test_nomenclatures.py — Critère de sortie de OOM-12 (résolution categorie)."""
from __future__ import annotations
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
verifier("274 codes, comme annoncé en en-tête du CSV",
         len(categories) == 274, len(categories))
verifier("aucun libellé vide", all(lib.strip() for lib in categories.values()))
verifier("aucun code vide", all(code.strip() for code in categories))


print("2. Résolution de codes réels connus (extrait FINESS-Structures 202607)")
# Ces couples code -> libellé proviennent de la documentation officielle
# DREES/DMSI (cf. en-tête de referentiels/nomenclature_categorie_finess.csv)
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

# Un code réellement observé dans l'extrait 202607 mais non couvert par ce
# référentiel partiel (série 60x apparue après la date de la source) doit
# être signalé exactement de la même façon : le mécanisme ne dépend pas de
# la raison de l'absence.
try:
    n.resoudre_categorie("601")
    verifier("code réel non couvert (601) signalé, pas ignoré", False,
             "aucune exception levée")
except n.CodeCategorieInconnu:
    verifier("code réel non couvert (601) signalé, pas ignoré", True)


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
