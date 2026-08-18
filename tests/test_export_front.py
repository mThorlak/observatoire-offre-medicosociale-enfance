"""test_export_front.py — Critère de sortie d'OOM-19 (portée codes bruts)."""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import finess_commun as fc
from entrepot import Entrepot
import export_front as ef

BASE = Path("/tmp/tests_export_front"); BASE.mkdir(exist_ok=True)
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


print("1. etablissements_bruts — jointure adresse principale")
chemin = neuve()
with Entrepot(chemin) as e:
    e.creer()
    c = e.connexion
    inserer(c, "entete", **LOT)
    inserer(c, "entite_juridique", **EJ)
    inserer(c, "etablissement", **etablissement("010000020", "G0", "183", "A", "IME Un"))
    inserer(c, "etablissement", **etablissement("010000021", "G1", "500", "I", "EHPAD Fermé"))
    inserer(c, "etablissement", **etablissement("010000022", "G2", None, "A", "Sans catégorie"))
    # deux adresses pour G0 : une secondaire, une principale (rang 2) — la
    # principale doit être retenue malgré l'ordre.
    inserer(c, "adresse", **adresse("G0", 1, "04", "01001"))
    inserer(c, "adresse", **adresse("G0", 2, "03", "01053"))
    inserer(c, "adresse", **adresse("G1", 1, "03", "97105"))
    # G2 : aucune adresse principale — doit rester None, pas planté.

    lignes = ef.etablissements_bruts(e)
    par_finess = {l["num_finess_et"]: l for l in lignes}

    verifier("3 établissements exportés", len(lignes) == 3, lignes)
    verifier("adresse principale retenue malgré l'ordre d'insertion",
             par_finess["010000020"]["cog_commune"] == "01053",
             par_finess["010000020"])
    verifier("code_categorie exposé brut (183, pas de libellé)",
             par_finess["010000020"]["code_categorie"] == "183")
    verifier("etat_objet A -> libellé Actif",
             par_finess["010000020"]["etat_libelle"] == "Actif")
    verifier("etat_objet I -> libellé Inactif",
             par_finess["010000021"]["etat_libelle"] == "Inactif")
    verifier("établissement sans adresse principale : cog_commune=None, pas d'exception",
             par_finess["010000022"]["cog_commune"] is None)
    verifier("code_categorie absent exposé tel quel (None), pas de valeur inventée",
             par_finess["010000022"]["code_categorie"] is None)

    print("\n2. exporter — fichiers JSON écrits")
    dossier = BASE / "sortie"
    meta = ef.exporter(e, dossier)

    verifier("etablissements.json écrit", (dossier / "etablissements.json").exists())
    verifier("meta.json écrit", (dossier / "meta.json").exists())
    contenu = json.loads((dossier / "etablissements.json").read_text(encoding="utf-8"))
    verifier("contenu JSON = 3 établissements", len(contenu) == 3, contenu)
    verifier("meta : nombre_etablissements = 3", meta["nombre_etablissements"] == 3, meta)
    verifier("meta : 1 sans adresse principale", meta["sans_adresse_principale"] == 1, meta)
    verifier("meta signale explicitement l'absence de résolution département/libellé",
             meta["departement_resolu"] is False and meta["libelles_categorie_resolus"] is False,
             meta)

print("\n3. entrepôt non ouvert -> échec explicite")
try:
    ef.etablissements_bruts(Entrepot(neuve("jamais_ouvert.db")))
    verifier("refuse un entrepôt non ouvert", False)
except ef.ErreurExportFront:
    verifier("refuse un entrepôt non ouvert", True)

print(f"\n{ok} OK, {ko} ÉCHEC(s)")
sys.exit(1 if ko else 0)
