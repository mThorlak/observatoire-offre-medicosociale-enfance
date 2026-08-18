"""
test_cli.py — Orchestration, étape E6.

Éprouve les quatre commandes de bout en bout sur des documents synthétiques,
y compris les codes de retour, qui sont le seul signal exploitable par un
enchaînement automatisé.
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import cli
import finess_commun as fc
import finess_structures as fs
import finess_activites as fa

BASE = Path("/tmp/tests_cli")
BASE.mkdir(exist_ok=True)
ok = ko = 0


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
    assert not set(valeurs) - set(cles), set(valeurs) - set(cles)
    base.update(valeurs)
    return base


def doc_structures(nb=2, ege_porteuse=None):
    pmej = []
    for p in range(nb):
        adresse = objet(fc.CLES_ADRESSE, usageAdresse="03", typeVoie="RUE",
                        libelleVoie="DES LILAS", cogCommune="01001", codePostal="01000")
        ege = objet(fs.CLES_EGE,
                    informationsGeneralesEGE=objet(
                        fs.CLES_INFOS_EGE, egeId=f"G{p}", numFinessEge=f"01000002{p}",
                        nomEgeCourt="IME", nomEgeLong="IME LONG", dateOuverture="1990-01-01"),
                    categorieentiteGeographiqueExercice="183", modefixationtarifaire="01",
                    typeBudget=["01"], adresse=[adresse], contact=[], engagement=[],
                    evenement=[],
                    roleEge=[objet(fs.CLES_ROLE_EGE,
                                   idEgePorteuse=ege_porteuse or f"G{p}",
                                   idEgeNonPorteuse=f"G{p}", roleRelationEge="B")],
                    etatObjet="A", dateDerniereMaj="2026-05-01T00:00:00Z")
        pmej.append(objet(fs.CLES_PMEJ,
                          informationsGeneralesPMEJ=objet(
                              fs.CLES_INFOS_PMEJ, pmSmsseId=f"{100 + p}",
                              numFinessPm=f"01000840{p}", denominationPm="ASSO",
                              denominationLonguePmSmsse="ASSO LONGUE", statutJuridique="60",
                              typePersonneMorale="1", dateCreation="1980-01-01"),
                          adresse=[adresse], contact=[], engagement=[], evenement=[],
                          ege=[ege], etatObjet="A",
                          dateDerniereMaj="2026-05-01T00:00:00Z"))
    return {"schemaVersion": "v1.0.0", "generatedAt": "2026-08-01T02:06:22Z",
            "gco": [], "gcc": [], "pmej": pmej}


def doc_activites(nb=2, ej_inconnue=False):
    pmej = []
    for p in range(nb):
        def activite(ae, niveau, ege_id=None):
            gen = objet(fa.CLES_GENERIQUES_EJ if niveau == "EJ" else fa.CLES_GENERIQUES_ET,
                        activiteAeId=ae, typeActiviteSMSSE="70237", etatObjet="A",
                        egeId=ege_id)
            spec = objet(fa.NATURES["ASMR"].cles_specifiques, activiteAeId=ae,
                         aaSocialeReguleeId=f"S{ae}",
                         typeActiviteAMSR=objet(fa.NATURES["ASMR"].cles_bloc,
                                                activiteSocialeRegulee="841",
                                                modeFonctionnement="21", public="200"))
            return objet(fa.CLES_ACTIVITE, caracteristiquesGeneriques=gen,
                         nature=objet(fa.CLES_NATURE, codeNature="ASMR",
                                      caracteristiquesSpecifiques=spec),
                         capacite=[objet(fa.CLES_CAPACITE, idCapacite=f"C{ae}",
                                         activiteAeId=ae, nombre="24",
                                         statutCapacite="09", uniteMesureCapacite="02")],
                         zoneIntervention=None, evenement=[], engagement=[])
        num = "999999999" if (ej_inconnue and p == 0) else f"01000840{p}"
        ege = objet(fa.CLES_EGE, egeId=f"G{p}", numFinessEge=f"01000002{p}",
                    activitesExercees=[activite(f"AE{p}T", "ET", f"G{p}")])
        pmej.append(objet(fa.CLES_PMEJ, numFiness=num, pmSmsseId=f"{100 + p}",
                          activitesAutorisees=[activite(f"AE{p}J", "EJ")], ege=[ege]))
    return {"schemaVersion": "v1.0.0", "generatedAt": "2026-08-01T02:14:23Z", "pmej": pmej}


def ecrire(nom, doc):
    chemin = BASE / nom
    chemin.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return chemin


def lancer(*arguments):
    sortie = io.StringIO()
    with redirect_stdout(sortie):
        retour = cli.main([str(a) for a in arguments])
    return retour, sortie.getvalue()


CS = ecrire("finess-structures-mensuel-202607.json", doc_structures())
CA = ecrire("finess-activites-mensuel-202607.json", doc_activites())

print("1. inspecter")
retour, texte = lancer("inspecter", CS)
verifier("code de retour nul", retour == 0, texte[-300:])
verifier("volumétrie affichée", "etablissement" in texte and "entite_juridique" in texte)
verifier("connecteur déduit du nom du fichier", "finess_structures" in texte)
retour, texte = lancer("inspecter", CA, "--controle", "strict", "--echantillon")
verifier("échantillon affiché", "[activite]" in texte and "code_public" in texte, texte[:200])
retour, texte = lancer("inspecter", CS, "--source", "structures")
verifier("connecteur forcé accepté", retour == 0)

ambigu = ecrire("fichier-sans-indice.json", doc_structures())
try:
    lancer("inspecter", ambigu)
    verifier("nom de fichier ambigu → refus explicite, jamais de supposition", False)
except SystemExit:
    verifier("nom de fichier ambigu → refus explicite, jamais de supposition", True)

print("2. inventaire")
retour, texte = lancer("inventaire", CS, CA, "--sortie", BASE / "registre.csv")
verifier("code de retour nul", retour == 0, texte[-400:])
verifier("registre écrit", (BASE / "registre.csv").exists())
verifier("statistiques par domaine affichées", "OCCURRENCES" in texte and "HAPAX" in texte)

print("3. integrite")
retour, texte = lancer("integrite", CS, CA)
verifier("code de retour nul sur données cohérentes", retour == 0, texte[-400:])
verifier("les treize relations sont évaluées",
         all(r.nom in texte for r in fc.RELATIONS_PIVOT),
         [r.nom for r in fc.RELATIONS_PIVOT if r.nom not in texte])
verifier("aucune référence orpheline", "Références orphelines : 0" in texte)
verifier("empreinte des index rapportée", "Index différés" in texte)

CA_ORPH = ecrire("finess-activites-mensuel-202607-orph.json", doc_activites(ej_inconnue=True))
retour, texte = lancer("integrite", CS, CA_ORPH)
verifier("entité juridique inconnue → orpheline et code de retour 1",
         retour == 1 and "reference_orpheline_differee" in texte, texte[-500:])

CS_ORPH = ecrire("finess-structures-mensuel-202607-orph.json",
                 doc_structures(ege_porteuse="GX"))
retour, texte = lancer("integrite", CS_ORPH, CA)
verifier("établissement porteur inconnu → orpheline et code de retour 1",
         retour == 1 and "Références orphelines : 2" in texte, texte[-500:])

print("4. tout")
retour, texte = lancer("tout", CS, CA, "--sortie", BASE / "registre2.csv")
verifier("les trois étapes enchaînées", retour == 0
         and texte.count("##########") == 8, texte.count("##########"))
retour, texte = lancer("tout", CS, CA_ORPH, "--sortie", BASE / "registre3.csv")
verifier("une seule étape en échec suffit à faire échouer l'ensemble", retour == 1)

print("5. charger")
BASE_ENTREPOT = BASE / "entrepot_charger.sqlite"
for suffixe in ("", "-wal", "-shm", "-journal"):
    p = Path(str(BASE_ENTREPOT) + suffixe)
    if p.exists():
        p.unlink()

retour, texte = lancer("charger", BASE_ENTREPOT, CS, "--creer")
verifier("code de retour nul, structures seules", retour == 0, texte[-500:])
verifier("établissements chargés", "etablissement" in texte)
verifier("rapport final de l'entrepôt affiché", "Schéma     : conforme" in texte, texte[-500:])

retour, texte = lancer("charger", BASE_ENTREPOT, CS)
verifier("fichier déjà chargé (même empreinte) → refus, code de retour 1",
         retour == 1 and "ÉCHEC" in texte, texte[-300:])

retour, texte = lancer("charger", BASE_ENTREPOT, CS, "--remplacer")
verifier("remplacement explicite accepté", retour == 0, texte[-300:])

BASE_ENTREPOT_2 = BASE / "entrepot_charger_activites.sqlite"
for suffixe in ("", "-wal", "-shm", "-journal"):
    p = Path(str(BASE_ENTREPOT_2) + suffixe)
    if p.exists():
        p.unlink()

retour, texte = lancer("charger", BASE_ENTREPOT_2, CS, "--activites", CA, "--creer")
verifier("structures et activités chargées ensemble",
         retour == 0 and "activite" in texte, texte[-500:])

print(f"\n{ok} tests réussis, {ko} échecs")
sys.exit(1 if ko else 0)
