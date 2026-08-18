"""test_chargement.py — Critère de sortie de F3."""
from __future__ import annotations
import sqlite3, sys
from pathlib import Path

from contrat_source import CONTROLE_MINIMAL, CONTROLE_STRICT
from entrepot import Entrepot, ErreurEntrepot, REGLAGES_CHARGEMENT
from chargement import (ErreurChargement, REFUSER, REMPLACER, charger)
from finess_activites import SourceFinessActivites
from finess_structures import SourceFinessStructures

BASE = Path("/tmp/tests_chargement"); BASE.mkdir(exist_ok=True)
# L'échantillon réduit versionné, cherché à côté du test puis dans echantillon/.
def _echantillon(nom):
    for candidat in (Path(nom), Path("echantillon") / nom,
                     Path(__file__).parent / "echantillon" / nom):
        if candidat.exists():
            return candidat
    raise SystemExit(f"Échantillon introuvable : {nom}")

S = _echantillon("finess-structures-mensuel-202607-echantillon_json.gz")
A = _echantillon("finess-activites-mensuel-202607-echantillon_json.gz")
ok = ko = 0

def verifier(intitule, condition, detail=""):
    global ok, ko
    if condition: ok += 1; print(f"  OK    {intitule}")
    else: ko += 1; print(f"  ECHEC {intitule} — {detail}")

def neuve(nom):
    chemin = BASE / nom
    for s in ("", "-wal", "-shm", "-journal"):
        p = Path(str(chemin) + s)
        if p.exists(): p.unlink()
    e = Entrepot(chemin); e.ouvrir(creer_si_absent=True); e.creer(ecraser=True)
    return e

print("1. Chargement nominal de l'échantillon, contrôle strict")
e = neuve("nominal.db")
rs = charger(e, SourceFinessStructures(), S, controle=CONTROLE_STRICT)
ra = charger(e, SourceFinessActivites(), A, controle=CONTROLE_STRICT)
verifier("les deux fichiers en succès", rs.statut == "SUCCES" and ra.statut == "SUCCES",
         (rs.statut, ra.statut))
verifier("50 085 lignes insérées", rs.total + ra.total == 50085, rs.total + ra.total)
verifier("aucune violation de clé étrangère", not rs.violations and not ra.violations)
comptes = e.compter()
verifier("comptes en base identiques aux lignes émises",
         sum(comptes.values()) == 50085, sum(comptes.values()))
verifier("identifiants de lot distincts", rs.id_lot != ra.id_lot)
verifier("intégrité interne", e.verifier_integrite()["integrite_ok"])

print("2. Idempotence")
try:
    charger(e, SourceFinessStructures(), S)
    verifier("rechargement du même fichier refusé", False)
except ErreurChargement as erreur:
    verifier("rechargement du même fichier refusé", "déjà chargé" in str(erreur))
avant = e.compter()
r = charger(e, SourceFinessStructures(), S, doublon=REMPLACER)
verifier("remplacement signalé comme tel", r.remplacement)
verifier("aucune duplication après remplacement", e.compter() == avant, e.compter())
verifier("identifiant de lot inchangé", r.id_lot == rs.id_lot)
try:
    charger(e, SourceFinessStructures(), S, doublon="fantaisie")
    verifier("politique de doublon inconnue refusée", False)
except ErreurChargement: verifier("politique de doublon inconnue refusée", True)
e.fermer()

print("3. Détection des orphelins après chargement")
e = neuve("orphelins.db")
r = charger(e, SourceFinessActivites(), A, controle=CONTROLE_MINIMAL)
verifier("activités chargées seules → violations détectées", len(r.violations) > 0,
         len(r.violations))
verifier("statut en échec", r.statut == "ECHEC", r.statut)
verifier("lignes tout de même insérées, la violation n'est pas silencieuse",
         r.total > 0 and sum(e.compter().values()) == r.total)
charger(e, SourceFinessStructures(), S, controle=CONTROLE_MINIMAL)
verifier("plus aucune violation une fois les structures chargées",
         not e.verifier_integrite()["violations_cles_etrangeres"])
e.fermer()

print("4. Atomicité")
e = neuve("atomique.db")
class SourceCassee(SourceFinessStructures):
    def produire(self, chemin, contexte):
        for i, (nom, valeurs) in enumerate(super().produire(chemin, contexte)):
            if i == 500:
                raise RuntimeError("panne simulée en cours de flux")
            yield nom, valeurs
try:
    charger(e, SourceCassee(), S)
    verifier("panne en cours de flux → exception propagée", False)
except RuntimeError: verifier("panne en cours de flux → exception propagée", True)
verifier("aucune ligne laissée en base après annulation",
         sum(e.compter().values()) == 0, e.compter())
e.fermer()

print("5. Taille des lots : sans effet sur le résultat")
resultats = []
for lot in (1, 97, 5000):
    e = neuve(f"lot{lot}.db")
    charger(e, SourceFinessStructures(), S, taille_lot=lot, controle=CONTROLE_MINIMAL)
    resultats.append(e.compter()); e.fermer()
verifier("comptes identiques quelle que soit la taille des lots",
         resultats[0] == resultats[1] == resultats[2], resultats)

print("6. Refus sur schéma absent ou divergent")
chemin = BASE / "vide.db"
for s in ("", "-wal", "-journal"):
    p = Path(str(chemin) + s)
    if p.exists(): p.unlink()
e = Entrepot(chemin); e.ouvrir(creer_si_absent=True)
try:
    charger(e, SourceFinessStructures(), S)
    verifier("chargement sans schéma refusé", False)
except ErreurChargement: verifier("chargement sans schéma refusé", True)
e.creer(ecraser=True)
e.connexion.execute("DROP TABLE appareil")
try:
    charger(e, SourceFinessStructures(), S)
    verifier("chargement sur schéma divergent refusé", False)
except ErreurChargement: verifier("chargement sur schéma divergent refusé", True)
e.fermer()

print("7. Les deux niveaux de protection contre le mélange de millésimes")
e = neuve("millesimes.db")
charger(e, SourceFinessStructures(), S, controle=CONTROLE_MINIMAL)
import shutil
autre = BASE / "finess-structures-mensuel-202608-echantillon_json.gz"
shutil.copy(S, autre)
autre.write_bytes(autre.read_bytes() + b"\x00")
try:
    charger(e, SourceFinessStructures(), autre, controle=CONTROLE_MINIMAL,
            doublon=REMPLACER)
    verifier("second millésime refusé avant toute écriture", False)
except ErreurChargement as erreur:
    verifier("second millésime refusé avant toute écriture",
             "mono-millésime" in str(erreur), str(erreur))
verifier("base intacte après le refus", sum(e.compter().values()) == 11199,
         sum(e.compter().values()))
# Sous cette vérification, la clé primaire reste le filet de dernier recours.
with e.reglages_temporaires(REGLAGES_CHARGEMENT):
    existant = list(e.connexion.execute(
        "SELECT * FROM etablissement LIMIT 1"))[0]
    try:
        with e.transaction() as c:
            c.execute("INSERT INTO etablissement VALUES (" + ",".join("?" * 20) + ")",
                      existant)
        verifier("clé primaire : filet de dernier recours toujours actif", False)
    except sqlite3.IntegrityError:
        verifier("clé primaire : filet de dernier recours toujours actif", True)
e.fermer()

print("8. Cohérence du millésime")
import shutil
e = neuve("millesime.db")
autre = BASE / "finess-activites-mensuel-202608-echantillon_json.gz"
shutil.copy(A, autre); autre.write_bytes(autre.read_bytes() + b"\x00")
charger(e, SourceFinessStructures(), S, controle=CONTROLE_MINIMAL)
try:
    charger(e, SourceFinessActivites(), autre, controle=CONTROLE_MINIMAL)
    verifier("millésime divergent refusé", False, "base incohérente constituée")
except ErreurChargement as erreur:
    verifier("millésime divergent refusé", "mono-millésime" in str(erreur), str(erreur))
verifier("rien n'a été écrit du fichier refusé",
         e.compter()["activite"] == 0, e.compter()["activite"])
charger(e, SourceFinessActivites(), A, controle=CONTROLE_MINIMAL)
etat = e.etat()
verifier("l'entrepôt se déclare cohérent", etat["coherent"], etat["motifs"])
verifier("un seul millésime, deux sources",
         etat["millesimes"] == ["202607"]
         and etat["sources"] == ["finess_activites", "finess_structures"], etat)
verifier("le rapport mentionne le millésime", "202607" in e.rapport())

print("9. Unicité de la source")
autre_s = BASE / "finess-structures-mensuel-202607-bis_json.gz"
shutil.copy(S, autre_s); autre_s.write_bytes(autre_s.read_bytes() + b"\x00")
try:
    charger(e, SourceFinessStructures(), autre_s, controle=CONTROLE_MINIMAL)
    verifier("seconde ingestion de la même source refusée", False)
except ErreurChargement as erreur:
    verifier("seconde ingestion de la même source refusée",
             "déjà chargée" in str(erreur), str(erreur))
avant = e.compter()
r = charger(e, SourceFinessStructures(), autre_s, controle=CONTROLE_MINIMAL,
            doublon=REMPLACER)
verifier("remplacement par un autre fichier du même millésime accepté", r.remplacement)
verifier("aucune duplication après ce remplacement", e.compter() == avant, e.compter())
verifier("l'entrepôt reste cohérent", e.etat()["coherent"])
verifier("un seul lot par source", len(e.etat()["lots"]) == 2, e.etat()["lots"])
e.fermer()

print("10. Détection d'une base déjà incohérente")
e = neuve("incoherente.db")
with e.reglages_temporaires(REGLAGES_CHARGEMENT):
    with e.transaction() as c:
        for source, millesime in (("finess_structures", "202607"),
                                  ("finess_activites", "202608")):
            c.execute("INSERT INTO entete VALUES (?,?,?,?,?,?,?,?)",
                      (f"{source}:{millesime}:x", source, millesime, "v1.0.0",
                       None, "f", f"e{millesime}", "1"))
etat = e.etat()
verifier("incohérence constatée par l'entrepôt",
         not etat["coherent"] and "plusieurs millésimes" in etat["motifs"][0], etat)
verifier("le rapport la signale", "INCOHÉRENT" in e.rapport())
try:
    charger(e, SourceFinessStructures(), S, controle=CONTROLE_MINIMAL,
            doublon=REMPLACER)
    verifier("chargement sur base incohérente refusé", False)
except ErreurChargement as erreur:
    verifier("chargement sur base incohérente refusé",
             "incohérent" in str(erreur) or "mono-millésime" in str(erreur), str(erreur))
e.fermer()

print("11. Les contrôles déclarés sont exécutés par le chemin nominal")
e = neuve("controles.db")
r = charger(e, SourceFinessStructures(), S, controle=CONTROLE_MINIMAL)
verifier("les cinq contrôles sont exécutés par charger()", len(r.controles) == 5,
         len(r.controles))
verifier("aucune anomalie sur des données saines", r.anomalies_controles == 0,
         r.controles)
verifier("le rapport les mentionne", "Contrôles après chargement" in r.texte())

# Un rattachement polymorphe orphelin : invisible pour SQL, détecté par les
# contrôles. Sans leur exécution, l'ingestion suivante se conclurait en succès.
with e.reglages_temporaires(REGLAGES_CHARGEMENT):
    with e.transaction() as c:
        c.execute("INSERT INTO contact VALUES (?,?,?,?,?,?,?,?,?)",
                  ("ET", "FANTOME", "010000020", "9", "01", "0474000000",
                   None, None, r.id_lot))
verifier("SQL ne voit rien, la relation n'étant pas déclarable",
         not e.verifier_integrite()["violations_cles_etrangeres"])
r2 = charger(e, SourceFinessActivites(), A, controle=CONTROLE_MINIMAL)
verifier("l'ingestion suivante est mise en échec par les contrôles",
         r2.statut == "ECHEC" and r2.anomalies_controles == 1,
         (r2.statut, r2.anomalies_controles))
verifier("aucune violation de clé étrangère pour autant", not r2.violations)
verifier("le contrôle fautif est nommé dans le rapport",
         "contact_porteur_existe" in r2.texte(), r2.texte()[-300:])
e.fermer()

print(f"\n{ok} tests réussis, {ko} échecs")
sys.exit(1 if ko else 0)
