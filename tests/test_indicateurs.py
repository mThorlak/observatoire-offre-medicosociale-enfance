"""test_indicateurs.py — Critère de sortie d'OOM-13."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import finess_commun as fc
from entrepot import Entrepot
import indicateurs as ind

BASE = Path("/tmp/tests_indicateurs"); BASE.mkdir(exist_ok=True)
ok = ko = 0


def verifier(intitule, condition, detail=""):
    global ok, ko
    if condition: ok += 1; print(f"  OK    {intitule}")
    else: ko += 1; print(f"  ECHEC {intitule} — {detail}")


def neuve(nom="i.db"):
    chemin = BASE / nom
    for suffixe in ("", "-wal", "-shm", "-journal"):
        p = Path(str(chemin) + suffixe)
        if p.exists(): p.unlink()
    return chemin


_TYPES = {t.nom: t for t in fc.TOUS_LES_TYPES}


def inserer(connexion, table, **valeurs):
    """Insertion générique, pilotée par les colonnes déclarées dans le schéma
    (jamais de position codée en dur : voir le principe de schema.py)."""
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


# Codes réels du référentiel (cf. test_nomenclatures.py) : 183 = IME, 186 = ITEP.
IME = "Institut Médico-Educatif (I.M.E.)"
ITEP = "Institut Thérapeutique Éducatif et Pédagogique (I.T.E.P.)"

print("1. indicateur_departement_categorie — comptage actif par département × catégorie")
chemin = neuve()
with Entrepot(chemin) as e:
    e.creer()
    c = e.connexion
    inserer(c, "entete", **LOT)
    inserer(c, "entite_juridique", **EJ)

    # G0, G1 : deux IME actifs dans le même département (01) -> case à 2.
    inserer(c, "etablissement", **etablissement("010000020", "G0", "183", "A", "IME Un"))
    inserer(c, "etablissement", **etablissement("010000021", "G1", "183", "A", "IME Deux"))
    inserer(c, "adresse", **adresse("G0", 1, "03", "01053"))
    inserer(c, "adresse", **adresse("G1", 1, "03", "01001"))

    # G2 : ITEP actif en outre-mer (971) -> case distincte à 1.
    inserer(c, "etablissement", **etablissement("010000022", "G2", "186", "A", "ITEP Un"))
    inserer(c, "adresse", **adresse("G2", 1, "03", "97105"))

    # G3 : IME inactif (etat_objet='I') dans le même département/catégorie que
    # G0/G1 -> ne doit PAS s'ajouter à leur case (définition d'« actif »).
    inserer(c, "etablissement", **etablissement("010000023", "G3", "183", "I", "IME Fermé"))
    inserer(c, "adresse", **adresse("G3", 1, "03", "01001"))

    # G4 : actif, sans adresse principale -> département non résolu.
    inserer(c, "etablissement", **etablissement("010000024", "G4", "183", "A", "IME Sans Adresse"))

    # G5 : actif, code_categorie absent du référentiel -> catégorie non résolue.
    inserer(c, "etablissement", **etablissement("010000025", "G5", "999", "A", "Catégorie Inconnue"))
    inserer(c, "adresse", **adresse("G5", 1, "03", "01001"))

    # G6 : actif, ni adresse principale ni catégorie connue -> les deux compteurs,
    # sans double compte dans exclus().
    inserer(c, "etablissement", **etablissement("010000026", "G6", None, "A", "Rien de résolu"))

    resultat = ind.indicateur_departement_categorie(e)

    verifier("6 établissements actifs comptés (le G3 inactif est exclu)",
             resultat.total_actifs == 6, resultat.total_actifs)
    verifier("département 01 × IME = 2 (G0 + G1, hors G3 inactif)",
             resultat.tableau.get(("01", IME)) == 2, resultat.tableau)
    verifier("département 971 × ITEP = 1 (G2)",
             resultat.tableau.get(("971", ITEP)) == 1, resultat.tableau)
    verifier("aucune case parasite hors les deux attendues",
             set(resultat.tableau) == {("01", IME), ("971", ITEP)}, resultat.tableau)
    verifier("sans_departement = 2 (G4 et G6)", resultat.sans_departement == 2,
             resultat.sans_departement)
    verifier("categorie_inconnue = 2 (G5 et G6)", resultat.categorie_inconnue == 2,
             resultat.categorie_inconnue)
    verifier("sans_departement_et_categorie_inconnue = 1 (G6 seul)",
             resultat.sans_departement_et_categorie_inconnue == 1,
             resultat.sans_departement_et_categorie_inconnue)
    verifier("total vérifiable à la main : tableau + exclusions = total actifs",
             resultat.verifier_total(), resultat.rapport())

    print("\n2. lignes_triees et rapport")
    lignes = resultat.lignes_triees()
    verifier("lignes triées département puis catégorie",
             lignes == [("01", IME, 2), ("971", ITEP, 1)], lignes)
    verifier("rapport() produit un texte non vide", len(resultat.rapport()) > 0)

print("\n3. etat_objet_actif — définition d'« actif »")
verifier("'A' est actif", ind.etat_objet_actif("A") is True)
verifier("'I' n'est pas actif", ind.etat_objet_actif("I") is False)
verifier("None n'est pas actif", ind.etat_objet_actif(None) is False)

print("\n4. entrepôt non ouvert -> échec explicite")
try:
    ind.indicateur_departement_categorie(Entrepot(neuve("jamais_ouvert.db")))
    verifier("refuse un entrepôt non ouvert", False)
except ind.ErreurIndicateurs:
    verifier("refuse un entrepôt non ouvert", True)

print(f"\n{ok} OK, {ko} ÉCHEC(s)")
sys.exit(1 if ko else 0)
