"""test_export_front.py — Critère de sortie d'OOM-19 (libellés résolus + indicateur)."""
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


def activite(activite_ae_id, num_finess_et, code_nature, ege_id=None,
             etat_objet="A", niveau="ET", rang=1):
    return dict(niveau=niveau, activite_ae_id=activite_ae_id,
                num_finess_ej=EJ["num_finess_ej"], pm_smsse_id=EJ["pm_smsse_id"],
                ege_id=ege_id, num_finess_et=num_finess_et, rang=str(rang),
                code_nature=code_nature, code_type_activite_smsse="SMS1",
                etat_objet=etat_objet, id_lot=LOT["id_lot"])


def capacite(id_capacite, activite_ae_id, nombre, code_unite_mesure="02",
             code_statut_capacite="08", rang=1, niveau="ET"):
    return dict(id_capacite=id_capacite, niveau=niveau, activite_ae_id=activite_ae_id,
                rang=str(rang), nombre=nombre, code_statut_capacite=code_statut_capacite,
                code_unite_mesure=code_unite_mesure, id_lot=LOT["id_lot"])


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

    # G0 : deux activités ET, l'une avec deux capacités, l'autre sans aucune.
    inserer(c, "activite", **activite("A1", "010000020", "ASMR", ege_id="G0"))
    inserer(c, "activite", **activite("A2", "010000020", "EML", ege_id="G0", etat_objet="I"))
    inserer(c, "capacite", **capacite("C1", "A1", "12", code_unite_mesure="02"))
    inserer(c, "capacite", **capacite("C2", "A1", "3", code_unite_mesure="03", rang=2))
    # Une activité de niveau EJ (aucun num_finess_et) : hors périmètre "par
    # établissement", ne doit apparaître pour aucun établissement.
    inserer(c, "activite", **activite("A3", None, "AMM", niveau="EJ"))
    # G1 et G2 : aucune activité — absents du dictionnaire, pas une liste vide.

    lignes = ef.etablissements_bruts(e)
    par_finess = {l["num_finess_et"]: l for l in lignes}

    verifier("3 établissements exportés", len(lignes) == 3, lignes)
    verifier("adresse principale retenue malgré l'ordre d'insertion",
             par_finess["010000020"]["cog_commune"] == "01053",
             par_finess["010000020"])
    verifier("code_categorie exposé brut (183)",
             par_finess["010000020"]["code_categorie"] == "183")
    verifier("libelle_categorie résolu (183 -> IME)",
             par_finess["010000020"]["libelle_categorie"] == "Institut Médico-Educatif (I.M.E.)",
             par_finess["010000020"])
    verifier("code_departement résolu (01053 -> 01)",
             par_finess["010000020"]["code_departement"] == "01",
             par_finess["010000020"])
    verifier("code_departement résolu outre-mer (97105 -> 971)",
             par_finess["010000021"]["code_departement"] == "971",
             par_finess["010000021"])
    verifier("etat_objet A -> libellé Actif",
             par_finess["010000020"]["etat_libelle"] == "Actif")
    verifier("etat_objet I -> libellé Inactif",
             par_finess["010000021"]["etat_libelle"] == "Inactif")
    verifier("établissement sans adresse principale : cog_commune=None, pas d'exception",
             par_finess["010000022"]["cog_commune"] is None)
    verifier("sans adresse principale : code_departement=None, pas de valeur inventée",
             par_finess["010000022"]["code_departement"] is None)
    verifier("code_categorie absent exposé tel quel (None), pas de valeur inventée",
             par_finess["010000022"]["code_categorie"] is None)
    verifier("code_categorie absent -> libelle_categorie=None, pas de valeur inventée",
             par_finess["010000022"]["libelle_categorie"] is None)

    print("\n2. activites_par_etablissement — regroupement ET + capacités (OOM-27)")
    activites = ef.activites_par_etablissement(e)

    verifier("2 établissements avec activités (G0 et pas G1/G2)",
             set(activites) == {"010000020"}, activites)
    verifier("établissement sans activité absent du dictionnaire (pas de liste vide)",
             "010000021" not in activites and "010000022" not in activites, activites)
    activites_g0 = {a["activite_ae_id"]: a for a in activites["010000020"]}
    verifier("2 activités ET pour G0, l'activité EJ (A3) exclue",
             set(activites_g0) == {"A1", "A2"}, activites_g0)
    verifier("code_nature exposé brut (ASMR)",
             activites_g0["A1"]["code_nature"] == "ASMR", activites_g0)
    verifier("libelle_nature toujours None (aucune nomenclature pour ce domaine)",
             activites_g0["A1"]["libelle_nature"] is None, activites_g0)
    verifier("etat_objet I -> libellé Inactif sur l'activité A2",
             activites_g0["A2"]["etat_libelle"] == "Inactif", activites_g0)
    verifier("A1 porte ses 2 capacités, dans l'ordre de rang",
             [ca["nombre"] for ca in activites_g0["A1"]["capacites"]] == ["12", "3"],
             activites_g0["A1"])
    verifier("A2 porte une liste de capacités vide, pas une absence de clé",
             activites_g0["A2"]["capacites"] == [], activites_g0["A2"])

    print("\n3. indicateur_json — mêmes chiffres que l'indicateur OOM-13")
    indicateur = ef.indicateur_json(e)
    verifier("1 seule case peuplée (G0 actif dept 01×IME ; G1 inactif exclu, "
             "G2 actif mais sans département exclu)",
             indicateur == [{"code_departement": "01",
                             "libelle_categorie": "Institut Médico-Educatif (I.M.E.)",
                             "effectif": 1}],
             indicateur)

    print("\n4. exporter — fichiers JSON écrits")
    dossier = BASE / "sortie"
    meta = ef.exporter(e, dossier)

    verifier("etablissements.json écrit", (dossier / "etablissements.json").exists())
    verifier("indicateur.json écrit", (dossier / "indicateur.json").exists())
    verifier("activites.json écrit", (dossier / "activites.json").exists())
    verifier("meta.json écrit", (dossier / "meta.json").exists())
    contenu = json.loads((dossier / "etablissements.json").read_text(encoding="utf-8"))
    verifier("contenu JSON = 3 établissements", len(contenu) == 3, contenu)
    contenu_indicateur = json.loads((dossier / "indicateur.json").read_text(encoding="utf-8"))
    verifier("indicateur.json = même contenu que indicateur_json()",
             contenu_indicateur == indicateur, contenu_indicateur)
    contenu_activites = json.loads((dossier / "activites.json").read_text(encoding="utf-8"))
    verifier("activites.json = même contenu que activites_par_etablissement()",
             contenu_activites == activites, contenu_activites)
    verifier("meta : nombre_etablissements = 3", meta["nombre_etablissements"] == 3, meta)
    verifier("meta : 1 sans adresse principale", meta["sans_adresse_principale"] == 1, meta)
    verifier("meta signale explicitement la résolution active département/libellé",
             meta["departement_resolu"] is True and meta["libelles_categorie_resolus"] is True,
             meta)
    verifier("meta : 0 département non résolu (aucun cog_commune invalide dans le jeu de test)",
             meta["departement_non_resolu"] == 0, meta)
    verifier("meta : 0 catégorie non résolue (aucun code hors référentiel dans le jeu de test)",
             meta["categorie_non_resolue"] == 0, meta)
    verifier("meta : indicateur_lignes = 1", meta["indicateur_lignes"] == 1, meta)
    verifier("meta : etablissements_avec_activites = 1", meta["etablissements_avec_activites"] == 1, meta)
    verifier("meta : activites_total = 2", meta["activites_total"] == 2, meta)
    verifier("meta signale explicitement l'absence de nomenclature pour la nature d'activité",
             meta["libelles_nature_resolus"] is False, meta)

print("\n5. entrepôt non ouvert -> échec explicite")
try:
    ef.etablissements_bruts(Entrepot(neuve("jamais_ouvert.db")))
    verifier("refuse un entrepôt non ouvert (etablissements_bruts)", False)
except ef.ErreurExportFront:
    verifier("refuse un entrepôt non ouvert (etablissements_bruts)", True)

try:
    ef.activites_par_etablissement(Entrepot(neuve("jamais_ouvert2.db")))
    verifier("refuse un entrepôt non ouvert (activites_par_etablissement)", False)
except ef.ErreurExportFront:
    verifier("refuse un entrepôt non ouvert (activites_par_etablissement)", True)

print(f"\n{ok} OK, {ko} ÉCHEC(s)")
sys.exit(1 if ko else 0)
