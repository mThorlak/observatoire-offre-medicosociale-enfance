"""test_export_tabulaire.py — Critère de sortie d'OOM-14.

Le calcul de l'indicateur lui-même (établissements actifs par département ×
catégorie, résolution des libellés, définition d'« actif ») est couvert par
`test_indicateurs.py` (OOM-13). Ce fichier vérifie la couche restante :
l'écriture CSV, le rapport de synthèse, et l'enchaînement `restituer`.
"""
from __future__ import annotations
import csv, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import finess_commun as fc
from entrepot import Entrepot
from indicateurs import Resultat
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


print("1. ecrire_csv — sur un Resultat construit à la main")
resultat = Resultat()
resultat.ajouter("01", "Institut Médico-Educatif (I.M.E.)")
resultat.ajouter("01", "Institut Médico-Educatif (I.M.E.)")
resultat.ajouter("75", "Etablissement d'hébergement pour personnes âgées dépendantes")
chemin_csv = BASE / "sortie" / "departement_categorie.csv"
et.ecrire_csv(resultat, chemin_csv)
verifier("CSV écrit", chemin_csv.exists())
with open(chemin_csv, encoding="utf-8", newline="") as f:
    contenu = list(csv.reader(f, delimiter=";"))
verifier("en-tête + 2 lignes de données", len(contenu) == 3, contenu)
verifier("en-tête attendu", contenu[0] ==
         ["code_departement", "libelle_categorie", "effectif"], contenu[0])
verifier("dept 01 × IME = 2", ["01", "Institut Médico-Educatif (I.M.E.)", "2"] in contenu, contenu)


print("\n2. restituer — bout en bout sur un entrepôt réel, indicateur réel (OOM-13)")
chemin = neuve()
with Entrepot(chemin) as e:
    e.creer()
    c = e.connexion
    inserer(c, "entete", **LOT)
    inserer(c, "entite_juridique", **EJ)
    inserer(c, "etablissement", **etablissement("010000001", "G0", "183", "A", "IME Un"))
    inserer(c, "adresse", **adresse("G0", 1, "03", "01053"))
    inserer(c, "etablissement", **etablissement("010000002", "G1", "183", "A", "IME Deux"))
    inserer(c, "adresse", **adresse("G1", 1, "03", "01001"))
    inserer(c, "etablissement", **etablissement("010000003", "G2", "183", "I", "IME Fermé"))
    inserer(c, "adresse", **adresse("G2", 1, "03", "01001"))

    dossier = BASE / "restitution"
    resultat = et.restituer(e, dossier)
    verifier("departement_categorie.csv écrit", resultat["chemin_csv"].exists())
    verifier("rapport.txt écrit", resultat["chemin_rapport"].exists())
    verifier("2 actifs comptés (le fermé exclu)",
             resultat["resultat"].total_actifs == 2, resultat["resultat"].total_actifs)
    verifier("total vérifiable à la main", resultat["resultat"].verifier_total())

    texte = resultat["chemin_rapport"].read_text(encoding="utf-8")
    verifier("rapport mentionne la volumétrie", "Volumétrie chargée" in texte, texte)
    verifier("rapport mentionne les invariants", "Invariants vérifiés" in texte, texte)
    verifier("rapport mentionne le résultat produit", "Résultat produit" in texte, texte)
    verifier("rapport mentionne l'IME (183)",
             "Institut Médico-Educatif (I.M.E.)" in texte, texte)
    verifier("texte retourné = contenu du fichier", resultat["texte_rapport"] == texte)

    with open(resultat["chemin_csv"], encoding="utf-8", newline="") as f:
        lignes_csv = list(csv.reader(f, delimiter=";"))
    verifier("CSV : dept 01 × IME = 2",
             ["01", "Institut Médico-Educatif (I.M.E.)", "2"] in lignes_csv, lignes_csv)

print("\n3. entrepôt non ouvert -> échec explicite")
try:
    et.restituer(Entrepot(neuve("jamais_ouvert.db")), BASE / "jamais")
    verifier("refuse un entrepôt non ouvert", False)
except et.ErreurExportTabulaire:
    verifier("refuse un entrepôt non ouvert", True)

print(f"\n{ok} OK, {ko} ÉCHEC(s)")
sys.exit(1 if ko else 0)
