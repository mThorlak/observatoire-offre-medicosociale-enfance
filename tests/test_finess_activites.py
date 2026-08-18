"""
test_finess_activites.py — Critère de sortie d'E4.

Les documents de test sont construits à partir des jeux de clés déclarés par
nature, jamais écrits à la main : un fichier de test ne peut pas diverger du
contrat sans que le test lui-même le signale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mesure_rss import rss_max_mio
from contrat_source import (CONTROLE_STRICT, InventaireCodes, Lot, RapportIngestion,
                            RegistreAnomalies, parcourir_source)
import finess_commun as fc
import finess_activites as fa

BASE = Path("/tmp/tests_activites")
BASE.mkdir(exist_ok=True)

ok = 0
ko = 0


def verifier(intitule, condition, detail=""):
    global ok, ko
    if condition:
        ok += 1
        print(f"  OK    {intitule}")
    else:
        ko += 1
        print(f"  ECHEC {intitule} — {detail}")


def objet(cles, **valeurs):
    base = {c: None for c in sorted(cles)}
    inconnues = set(valeurs) - set(cles)
    if inconnues:
        raise AssertionError(f"clés hors contrat dans le test : {inconnues}")
    base.update(valeurs)
    return base


# ---------------------------------------------------------------------------
# Fabrique
# ---------------------------------------------------------------------------

VALEURS_BLOC = {
    "activiteSocialeRegulee": "841", "activiteSanitaireDiverseRegulee": "170",
    "activiteEnseignementRegulee": "600", "activiteSanitaireRegulee": "16",
    "activiteAMF": "01", "activiteAMM": "02",
    "modeFonctionnement": "21", "public": "200",
    "formeActivite": "01", "modaliteActivite": "02",
    "modaliteAMM": "03", "mentionAMM": "04", "ptsAMM": "05", "declarationAMM": "06",
    "typeEmlId": "7",
}
VALEURS_SPEC = {
    "ageMinAutorise": "3", "ageMaxAutorise": "20",
    "ageMinInstalle": "3", "ageMaxInstalle": "20",
    "marque": "SIEMENS", "numeroSerie": "SN-1", "etatArhgos": "01",
    "numDecision": "D-1", "resultatVisite": None,
    "dateLimDep": "2030-01-01", "dateLimVisiteConformite": "2030-01-01",
    "dateVisite": "2020-01-01",
}


def specifiques(code_nature, ae_id, appareils=0):
    decl = fa.NATURES[code_nature]
    valeurs = {"activiteAeId": ae_id}
    for cle in decl.cles_specifiques:
        if cle == decl.bloc:
            valeurs[cle] = objet(decl.cles_bloc,
                                 **{k: v for k, v in VALEURS_BLOC.items()
                                    if k in decl.cles_bloc})
        elif cle == decl.identifiant:
            valeurs[cle] = f"ID-{code_nature}"
        elif cle == "appareil":
            valeurs[cle] = [objet(fa.CLES_APPAREIL, typeAppareilAMM="01",
                                  nombreAppareilAMM="2", statutAppareilAMM="A")
                            for _ in range(appareils)]
        elif cle in VALEURS_SPEC:
            valeurs[cle] = VALEURS_SPEC[cle]
    return objet(decl.cles_specifiques, **valeurs)


def capacite(ae_id, statut="09", n="24"):
    return objet(fa.CLES_CAPACITE, idCapacite=f"C-{ae_id}-{statut}", activiteAeId=ae_id,
                 nombre=n, statutCapacite=statut, uniteMesureCapacite="02",
                 habilitation="1", genre="2")


def zone(ae_id, communes=2):
    return objet(fa.CLES_ZONE, zoneInterventionAutoriseeId=f"Z-{ae_id}",
                 activiteAeId=ae_id, libelleZI="Territoire test",
                 communeZI=[objet(fa.CLES_COMMUNE_ZI, commune=f"0100{i}")
                            for i in range(communes)])


def evenement(vid):
    return objet(fc.CLES_EVENEMENT, evenementId=vid, codeEvenement="CRE",
                 dateEvenement="2020-01-01", dateEnregistrement="2020-01-02T10:00:00Z",
                 etatObjet1="A", typeObjet1="AE", identifiantObjet1="1",
                 systemeMaitre="FINESS")


def engagement(eid):
    return objet(fc.CLES_ENGAGEMENT, engagementId=eid, typeEngagement="ARR",
                 sousTypeEngagement="AUT", dateEffetEngagement="2020-01-01",
                 autoriteRegulationEngagement=[objet(fc.CLES_AUTORITE,
                                                     autoriteRegulationid="ARS-01")])


def activite(ae_id, code_nature, niveau, ege_id=None, capacites=2, avec_zone=False,
             appareils=0, evenements=1, engagements=0):
    cles_gen = fa.CLES_GENERIQUES_EJ if niveau == "EJ" else fa.CLES_GENERIQUES_ET
    gen = {"activiteAeId": ae_id, "typeActiviteSMSSE": "70237", "etatObjet": "A",
           "egeId": ege_id, "numAutorisationArhgos": "ARH-1",
           "dateDebutActiviteAutorisee": "2010-01-01"}
    if niveau == "ET":
        gen["identifiantAutorisation"] = "AUT-1"
    return objet(fa.CLES_ACTIVITE,
                 caracteristiquesGeneriques=objet(cles_gen, **gen),
                 nature=objet(fa.CLES_NATURE, codeNature=code_nature,
                              caracteristiquesSpecifiques=specifiques(
                                  code_nature, ae_id, appareils)),
                 capacite=[capacite(ae_id, s) for s in ("08", "09")[:capacites]],
                 zoneIntervention=zone(ae_id) if avec_zone else None,
                 evenement=[evenement(f"V-{ae_id}-{i}") for i in range(evenements)],
                 engagement=[engagement(f"E-{ae_id}-{i}") for i in range(engagements)])


def document(natures=("ASMR", "AMM"), nb_pmej=1, nb_ege=1):
    pmej = []
    for p in range(nb_pmej):
        autorisees = [activite(f"AE{p}{i}", n, "EJ", avec_zone=(n == "ASMR"),
                               engagements=1 if i == 0 else 0)
                      for i, n in enumerate(natures)]
        eges = []
        for g in range(nb_ege):
            exercees = [activite(f"AE{p}{g}{i}", n, "ET", ege_id=f"G{p}{g}",
                                 appareils=8 if n == "AMM" else 0)
                        for i, n in enumerate(natures)]
            eges.append(objet(fa.CLES_EGE, egeId=f"G{p}{g}",
                              numFinessEge=f"01000{p}{g}00", activitesExercees=exercees))
        pmej.append(objet(fa.CLES_PMEJ, numFiness=f"01000840{p}", pmSmsseId=f"{100 + p}",
                          activitesAutorisees=autorisees, ege=eges))
    return {"schemaVersion": "v1.0.0", "generatedAt": "2026-08-01T02:14:23Z", "pmej": pmej}


def ecrire(nom, doc):
    chemin = BASE / nom
    chemin.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return chemin


def executer(chemin, accumuler=True, controle=CONTROLE_STRICT):
    rap = RapportIngestion(Lot("", "", "", "", 0), RegistreAnomalies(),
                           InventaireCodes(), controle)
    flux = parcourir_source(fa.SourceFinessActivites(), chemin, controle=controle,
                            rapport=rap)
    if not accumuler:
        for _ in flux:
            pass
        return [], rap
    return list(flux), rap


# ---------------------------------------------------------------------------

print("1. Cas nominal, contrôle strict")
chemin = ecrire("nominal-mensuel-202607.json", document())
lignes, rap = executer(chemin)
verifier("statut SUCCES", rap.statut == "SUCCES", rap.registre.par_code())
verifier("aucune anomalie", rap.registre.total() == 0, rap.registre.par_code())
verifier("activités aux deux niveaux", rap.emis["activite"] == 4, rap.emis)
verifier("capacités aux deux niveaux", rap.emis["capacite"] == 8, rap.emis)
verifier("appareils au niveau ET seulement", rap.emis["appareil"] == 8, rap.emis)
verifier("zone d'intervention au niveau EJ seulement",
         rap.emis["zone_intervention"] == 1 and rap.emis["zone_intervention_commune"] == 2,
         rap.emis)
verifier("engagement et autorité rattachés", rap.emis["engagement"] == 1
         and rap.emis["engagement_autorite"] == 1, rap.emis)
verifier("millésime lu dans le nom du fichier", rap.lot.millesime == "202607")

print("2. Fentes uniques et rattachements")
par_type = {}
for nom, ligne in lignes:
    par_type.setdefault(nom, []).append(ligne)
pos = fc.TYPE_ACTIVITE.position
asmr = [a for a in par_type["activite"] if a[pos("code_nature")] == "ASMR"]
amm = [a for a in par_type["activite"] if a[pos("code_nature")] == "AMM"]
verifier("triplet médico-social dans la fente unique",
         asmr[0][pos("code_activite_regulee")] == "841"
         and asmr[0][pos("code_mode_fonctionnement")] == "21"
         and asmr[0][pos("code_public")] == "200",
         (asmr[0][pos("code_activite_regulee")], asmr[0][pos("code_public")]))
verifier("code AMM dans la même fente, désambiguïsé par code_nature",
         amm[0][pos("code_activite_regulee")] == "02"
         and amm[0][pos("code_modalite_amm")] == "03")
verifier("identifiant de nature dans la fente unique",
         asmr[0][pos("identifiant_nature")] == "ID-ASMR"
         and amm[0][pos("identifiant_nature")] == "ID-AMM")
verifier("bornes d'âge sur ASMR uniquement",
         asmr[0][pos("age_min_autorise")] == "3" and amm[0][pos("age_min_autorise")] is None)
verifier("niveau EJ sans identifiant d'autorisation, niveau ET avec",
         [a for a in asmr if a[pos("niveau")] == "EJ"][0][pos("identifiant_autorisation")] is None
         and [a for a in asmr if a[pos("niveau")] == "ET"][0][pos("identifiant_autorisation")] == "AUT-1")
verifier("établissement rattaché au niveau ET seulement",
         [a for a in asmr if a[pos("niveau")] == "ET"][0][pos("num_finess_et")] == "010000000"
         and [a for a in asmr if a[pos("niveau")] == "EJ"][0][pos("num_finess_et")] is None)
pos_c = fc.TYPE_CAPACITE.position
verifier("capacités portent leur niveau",
         {c[pos_c("niveau")] for c in par_type["capacite"]} == {"EJ", "ET"})
verifier("évènements d'activité rattachés au bon type de porteur",
         {v[fc.TYPE_EVENEMENT.position("type_porteur")] for v in par_type["evenement"]}
         == {fc.PORTEUR_ACTIVITE_EJ, fc.PORTEUR_ACTIVITE_ET})

print("3. Contrat par nature")
for nature in fa.NATURES:
    _, r = executer(ecrire(f"nature-{nature}-202607.json",
                           document(natures=(nature,))))
    verifier(f"nature {nature} ingérée sans anomalie",
             r.statut == "SUCCES" and r.emis["activite"] == 2,
             (r.statut, r.registre.par_code()))

print("4. Détection des dérives de schéma")
cas = [
    ("cle_spec_ajoutee", "cle_json_non_declaree",
     lambda d: d["pmej"][0]["activitesAutorisees"][0]["nature"]
     ["caracteristiquesSpecifiques"].update({"nouveauChamp": "x"})),
    ("cle_spec_etrangere", "cle_json_non_declaree",
     lambda d: d["pmej"][0]["activitesAutorisees"][0]["nature"]
     ["caracteristiquesSpecifiques"].update({"typeActiviteAMM": {}})),
    ("cle_bloc_ajoutee", "cle_json_non_declaree",
     lambda d: d["pmej"][0]["activitesAutorisees"][0]["nature"]
     ["caracteristiquesSpecifiques"]["typeActiviteAMSR"].update({"nouveau": "x"})),
    ("cle_generique_absente", "cle_json_absente",
     lambda d: d["pmej"][0]["activitesAutorisees"][0]["caracteristiquesGeneriques"]
     .pop("numAutorisationArhgos")),
    ("cle_capacite_ajoutee", "cle_json_non_declaree",
     lambda d: d["pmej"][0]["activitesAutorisees"][0]["capacite"][0].update({"x": "y"})),
    ("cle_zone_ajoutee", "cle_json_non_declaree",
     lambda d: d["pmej"][0]["activitesAutorisees"][0]["zoneIntervention"].update({"x": "y"})),
]
for nom_cas, code_attendu, muter in cas:
    doc = document()
    muter(doc)
    _, r = executer(ecrire(f"{nom_cas}-202607.json", doc))
    verifier(f"{nom_cas} → {code_attendu} bloquant",
             code_attendu in r.registre.par_code() and r.statut == "ECHEC",
             r.registre.par_code())

doc = document()
doc["pmej"][0]["activitesAutorisees"][0]["nature"]["codeNature"] = "XXXX"
_, r = executer(ecrire("nature-inconnue-202607.json", doc))
verifier("nature inconnue → bloquant",
         "nature_non_declaree" in r.registre.par_code() and r.statut == "ECHEC",
         r.registre.par_code())

doc = document()
doc["pmej"][0]["activitesAutorisees"][0]["nature"]["caracteristiquesSpecifiques"]["typeActiviteAMSR"] = None
_, r = executer(ecrire("bloc-nul-202607.json", doc))
verifier("bloc typé nul → bloquant",
         "bloc_absent" in r.registre.par_code() and r.statut == "ECHEC",
         r.registre.par_code())

doc = document()
doc["pmej"][0]["ege"][0]["activitesExercees"][0]["caracteristiquesGeneriques"]["egeId"] = "AUTRE"
_, r = executer(ecrire("rattachement-202607.json", doc))
verifier("egeId discordant avec l'établissement englobant → bloquant",
         "rattachement_incoherent" in r.registre.par_code() and r.statut == "ECHEC",
         r.registre.par_code())

doc = document()
doc["nouveauTableau"] = [{"a": "b"}]
_, r = executer(ecrire("tableau-racine-202607.json", doc))
verifier("tableau racine inconnu → bloquant",
         "tableau_racine_non_declare" in r.registre.par_code() and r.statut == "ECHEC",
         r.registre.par_code())

print("5. Cas limites structurels")
doc = document()
doc["pmej"][0]["ege"] = []
_, r = executer(ecrire("sans-ege-202607.json", doc))
verifier("entité juridique sans établissement acceptée",
         r.statut == "SUCCES" and r.emis["activite"] == 2, (r.statut, r.emis))
doc = document()
doc["pmej"][0]["activitesAutorisees"] = []
doc["pmej"][0]["ege"][0]["activitesExercees"] = []
_, r = executer(ecrire("sans-activite-202607.json", doc))
verifier("entité juridique sans aucune activité → aucune_donnee bloquant",
         "aucune_donnee" in r.registre.par_code(), r.registre.par_code())

print("6. Déterminisme et mémoire")
chemin = ecrire("nominal-mensuel-202607.json", document())
a, ra = executer(chemin)
b, rb = executer(chemin)
verifier("identifiant de lot déterministe", ra.lot.identifiant == rb.lot.identifiant)
verifier("séquence de lignes identique d'une exécution à l'autre", a == b)

gros = ecrire("volumineux-202607.json", document(natures=("ASMR", "ASOCR", "AMM", "ASDR"),
                                                 nb_pmej=400, nb_ege=3))
avant = rss_max_mio()
_, r_gros = executer(gros, accumuler=False)
apres = rss_max_mio()
verifier("gros document ingéré sans anomalie",
         r_gros.statut == "SUCCES" and r_gros.emis["activite"] == 400 * (4 + 3 * 4),
         (r_gros.statut, r_gros.emis.get("activite")))
verifier(f"RSS stable ({avant:.0f} → {apres:.0f} Mio)", apres - avant < 20,
         f"croissance {apres - avant:.1f} Mio")

print(f"\n{ok} tests réussis, {ko} échecs")
sys.exit(1 if ko else 0)
