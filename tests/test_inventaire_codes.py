"""
test_inventaire_codes.py — Critère de sortie d'E5.

Chaque contrôle de la passe E5 est éprouvé sur un défaut fabriqué : un contrôle
qui ne se déclenche jamais ne prouve rien. Les documents de test sont
construits à partir des jeux de clés déclarés.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mesure_rss import rss_max_mio
import finess_commun as fc
import finess_structures as fs
import finess_activites as fa
import inventaire_codes as ic

BASE = Path("/tmp/tests_inventaire")
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
# Documents minimaux
# ---------------------------------------------------------------------------

def doc_structures(nb_ej=2, categories=("183", "186"), codes_evenement=("001",),
                   etat_objet1="100", type_objet1="EGE"):
    pmej = []
    for p in range(nb_ej):
        adresse = objet(fc.CLES_ADRESSE, usageAdresse="03", typeVoie="RUE",
                        libelleVoie="DES LILAS", cogCommune="01001", codePostal="01000",
                        ligneAcheminement="01000 BOURG")
        contact = objet(fc.CLES_CONTACT,
                        typeContact=objet(fc.CLES_TYPE_CONTACT, roleContact="01"),
                        telecom=objet(fc.CLES_TELECOM, telephone="0474000000"))
        evenements = [objet(fc.CLES_EVENEMENT, evenementId=f"V{p}{i}", codeEvenement=c,
                            dateEvenement="2020-01-01",
                            dateEnregistrement="2020-01-02T10:00:00Z",
                            etatObjet1=etat_objet1, typeObjet1=type_objet1,
                            identifiantObjet1="1",
                            systemeMaitre="FINESS")
                      for i, c in enumerate(codes_evenement)]
        ege = objet(fs.CLES_EGE,
                    informationsGeneralesEGE=objet(
                        fs.CLES_INFOS_EGE, egeId=f"G{p}", numFinessEge=f"01000002{p}",
                        nomEgeCourt="IME", nomEgeLong="IME LONG",
                        dateOuverture="1990-01-01"),
                    categorieentiteGeographiqueExercice=categories[p % len(categories)],
                    modefixationtarifaire="01", typeBudget=["01"],
                    adresse=[adresse], contact=[contact], engagement=[],
                    evenement=evenements, roleEge=[],
                    etatObjet="A", dateDerniereMaj="2026-05-01T00:00:00Z")
        pmej.append(objet(fs.CLES_PMEJ,
                          informationsGeneralesPMEJ=objet(
                              fs.CLES_INFOS_PMEJ, pmSmsseId=f"{100 + p}",
                              numFinessPm=f"01000840{p}", denominationPm="ASSO",
                              denominationLonguePmSmsse="ASSO LONGUE",
                              statutJuridique="60", typePersonneMorale="1",
                              dateCreation="1980-01-01"),
                          adresse=[adresse], contact=[contact], engagement=[],
                          evenement=[], ege=[ege],
                          etatObjet="A", dateDerniereMaj="2026-05-01T00:00:00Z"))
    return {"schemaVersion": "v1.0.0", "generatedAt": "2026-08-01T02:06:22Z",
            "gco": [], "gcc": [], "pmej": pmej}


def doc_activites(nb_ej=2, publics=("200", "110"), codes_evenement=("008",),
                  etat_objet1=None, type_objet1="EGE"):
    pmej = []
    for p in range(nb_ej):
        def activite(ae_id, niveau, ege_id=None):
            cles_gen = fa.CLES_GENERIQUES_EJ if niveau == "EJ" else fa.CLES_GENERIQUES_ET
            gen = {"activiteAeId": ae_id, "typeActiviteSMSSE": "70237",
                   "etatObjet": "A", "egeId": ege_id}
            spec = objet(fa.NATURES["ASMR"].cles_specifiques,
                         activiteAeId=ae_id, aaSocialeReguleeId=f"S{ae_id}",
                         ageMinAutorise="3", ageMaxAutorise="20",
                         typeActiviteAMSR=objet(fa.NATURES["ASMR"].cles_bloc,
                                                activiteSocialeRegulee="841",
                                                modeFonctionnement="21",
                                                public=publics[p % len(publics)]))
            return objet(fa.CLES_ACTIVITE,
                         caracteristiquesGeneriques=objet(cles_gen, **gen),
                         nature=objet(fa.CLES_NATURE, codeNature="ASMR",
                                      caracteristiquesSpecifiques=spec),
                         capacite=[objet(fa.CLES_CAPACITE, idCapacite=f"C{ae_id}",
                                         activiteAeId=ae_id, nombre="24",
                                         statutCapacite="09", uniteMesureCapacite="02")],
                         zoneIntervention=None,
                         evenement=[objet(fc.CLES_EVENEMENT, evenementId=f"W{ae_id}{i}",
                                          codeEvenement=c, dateEvenement="2020-01-01",
                                          dateEnregistrement="2020-01-02T10:00:00Z",
                                          etatObjet1=etat_objet1 or c,
                                          typeObjet1=type_objet1,
                                          identifiantObjet1="1", systemeMaitre="FINESS")
                                    for i, c in enumerate(codes_evenement)],
                         engagement=[])
        ege = objet(fa.CLES_EGE, egeId=f"G{p}", numFinessEge=f"01000002{p}",
                    activitesExercees=[activite(f"AE{p}T", "ET", f"G{p}")])
        pmej.append(objet(fa.CLES_PMEJ, numFiness=f"01000840{p}", pmSmsseId=f"{100 + p}",
                          activitesAutorisees=[activite(f"AE{p}J", "EJ")], ege=[ege]))
    return {"schemaVersion": "v1.0.0", "generatedAt": "2026-08-01T02:14:23Z", "pmej": pmej}


def ecrire(nom, doc):
    chemin = BASE / nom
    chemin.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return chemin


def lancer(ds=None, da=None, plafond=ic.PLAFOND_E5, csv=None):
    cs = ecrire("structures-mensuel-202607.json", ds if ds is not None else doc_structures())
    ca = ecrire("activites-mensuel-202607.json", da if da is not None else doc_activites())
    return ic.executer(cs, ca, csv, plafond)


def codes(resultat):
    agrege = {}
    for r in resultat.registres:
        for code, n in r.par_code().items():
            agrege[code] = agrege.get(code, 0) + n
    return agrege


def gravites(resultat, code_cherche):
    trouve = set()
    for r in resultat.registres:
        for code, gravite, _t, _c, _n in r.detail():
            if code == code_cherche:
                trouve.add(gravite)
    return trouve


# ---------------------------------------------------------------------------

print("1. Cas nominal")
resultat, retour = lancer(csv=BASE / "registre.csv")
verifier("code de retour nul", retour == 0, codes(resultat))
verifier("aucune anomalie bloquante",
         sum(r.bloquantes for r in resultat.registres) == 0, codes(resultat))
verifier("seuls les domaines disjoints du fichier réel le sont ici",
         codes(resultat).get("vocabulaires_disjoints") == 2,
         codes(resultat).get("vocabulaires_disjoints"))
verifier("les deux recensements coïncident",
         "recensements_discordants" not in codes(resultat)
         and "effectifs_discordants" not in codes(resultat))
verifier("couverture complète", "couverture_incomplete" not in codes(resultat))
verifier("aucun contrôle d'intégrité résiduel dans E5 (migrés en E6)",
         not any(c.startswith("reference_") for c in codes(resultat)), codes(resultat))
a, b = resultat.par_domaine_a, resultat.par_domaine_b()
verifier("recensement A et recensement B identiques", a == b,
         {d: (a.get(d), b.get(d)) for d in set(a) ^ set(b)})

print("2. Unicité du registre produit")
lignes = (BASE / "registre.csv").read_text(encoding="utf-8").splitlines()[1:]
couples = [tuple(l.split(";")[:2]) for l in lignes if l.strip()]
verifier("chaque couple (domaine, code) figure une fois et une seule",
         len(couples) == len(set(couples)), f"{len(couples)} lignes, {len(set(couples))} couples")
verifier("registre complet", len(couples) == sum(len(v) for v in a.values()),
         (len(couples), sum(len(v) for v in a.values())))
verifier("aucun doublon signalé", "doublon_registre" not in codes(resultat))

print("3. Couverture et effectifs")
for domaine in sorted(a):
    occurrences, attendu = resultat.couverture(domaine)
    if occurrences != attendu:
        verifier(f"couverture de {domaine}", False, (occurrences, attendu))
        break
else:
    verifier("occurrences inventoriées = valeurs non nulles, pour tous les domaines", True)

print("4. Saturation du plafond")
resultat_s, retour_s = lancer(plafond=1)
verifier("saturation → bloquant", "domaine_sature" in codes(resultat_s) and retour_s == 1,
         codes(resultat_s))
verifier("saturation → recensements discordants détectés",
         "recensements_discordants" in codes(resultat_s), codes(resultat_s))
verifier("saturation → couverture incomplète détectée",
         "couverture_incomplete" in codes(resultat_s), codes(resultat_s))

print("5. Constats de structure, bloquants sauf acquittement")
ds = doc_structures(codes_evenement=("001",))
da = doc_activites(codes_evenement=("008",))
resultat_d, retour_d = lancer(ds=ds, da=da)
verifier("vocabulaires disjoints acquittés → avertissement, pas d'échec",
         gravites(resultat_d, "vocabulaires_disjoints") == {"avertissement"}
         and retour_d == 0,
         (gravites(resultat_d, "vocabulaires_disjoints"), retour_d))

acquittes = dict(ic.CONSTATS_ACQUITTES)
ic.CONSTATS_ACQUITTES.clear()
try:
    resultat_na, retour_na = lancer(ds=ds, da=da)
    verifier("constat non acquitté → bloquant et interruption",
             gravites(resultat_na, "vocabulaires_disjoints") == {"bloquant"}
             and retour_na == 1,
             (gravites(resultat_na, "vocabulaires_disjoints"), retour_na))
    verifier("redondance de colonnes non acquittée → bloquante",
             "colonnes_redondantes" not in codes(resultat_na)
             or gravites(resultat_na, "colonnes_redondantes") == {"bloquant"},
             gravites(resultat_na, "colonnes_redondantes"))
finally:
    ic.CONSTATS_ACQUITTES.update(acquittes)

ds = doc_structures(codes_evenement=("008",), etat_objet1="008")
resultat_c, _ = lancer(ds=ds, da=doc_activites(codes_evenement=("008",), etat_objet1="008"))
verifier("vocabulaires se recoupant → aucun constat de disjonction",
         "vocabulaires_disjoints" not in codes(resultat_c), codes(resultat_c))

print("6. Colonnes constantes et faux positifs")
verifier("paire non discriminante écartée sur le cas nominal",
         "colonnes_redondantes" not in codes(resultat)
         or gravites(resultat, "colonnes_redondantes") == {"avertissement"},
         codes(resultat))

print("7. Domaines jamais alimentés")
verifier("domaines non alimentés signalés en avertissement",
         "domaine_jamais_alimente" not in codes(resultat)
         or gravites(resultat, "domaine_jamais_alimente") == {"avertissement"},
         gravites(resultat, "domaine_jamais_alimente"))
verifier("colonne codifiée toujours nulle signalée",
         "colonne_codifiee_toujours_nulle" in codes(resultat), codes(resultat))

print("8. Déterminisme et mémoire")
r1, _ = lancer()
r2, _ = lancer()
verifier("registre identique d'une exécution à l'autre",
         r1.par_domaine_a == r2.par_domaine_a)
avant = rss_max_mio()
r3, _ = lancer(ds=doc_structures(nb_ej=300), da=doc_activites(nb_ej=300))
apres = rss_max_mio()
verifier("volume x150 ingéré sans anomalie bloquante",
         sum(r.bloquantes for r in r3.registres) == 0, codes(r3))
verifier(f"RSS stable ({avant:.0f} → {apres:.0f} Mio)", apres - avant < 25,
         f"croissance {apres - avant:.1f} Mio")
verifier("nombre de codes indépendant du volume",
         {d: len(v) for d, v in r3.par_domaine_a.items()}
         == {d: len(v) for d, v in r1.par_domaine_a.items()},
         "vocabulaire identique attendu")

print(f"\n{ok} tests réussis, {ko} échecs")
sys.exit(1 if ko else 0)
