"""
test_contrat_source.py — Critère de sortie d'E2.

Le contrat est instrumenté par une source factice, entièrement paramétrable,
qui permet de provoquer à volonté chaque situation prévue par le contrat.
Aucun fichier FINESS n'est nécessaire.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mesure_rss import rss_max_mio
from contrat_source import (
    AVERTISSEMENT, BLOQUANT, CONTROLE_ECHANTILLON, CONTROLE_MINIMAL, CONTROLE_STRICT,
    DATE, ENTIER_TEXTE, HORODATAGE, TEXTE,
    Champ, ContexteSource, ErreurContrat, InventaireCodes, RegistreAnomalies,
    Source, TypeEnregistrement, TYPE_ENTETE,
    empreinte_fichier, parcourir_source,
)

BASE = Path("/tmp/tests_contrat")
BASE.mkdir(exist_ok=True)
FICHIER = BASE / "source_factice.txt"
FICHIER.write_text("millesime=202607\n", encoding="utf-8")

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
# Types d'enregistrements de la source factice
# ---------------------------------------------------------------------------

TYPE_ETABLISSEMENT = TypeEnregistrement("etablissement", [
    Champ("identifiant", TEXTE, obligatoire=True),
    Champ("nom", TEXTE, obligatoire=True),
    Champ("code_categorie", TEXTE, domaine="categorie"),
    Champ("date_ouverture", DATE),
    Champ("id_lot", TEXTE, obligatoire=True),
])

TYPE_CAPACITE = TypeEnregistrement("capacite", [
    Champ("identifiant", TEXTE, obligatoire=True),
    Champ("nombre", ENTIER_TEXTE),
    Champ("code_statut", TEXTE, domaine="statut_capacite"),
    Champ("id_lot", TEXTE, obligatoire=True),
])


class SourceFactice(Source):
    """Source entièrement pilotable, destinée à éprouver le contrat."""

    nom = "factice"

    def __init__(self, scenario="nominal", nombre=5, ignores=0, domaine_large=0):
        self.scenario = scenario
        self.nombre = nombre
        self.ignores = ignores
        self.domaine_large = domaine_large

    def millesime(self, chemin):
        return "202607"

    def types_enregistrements(self):
        if self.scenario == "sans_entete_declaree":
            return (TYPE_ETABLISSEMENT, TYPE_CAPACITE)
        return (TYPE_ENTETE, TYPE_ETABLISSEMENT, TYPE_CAPACITE)

    def produire(self, chemin, contexte):
        lot = contexte.lot
        lot.schema_version = "v1.0.0"
        lot.genere_le = "2026-08-01T02:06:22Z"

        if self.scenario != "entete_absente":
            yield ("entete", lot.ligne_entete())

        if self.scenario == "entete_seule":
            return

        if self.scenario == "entete_dupliquee":
            yield ("entete", lot.ligne_entete())

        for i in range(self.nombre):
            contexte.compter_lu("objet_source")
            base = {
                "identifiant": f"{i:09d}",
                "nom": f"Structure {i}",
                "code_categorie": ["183", "186", "177"][i % 3],
                "date_ouverture": "1990-01-01",
                "id_lot": lot.identifiant,
            }
            if self.scenario == "champ_manquant" and i == 1:
                del base["date_ouverture"]
            if self.scenario == "champ_inconnu" and i == 1:
                base["champ_imprevu"] = "x"
            if self.scenario == "valeur_non_textuelle" and i == 1:
                base["nom"] = 42
            if self.scenario == "obligatoire_nul" and i == 1:
                base["nom"] = None
            if self.scenario == "format_date" and i == 1:
                base["date_ouverture"] = "01/01/1990"
            if self.scenario == "domaine_large":
                base["code_categorie"] = f"C{i:06d}"
            yield ("etablissement", base)

            if self.scenario == "type_inconnu" and i == 1:
                yield ("type_qui_nexiste_pas", {"a": "b"})

            yield ("capacite", {
                "identifiant": f"{i:09d}",
                "nombre": str(10 + i),
                "code_statut": "09" if i % 2 else "08",
                "id_lot": lot.identifiant,
            })

        for _ in range(self.ignores):
            contexte.compter_ignore("objet_source")


from contrat_source import Lot, RapportIngestion


def _rapport_vierge():
    return RapportIngestion(Lot("x", "x", "x", "x" * 8, 0), RegistreAnomalies(),
                            InventaireCodes(), CONTROLE_ECHANTILLON)


def executer(source, accumuler=True, **kw):
    """Exécute un parcours et renvoie (lignes, rapport).

    `accumuler=False` consomme le flux sans rien conserver : c'est l'usage
    réel, et la seule façon de mesurer la mémoire du contrat lui-même.
    """
    rap = _rapport_vierge()
    flux = parcourir_source(source, FICHIER, rapport=rap, **kw)
    if accumuler:
        return list(flux), rap
    for _ in flux:
        pass
    return [], rap


# ---------------------------------------------------------------------------

print("1. Déclaration du schéma")
try:
    TypeEnregistrement("t", [Champ("a"), Champ("a")])
    verifier("champs en double refusés", False, "aucune exception")
except ErreurContrat:
    verifier("champs en double refusés", True)
try:
    Champ("a", "FLOTTANT")
    verifier("type de valeur inconnu refusé", False)
except ErreurContrat:
    verifier("type de valeur inconnu refusé", True)
try:
    TypeEnregistrement("t", [])
    verifier("type sans champ refusé", False)
except ErreurContrat:
    verifier("type sans champ refusé", True)
verifier("gabarit complet et à None",
         TYPE_CAPACITE.gabarit() == {"identifiant": None, "nombre": None,
                                     "code_statut": None, "id_lot": None})
verifier("ordre des champs figé",
         TYPE_ETABLISSEMENT.ligne({"nom": "B", "id_lot": "L", "identifiant": "A",
                                   "code_categorie": "183", "date_ouverture": "1990-01-01"})
         == ("A", "B", "183", "1990-01-01", "L"))

print("2. Cas nominal")
lignes, rap = executer(SourceFactice("nominal", nombre=5))
verifier("statut SUCCES", rap.statut == "SUCCES", rap.statut)
verifier("en-tête émise en premier", lignes[0][0] == "entete")
verifier("effectifs par type", rap.emis == {"entete": 1, "etablissement": 5, "capacite": 5},
         rap.emis)
verifier("aucune anomalie", rap.registre.total() == 0, rap.registre.par_code())
verifier("compteur de lecture renseigné", rap.lus == {"objet_source": 5}, rap.lus)
verifier("lignes émises sous forme de tuples",
         all(isinstance(l, tuple) for _n, l in lignes))
verifier("identifiant de lot déterministe",
         rap.lot.identifiant == executer(SourceFactice("nominal", nombre=5))[1].lot.identifiant)
verifier("en-tête conforme au type déclaré",
         len(lignes[0][1]) == len(TYPE_ENTETE.noms))

print("3. Inventaire des codes")
verifier("deux domaines inventoriés", rap.inventaire.domaines() == ["categorie", "statut_capacite"],
         rap.inventaire.domaines())
verifier("valeurs distinctes de catégorie", rap.inventaire.nombre_distinct("categorie") == 3,
         rap.inventaire.valeurs("categorie"))
verifier("occurrences comptées", sum(rap.inventaire.valeurs("categorie").values()) == 5)
verifier("aucun domaine saturé", not rap.inventaire.sature("categorie"))

_, rap_large = executer(SourceFactice("domaine_large", nombre=50), max_codes_par_domaine=10)
verifier("saturation détectée", rap_large.inventaire.sature("categorie"))
verifier("plafond respecté", rap_large.inventaire.nombre_distinct("categorie") == 10,
         rap_large.inventaire.nombre_distinct("categorie"))

print("4. Violations du contrat")
for scenario, code_attendu in [
    ("champ_manquant", "ligne_hors_contrat"),
    ("champ_inconnu", "ligne_hors_contrat"),
    ("obligatoire_nul", "champ_obligatoire_nul"),
    ("type_inconnu", "type_hors_contrat"),
    ("entete_absente", "entete_absente"),
    ("entete_dupliquee", "entete_manquante_ou_multiple"),
    ("entete_seule", "aucune_donnee"),
]:
    _, r = executer(SourceFactice(scenario, nombre=3))
    verifier(f"{scenario} → {code_attendu} bloquant",
             code_attendu in r.registre.par_code() and r.statut == "ECHEC",
             f"codes={r.registre.par_code()} statut={r.statut}")

_, r_nt = executer(SourceFactice("valeur_non_textuelle", nombre=3), controle=CONTROLE_STRICT)
verifier("valeur_non_textuelle → bloquant en mode strict",
         "valeur_non_textuelle" in r_nt.registre.par_code() and r_nt.statut == "ECHEC",
         r_nt.registre.par_code())
_, r_nt2 = executer(SourceFactice("valeur_non_textuelle", nombre=3),
                    controle=CONTROLE_ECHANTILLON, pas_echantillon=1000)
verifier("valeur_non_textuelle échappe à l'échantillon (limite assumée, cf. docstring)",
         "valeur_non_textuelle" not in r_nt2.registre.par_code(),
         r_nt2.registre.par_code())

_, r = executer(SourceFactice("nominal", nombre=3, ignores=2))
verifier("objets ignorés → échec bloquant",
         "objets_ignores" in r.registre.par_code() and r.statut == "ECHEC",
         r.registre.par_code())

print("5. Contrôle de format selon le mode")
_, r_strict = executer(SourceFactice("format_date", nombre=3), controle=CONTROLE_STRICT)
verifier("mode strict détecte la date mal formée",
         "format_inattendu" in r_strict.registre.par_code())
verifier("format mal formé = avertissement, pas échec", r_strict.statut == "SUCCES",
         r_strict.statut)
_, r_min = executer(SourceFactice("format_date", nombre=3), controle=CONTROLE_MINIMAL)
verifier("mode minimal ne contrôle aucun format",
         "format_inattendu" not in r_min.registre.par_code())
_, r_ech = executer(SourceFactice("format_date", nombre=200),
                    controle=CONTROLE_ECHANTILLON, pas_echantillon=1000)
verifier("mode échantillon ne contrôle qu'une fraction des lignes",
         r_ech.lignes_controlees == 1, r_ech.lignes_controlees)
verifier("cardinalité toujours contrôlée quel que soit le mode",
         executer(SourceFactice("champ_manquant", nombre=3),
                  controle=CONTROLE_MINIMAL)[1].statut == "ECHEC")

print("6. Bornes du registre d'anomalies")
_, r_borne = executer(SourceFactice("obligatoire_nul", nombre=3), max_exemples=1)
verifier("exemples plafonnés", len(r_borne.registre.exemples("champ_obligatoire_nul")) <= 1)
registre = RegistreAnomalies(max_exemples=2)
for i in range(10_000):
    registre.signaler("essai", AVERTISSEMENT, detail=str(i))
verifier("comptage exhaustif malgré le plafond d'exemples",
         registre.total() == 10_000 and len(registre.exemples("essai")) == 2)

print("7. Contrat de la source elle-même")
try:
    list(parcourir_source(SourceFactice("sans_entete_declaree"), FICHIER))
    verifier("source ne déclarant pas l'en-tête refusée", False)
except ErreurContrat:
    verifier("source ne déclarant pas l'en-tête refusée", True)
try:
    list(parcourir_source(SourceFactice("nominal"), FICHIER, controle="fantaisie"))
    verifier("mode de contrôle inconnu refusé", False)
except ErreurContrat:
    verifier("mode de contrôle inconnu refusé", True)
try:
    list(parcourir_source(SourceFactice("nominal"), BASE / "inexistant.txt"))
    verifier("fichier absent refusé", False)
except ErreurContrat:
    verifier("fichier absent refusé", True)

print("8. Empreinte")
e1, o1 = empreinte_fichier(FICHIER)
e2, o2 = empreinte_fichier(FICHIER, taille_bloc=3)
verifier("empreinte indépendante de la taille de bloc", e1 == e2 and o1 == o2)
verifier("empreinte de 64 caractères hexadécimaux", len(e1) == 64 and int(e1, 16) >= 0)

print("9. Mémoire bornée sur un flux volumineux (flux consommé sans accumulation)")
avant = rss_max_mio()
_, r_gros = executer(SourceFactice("nominal", nombre=200_000), accumuler=False)
apres = rss_max_mio()
verifier("400 001 lignes émises", r_gros.total_emis == 400_001, r_gros.total_emis)
verifier(f"RSS stable ({avant:.0f} → {apres:.0f} Mio)", apres - avant < 10,
         f"croissance {apres - avant:.1f} Mio")
verifier("inventaire toujours borné", r_gros.inventaire.nombre_distinct("categorie") == 3)
_, r_gros2 = executer(SourceFactice("nominal", nombre=400_000), accumuler=False)
encore = rss_max_mio()
verifier(f"mémoire indépendante du volume (x2 lignes → {encore:.0f} Mio)",
         encore - apres < 5, f"croissance {encore - apres:.1f} Mio")

print(f"\n{ok} tests réussis, {ko} échecs")
sys.exit(1 if ko else 0)
