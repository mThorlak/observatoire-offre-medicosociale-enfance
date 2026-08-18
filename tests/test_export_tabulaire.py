"""test_export_tabulaire.py — Critère de sortie d'OOM-14 (stub en attente d'OOM-13).

Vérifie le stub de `export_tabulaire.py` sur des totaux calculables à la
main, ainsi que l'export CSV et le rapport de synthèse qui en découlent.
Voir le docstring du module pour le statut provisoire du calcul lui-même.
"""
from __future__ import annotations
import csv, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import finess_commun as fc
from entrepot import Entrepot
import export_tabulaire as et

BASE = Path("/tmp/tests_export_tabulaire"); BASE.mkdir(exist_ok=True)
ok = ko = 0


def verifier(intitule, condition, detail=""):
    global ok, ko
    if condition: ok += 1; print(f"  OK    {intitule}")
    else: ko += 1; print(f"  ECHEC {intitule} — {detail}")


def neuve(nom="e.db"):
    chemin = BASE / nom
    for suffixe in ("", "-wal", "-shm", "-journal"):
        p = Path(str(chemin) + suffixe)
        if p.exists(): p.unlink()
    return chemin


_TYPES = {t.nom: t for t in fc.TOUS_LES_TYPES}


def inserer(connexion, table, **valeurs):
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


def etablissement(num_finess_et, ege_id, code_categorie, etat_objet, nom="Ét. Test"):
    return dict(num_finess_et=num_finess_et, ege_id=ege_id,
                num_finess_ej=EJ["num_finess_ej"], pm_smsse_id=EJ["pm_smsse_id"],
                nom_court=nom, nom_long=nom, code_categorie=code_categorie,
                date_ouverture="1990-01-01", etat_objet=etat_objet,
                date_derniere_maj="2026-01-01", id_lot=LOT["id_lot"])


def adresse(ege_id, rang, code_usage, cog_commune, code_postal="01000"):
    return dict(type_porteur="ET", id_porteur=ege_id, num_finess_porteur=ege_id,
                rang=str(rang), code_usage_adresse=code_usage,
                code_postal=code_postal, cog_commune=cog_commune, id_lot=LOT["id_lot"])


print("1. tableau_departement_categorie — totaux vérifiables à la main")
chemin = neuve()
with Entrepot(chemin) as e:
    e.creer()
    c = e.connexion
    inserer(c, "entete", **LOT)
    inserer(c, "entite_juridique", **EJ)
    # Dept 01, catégorie 183 (IME) — deux établissements actifs.
    inserer(c, "etablissement", **etablissement("010000001", "G0", "183", "A", "IME Un"))
    inserer(c, "adresse", **adresse("G0", 1, "03", "01053"))
    inserer(c, "etablissement", **etablissement("010000002", "G1", "183", "A", "IME Deux"))
    inserer(c, "adresse", **adresse("G1", 1, "03", "01001"))
    # Dept 75, catégorie 500 (EHPAD) — un établissement actif.
    inserer(c, "etablissement", **etablissement("750000003", "G2", "500", "A", "EHPAD"))
    inserer(c, "adresse", **adresse("G2", 1, "03", "75056"))
    # Dept 01, actif mais fermé (I) — ne doit pas être compté.
    inserer(c, "etablissement", **etablissement("010000004", "G3", "183", "I", "IME Fermé"))
    inserer(c, "adresse", **adresse("G3", 1, "03", "01001"))
    # Dept 01, catégorie absente — actif, doit apparaître comme non renseignée.
    inserer(c, "etablissement", **etablissement("010000005", "G4", None, "A", "Sans catégorie"))
    inserer(c, "adresse", **adresse("G4", 1, "03", "01001"))
    # Dept 01, catégorie hors référentiel — actif, doit apparaître comme inconnue.
    inserer(c, "etablissement", **etablissement("010000006", "G5", "999", "A", "Catégorie inconnue"))
    inserer(c, "adresse", **adresse("G5", 1, "03", "01001"))
    # Actif, sans adresse principale — département non résoluble.
    inserer(c, "etablissement", **etablissement("010000007", "G6", "183", "A", "Sans adresse"))

    lignes, diagnostics = et.tableau_departement_categorie(e)

    verifier("6 établissements actifs comptés (le fermé G3 est exclu)",
             diagnostics.actifs_total == 6, diagnostics)
    verifier("1 établissement actif sans département résoluble (G6)",
             diagnostics.sans_departement_resolu == 1, diagnostics)
    verifier("1 établissement actif sans catégorie renseignée (G4)",
             diagnostics.sans_categorie == 1, diagnostics)
    verifier("1 établissement actif à catégorie hors référentiel (G5)",
             diagnostics.categories_inconnues == 1, diagnostics)
    verifier("4 lignes département×catégorie", len(lignes) == 4, lignes)

    par_cle = {(l.code_departement, l.code_categorie): l for l in lignes}
    verifier("dept 01 × IME (183) = 2", par_cle[("01", "183")].effectif == 2, lignes)
    verifier("libellé IME résolu", par_cle[("01", "183")].libelle_categorie ==
             "Institut Médico-Educatif (I.M.E.)", lignes)
    verifier("dept 75 × EHPAD (500) = 1", par_cle[("75", "500")].effectif == 1, lignes)
    verifier("dept 01 × catégorie absente = 1, libellé explicite",
             par_cle[("01", None)].effectif == 1 and
             par_cle[("01", None)].libelle_categorie == et.LIBELLE_CATEGORIE_ABSENTE, lignes)
    verifier("dept 01 × catégorie inconnue (999) = 1, libellé explicite",
             par_cle[("01", "999")].effectif == 1 and
             "999" in par_cle[("01", "999")].libelle_categorie, lignes)

    print("\n2. ecrire_csv — fichier écrit, lisible")
    chemin_csv = BASE / "sortie" / "departement_categorie.csv"
    et.ecrire_csv(lignes, chemin_csv)
    verifier("CSV écrit", chemin_csv.exists())
    with open(chemin_csv, encoding="utf-8", newline="") as f:
        contenu = list(csv.reader(f, delimiter=";"))
    verifier("en-tête + 4 lignes de données", len(contenu) == 5, contenu)
    verifier("en-tête attendu", contenu[0] ==
             ["code_departement", "code_categorie", "libelle_categorie", "effectif"], contenu[0])

    print("\n3. restituer — CSV + rapport écrits, cohérents")
    dossier = BASE / "restitution"
    resultat = et.restituer(e, dossier)
    verifier("departement_categorie.csv écrit", resultat["chemin_csv"].exists())
    verifier("rapport.txt écrit", resultat["chemin_rapport"].exists())
    texte = resultat["chemin_rapport"].read_text(encoding="utf-8")
    verifier("rapport mentionne la volumétrie", "Volumétrie chargée" in texte, texte)
    verifier("rapport mentionne les invariants", "Invariants vérifiés" in texte, texte)
    verifier("rapport mentionne le résultat produit", "Résultat produit" in texte, texte)
    verifier("rapport mentionne le total d'actifs (6)", "6" in texte, texte)
    verifier("texte retourné = contenu du fichier", resultat["texte_rapport"] == texte)

print("\n4. entrepôt non ouvert -> échec explicite")
try:
    et.tableau_departement_categorie(Entrepot(neuve("jamais_ouvert.db")))
    verifier("refuse un entrepôt non ouvert", False)
except et.ErreurExportTabulaire:
    verifier("refuse un entrepôt non ouvert", True)

print(f"\n{ok} OK, {ko} ÉCHEC(s)")
sys.exit(1 if ko else 0)
