"""
test_finess_structures.py — Critère de sortie d'E3.

Les fichiers synthétiques sont construits à partir des jeux de clés déclarés,
et non écrits à la main : un fichier de test ne peut donc pas diverger du
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
import finess_structures as fs

BASE = Path("/tmp/tests_structures")
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


# ---------------------------------------------------------------------------
# Fabrique de documents synthétiques
# ---------------------------------------------------------------------------

def objet(cles, **valeurs):
    """Objet portant exactement les clés déclarées, valorisé au besoin."""
    base = {c: None for c in sorted(cles)}
    inconnues = set(valeurs) - set(cles)
    if inconnues:
        raise AssertionError(f"clés hors contrat dans le test : {inconnues}")
    base.update(valeurs)
    return base


def adresse(n="1", commune="01001"):
    return objet(fc.CLES_ADRESSE, usageAdresse="03", numeroVoie=n, typeVoie="RUE",
                 libelleVoie="DES LILAS", cogCommune=commune, codePostal="01000",
                 ligneAcheminement="01000 BOURG",
                 coordonneesGeographique=objet(fc.CLES_COORDONNEES,
                                               coordonneeX="5.22", coordonneeY="46.20",
                                               directionLatitude="N", directionLongitude="E",
                                               cleInInteropBAN="01001_0001", scoreBAN="0.95"))


def contact(tel="0474000000"):
    return objet(fc.CLES_CONTACT,
                 typeContact=objet(fc.CLES_TYPE_CONTACT, roleContact="01"),
                 telecom=objet(fc.CLES_TELECOM, telephone=tel))


def engagement(eid="E1", type_e="DISP", sous_type="DIT", autorites=1):
    return objet(fc.CLES_ENGAGEMENT, engagementId=eid, typeEngagement=type_e,
                 sousTypeEngagement=sous_type, dateEffetEngagement="2020-01-01",
                 dateSignatureEngagement="2019-12-01",
                 autoriteRegulationEngagement=[
                     objet(fc.CLES_AUTORITE, autoriteRegulationid=f"ARS-{i:02d}")
                     for i in range(autorites)])


def evenement(vid="V1"):
    return objet(fc.CLES_EVENEMENT, evenementId=vid, codeEvenement="CRE",
                 dateEvenement="2020-01-01", dateEnregistrement="2020-01-02T10:00:00Z",
                 etatObjet1="A", typeObjet1="EGE", identifiantObjet1="1",
                 systemeMaitre="FINESS")


def ege(num="010000024", ege_id="1", roles=1):
    return objet(fs.CLES_EGE,
                 informationsGeneralesEGE=objet(
                     fs.CLES_INFOS_EGE, egeId=ege_id, numFinessEge=num,
                     nomEgeCourt="IME LES SAPINS", nomEgeLong="IME LES SAPINS LONG",
                     siret="12345678900011", espic=["1"], numeroEducationNationale="0010001A",
                     dateOuverture="1990-01-01", datePremiereAutorisation="1990-01-01"),
                 categorieentiteGeographiqueExercice="183",
                 modefixationtarifaire="01", typeBudget=["01"],
                 adresse=[adresse(), adresse("2")], contact=[contact()],
                 engagement=[engagement("E-ET")], evenement=[evenement("V-ET")],
                 roleEge=[objet(fs.CLES_ROLE_EGE, idEgePorteuse="1",
                                idEgeNonPorteuse="2", roleRelationEge="B")
                          for _ in range(roles)],
                 etatObjet="A", dateDerniereMaj="2026-05-01T00:00:00Z")


def pmej(num="010008407", pm_id="100", nb_ege=2):
    return objet(fs.CLES_PMEJ,
                 informationsGeneralesPMEJ=objet(
                     fs.CLES_INFOS_PMEJ, pmSmsseId=pm_id, numFinessPm=num,
                     denominationPm="ASSOCIATION X", denominationLonguePmSmsse="ASSOCIATION X LONG",
                     siren="123456789", codeApe="8710A", statutJuridique="60",
                     typePersonneMorale="1", dateCreation="1980-01-01"),
                 adresse=[adresse()], contact=[contact()],
                 engagement=[engagement("E-EJ")], evenement=[evenement("V-EJ")],
                 ege=[ege(f"01000002{i}", str(i)) for i in range(nb_ege)],
                 etatObjet="A", dateDerniereMaj="2026-05-01T00:00:00Z")


def document(nb_pmej=2, nb_ege=2, gco=1, gcc=1, **surcharges):
    doc = {
        "schemaVersion": "v1.0.0",
        "generatedAt": "2026-08-01T02:06:22Z",
        "gco": [objet(fs.CLES_GCO, pmSmsseId=f"9{i}", typeGco="001",
                      pmejDuGco=[objet(fc.CLES_MEMBRE_GROUPEMENT,
                                       pmSmsseId="100", typeRoleEntiteGroupe="M")],
                      egeDuGco=[]) for i in range(gco)],
        "gcc": [objet(fs.CLES_GCC, gccId=f"G{i}", nomGcc="GCSMS TEST", typeGcc="001",
                      numFinessGcc="49824516535", engagement=[], evenement=[evenement("V-GCC")],
                      pmejDuGcc=[objet(fc.CLES_MEMBRE_GROUPEMENT,
                                       pmSmsseId="100", typeRoleEntiteGroupe="M")],
                      egeDuGcc=[], etatObjet="A",
                      dateDerniereMaj="2026-05-01T00:00:00Z") for i in range(gcc)],
        "pmej": [pmej(f"01000840{i}", str(100 + i), nb_ege) for i in range(nb_pmej)],
    }
    doc.update(surcharges)
    return doc


def ecrire(nom, doc):
    chemin = BASE / nom
    chemin.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return chemin


def executer(chemin, accumuler=True, controle=CONTROLE_STRICT):
    rap = RapportIngestion(Lot("", "", "", "", 0), RegistreAnomalies(),
                           InventaireCodes(), controle)
    flux = parcourir_source(fs.SourceFinessStructures(), chemin,
                            controle=controle, rapport=rap)
    if not accumuler:
        for _ in flux:
            pass
        return [], rap
    return list(flux), rap


# ---------------------------------------------------------------------------

print("1. Cas nominal, contrôle strict")
chemin = ecrire("nominal-mensuel-202607.json", document(nb_pmej=2, nb_ege=2))
lignes, rap = executer(chemin)
verifier("statut SUCCES", rap.statut == "SUCCES", rap.registre.par_code())
verifier("aucune anomalie", rap.registre.total() == 0, rap.registre.par_code())
attendu = {
    "entete": 1, "groupement": 2, "groupement_membre": 2,
    "entite_juridique": 2, "etablissement": 4,
    "adresse": 2 * 1 + 4 * 2, "contact": 2 + 4,
    "engagement": 2 + 4, "engagement_autorite": 6,
    "evenement": 1 + 2 + 4, "relation_etablissement": 4,
}
verifier("effectifs par type conformes", rap.emis == attendu,
         {k: v for k, v in rap.emis.items() if attendu.get(k) != v})
verifier("millésime lu dans le nom du fichier", rap.lot.millesime == "202607",
         rap.lot.millesime)
verifier("en-tête émise en premier", lignes[0][0] == "entete")
verifier("ordre du document respecté (groupements avant entités juridiques)",
         [n for n, _ in lignes].index("groupement") < [n for n, _ in lignes].index("entite_juridique"))

print("2. Contenu et rattachements")
par_type = {}
for nom, ligne in lignes:
    par_type.setdefault(nom, []).append(ligne)

etab = par_type["etablissement"][0]
pos = fc.TYPE_ETABLISSEMENT.position
verifier("établissement rattaché à son entité juridique",
         etab[pos("num_finess_ej")] == "010008400" and etab[pos("num_finess_et")] == "010000020",
         etab[:4])
verifier("liste espic aplatie en colonne", etab[pos("code_espic")] == "1")
verifier("liste typeBudget aplatie en colonne", etab[pos("code_type_budget")] == "01")
verifier("catégorie prise au niveau de l'établissement", etab[pos("code_categorie")] == "183")

adresses_et = [a for a in par_type["adresse"]
               if a[fc.TYPE_ADRESSE.position("type_porteur")] == fc.PORTEUR_ET]
pos_a = fc.TYPE_ADRESSE.position
verifier("adresses d'établissement rattachées et rangées",
         len(adresses_et) == 8 and {a[pos_a("rang")] for a in adresses_et} == {"0", "1"},
         len(adresses_et))
verifier("coordonnées BAN aplaties",
         adresses_et[0][pos_a("cle_interop_ban")] == "01001_0001"
         and adresses_et[0][pos_a("score_ban")] == "0.95")
verifier("adresse d'entité juridique rattachée au bon porteur",
         [a for a in par_type["adresse"]
          if a[pos_a("type_porteur")] == fc.PORTEUR_EJ][0][pos_a("num_finess_porteur")] == "010008400")

pos_e = fc.TYPE_ENGAGEMENT.position
dispositifs = [e for e in par_type["engagement"]
               if e[pos_e("code_sous_type_engagement")] == "DIT"]
verifier("engagement DISP/DIT conservé", len(dispositifs) == 6, len(dispositifs))
verifier("autorités de régulation rattachées à leur engagement",
         par_type["engagement_autorite"][0][
             fc.TYPE_ENGAGEMENT_AUTORITE.position("engagement_id")] in {"E-EJ", "E-ET"})

pos_g = fc.TYPE_GROUPEMENT.position
gco_ligne = [g for g in par_type["groupement"]
             if g[pos_g("nature_groupement")] == fc.GROUPEMENT_GCO][0]
gcc_ligne = [g for g in par_type["groupement"]
             if g[pos_g("nature_groupement")] == fc.GROUPEMENT_GCC][0]
verifier("GCO sans numéro FINESS ni nom", gco_ligne[pos_g("num_finess_groupement")] is None
         and gco_ligne[pos_g("nom_groupement")] is None)
verifier("GCC avec numéro FINESS et nom",
         gcc_ligne[pos_g("num_finess_groupement")] == "49824516535"
         and gcc_ligne[pos_g("nom_groupement")] == "GCSMS TEST")
verifier("évènement de groupement rattaché",
         any(v[fc.TYPE_EVENEMENT.position("type_porteur")] == fc.PORTEUR_GROUPEMENT
             for v in par_type["evenement"]))

print("3. Détection des dérives de schéma")
cas = [
    ("cle_ajoutee", "cle_json_non_declaree",
     lambda d: d["pmej"][0]["informationsGeneralesPMEJ"].update({"champNouveau": "x"})),
    ("cle_supprimee", "cle_json_absente",
     lambda d: d["pmej"][0]["informationsGeneralesPMEJ"].pop("siren")),
    ("cle_ajoutee_ege", "cle_json_non_declaree",
     lambda d: d["pmej"][0]["ege"][0].update({"nouveauBloc": []})),
    ("cle_ajoutee_adresse", "cle_json_non_declaree",
     lambda d: d["pmej"][0]["adresse"][0].update({"etage": "2"})),
    ("cle_ajoutee_capacite_coord", "cle_json_non_declaree",
     lambda d: d["pmej"][0]["adresse"][0]["coordonneesGeographique"].update({"altitude": "300"})),
]
for nom_cas, code_attendu, muter in cas:
    doc = document(nb_pmej=1, nb_ege=1)
    muter(doc)
    _, r = executer(ecrire(f"{nom_cas}-202607.json", doc))
    verifier(f"{nom_cas} → {code_attendu} bloquant",
             code_attendu in r.registre.par_code() and r.statut == "ECHEC",
             r.registre.par_code())

doc = document(nb_pmej=1, nb_ege=1)
doc["nouveauTableau"] = [{"a": "b"}]
_, r = executer(ecrire("tableau-racine-202607.json", doc))
verifier("tableau racine inconnu → bloquant",
         "tableau_racine_non_declare" in r.registre.par_code() and r.statut == "ECHEC",
         r.registre.par_code())

doc = document(nb_pmej=1, nb_ege=1)
doc["nouvelleCleScalaire"] = "x"
_, r = executer(ecrire("scalaire-racine-202607.json", doc))
verifier("clé racine scalaire inconnue → bloquant",
         "cle_racine_non_declaree" in r.registre.par_code() and r.statut == "ECHEC",
         r.registre.par_code())

doc = document(nb_pmej=1, nb_ege=1)
doc["pmej"][0]["ege"][0]["typeBudget"] = ["01", "02"]
_, r = executer(ecrire("cardinalite-202607.json", doc))
verifier("typeBudget de cardinalité 2 → bloquant",
         "cardinalite_inattendue" in r.registre.par_code() and r.statut == "ECHEC",
         r.registre.par_code())

doc = document(nb_pmej=1, nb_ege=1)
doc["gco"][0]["egeDuGco"] = [{"quelqueChose": "x"}]
_, r = executer(ecrire("membres-ege-202607.json", doc))
verifier("membres établissements d'un groupement → bloquant, jamais silencieux",
         "structure_inconnue" in r.registre.par_code()
         and "objets_ignores" in r.registre.par_code() and r.statut == "ECHEC",
         r.registre.par_code())

print("4. Champ obligatoire manquant dans la donnée")
doc = document(nb_pmej=1, nb_ege=1)
doc["pmej"][0]["ege"][0]["informationsGeneralesEGE"]["nomEgeCourt"] = None
_, r = executer(ecrire("obligatoire-202607.json", doc))
verifier("nom d'établissement nul → bloquant",
         "champ_obligatoire_nul" in r.registre.par_code() and r.statut == "ECHEC",
         r.registre.par_code())

print("5. Cas limites structurels")
doc = document(nb_pmej=1, nb_ege=0, gco=0, gcc=0)
_, r = executer(ecrire("sans-ege-202607.json", doc))
verifier("entité juridique sans établissement acceptée",
         r.statut == "SUCCES" and r.emis.get("etablissement") is None, r.emis)
doc = document(nb_pmej=0, nb_ege=0, gco=0, gcc=0)
_, r = executer(ecrire("vide-202607.json", doc))
verifier("document sans aucune entité → aucune_donnee bloquant",
         "aucune_donnee" in r.registre.par_code(), r.registre.par_code())

print("6. Déterminisme et mémoire")
chemin = ecrire("nominal-mensuel-202607.json", document(nb_pmej=2, nb_ege=2))
lignes_a, rap_a = executer(chemin)
lignes_b, rap_b = executer(chemin)
verifier("identifiant de lot déterministe", rap_a.lot.identifiant == rap_b.lot.identifiant)
verifier("séquence de lignes identique d'une exécution à l'autre", lignes_a == lignes_b)

gros = ecrire("volumineux-202607.json", document(nb_pmej=1500, nb_ege=4))
avant = rss_max_mio()
_, r_gros = executer(gros, accumuler=False)
apres = rss_max_mio()
verifier("gros document ingéré sans anomalie",
         r_gros.statut == "SUCCES" and r_gros.emis["etablissement"] == 6000,
         (r_gros.statut, r_gros.emis.get("etablissement")))
verifier(f"RSS stable ({avant:.0f} → {apres:.0f} Mio)", apres - avant < 20,
         f"croissance {apres - avant:.1f} Mio")

print(f"\n{ok} tests réussis, {ko} échecs")
sys.exit(1 if ko else 0)
