"""test_territoires.py — Critère de sortie de OOM-11."""
from __future__ import annotations
import sys, tempfile
from pathlib import Path

from territoires import (ErreurTerritoires, charger_departements,
                         departement_depuis_cog)

ok = ko = 0
def verifier(intitule, condition, detail=""):
    global ok, ko
    if condition: ok += 1; print(f"  OK    {intitule}")
    else: ko += 1; print(f"  ECHEC {intitule} — {detail}")

print("1. Métropole")
verifier("01001 -> 01", departement_depuis_cog("01001") == "01")
verifier("75056 -> 75 (Paris)", departement_depuis_cog("75056") == "75")
verifier("13055 -> 13 (Marseille)", departement_depuis_cog("13055") == "13")
verifier("95580 -> 95 (Val-d'Oise, borne haute métropole)",
         departement_depuis_cog("95580") == "95")
# 95 commence par 9 : la règle « 96-99 en tête => 3 chiffres » ne doit pas
# l'absorber par erreur.
verifier("95000 -> 95, non confondu avec un préfixe ultramarin à 3 chiffres",
         departement_depuis_cog("95000") == "95")

# 90 à 94 commencent aussi par 9 : jusqu'à OOM-106 ils étaient dérivés à tort
# en préfixe ultramarin à 3 chiffres (91228 -> "912").
for cog, dep in (("90010", "90"), ("91228", "91"), ("92012", "92"),
                 ("93066", "93"), ("94028", "94")):
    verifier(f"{cog} -> {dep} (métropole, pas un préfixe ultramarin)",
             departement_depuis_cog(cog) == dep, departement_depuis_cog(cog))

print("2. Corse")
verifier("2A247 -> 2A", departement_depuis_cog("2A247") == "2A")
verifier("2B033 -> 2B", departement_depuis_cog("2B033") == "2B")
verifier("préfixe corse en minuscule normalisé -> 2A",
         departement_depuis_cog("2a247") == "2A")

print("3. Outre-mer (DOM-TOM-COM)")
verifier("97105 -> 971 (Guadeloupe)", departement_depuis_cog("97105") == "971")
verifier("97209 -> 972 (Martinique)", departement_depuis_cog("97209") == "972")
verifier("97411 -> 974 (La Réunion)", departement_depuis_cog("97411") == "974")
verifier("98818 -> 988 (préfixe à 3 chiffres non whitelisté explicitement)",
         departement_depuis_cog("98818") == "988")

print("4. Non-résolution explicite, jamais de valeur devinée")
try:
    departement_depuis_cog("")
    verifier("cog_commune vide -> ErreurTerritoires", False)
except ErreurTerritoires:
    verifier("cog_commune vide -> ErreurTerritoires", True)

try:
    departement_depuis_cog(None)  # type: ignore[arg-type]
    verifier("cog_commune None -> ErreurTerritoires", False)
except ErreurTerritoires:
    verifier("cog_commune None -> ErreurTerritoires", True)

try:
    departement_depuis_cog("1A")
    verifier("cog_commune trop court -> ErreurTerritoires", False)
except ErreurTerritoires:
    verifier("cog_commune trop court -> ErreurTerritoires", True)

try:
    departement_depuis_cog("ABCDE")
    verifier("préfixe non reconnu -> ErreurTerritoires", False)
except ErreurTerritoires:
    verifier("préfixe non reconnu -> ErreurTerritoires", True)

try:
    departement_depuis_cog("20123")
    verifier("préfixe 20 (Corse pré-1976, disparu) -> ErreurTerritoires", False)
except ErreurTerritoires:
    verifier("préfixe 20 (Corse pré-1976, disparu) -> ErreurTerritoires", True)

try:
    departement_depuis_cog("00123")
    verifier("préfixe métropole hors bornes (00) -> ErreurTerritoires", False)
except ErreurTerritoires:
    verifier("préfixe métropole hors bornes (00) -> ErreurTerritoires", True)

# Un préfixe outre-mer à 3 chiffres n'est volontairement pas validé contre une
# liste fermée (cf. docstring) : tout préfixe numérique commençant par 96 à 99
# est accepté, y compris un préfixe non observé dans un échantillon donné.
verifier("préfixe ultramarin non whitelisté mais bien formé -> résolu, pas une erreur",
         departement_depuis_cog("99901") == "999")

try:
    departement_depuis_cog(12345)  # type: ignore[arg-type]
    verifier("cog_commune non textuel -> ErreurTerritoires", False)
except ErreurTerritoires:
    verifier("cog_commune non textuel -> ErreurTerritoires", True)

print("5. Référentiel des départements (OOM-106)")
departements = charger_departements()
codes = list(departements)
verifier("101 départements", len(departements) == 101, len(departements))
verifier("codes tous textuels", all(isinstance(c, str) for c in codes))
verifier("2A et 2B présents, 20 absent",
         "2A" in departements and "2B" in departements and "20" not in departements)
verifier("zéro de tête conservé (01 et non 1)", "01" in departements and "1" not in departements)
verifier("DROM 971 à 974 et 976 présents, 975 absent",
         all(c in departements for c in ("971", "972", "973", "974", "976"))
         and "975" not in departements)
verifier("ordre du COG : 01 en tête, 2A/2B entre 29 et 30, 976 en dernier",
         codes[0] == "01" and codes[-1] == "976"
         and codes.index("29") + 1 == codes.index("2A") == codes.index("2B") - 1
         and codes.index("2B") + 1 == codes.index("30"), codes[25:35])
verifier("libellés résolus (2A, 974)",
         departements["2A"] == "Corse-du-Sud" and departements["974"] == "La Réunion",
         (departements.get("2A"), departements.get("974")))
verifier("chaque code du référentiel est celui que dérive departement_depuis_cog",
         all(departement_depuis_cog(c + "0" * (5 - len(c))) == c for c in codes))

with tempfile.TemporaryDirectory() as dossier:
    for nom, contenu in (("absent", None),
                         ("double", "code;libelle\n01;Ain\n01;Ain\n"),
                         ("incomplet", "code;libelle\n01;\n"),
                         ("colonnes", "dep;nom\n01;Ain\n"),
                         ("vide", "# rien\ncode;libelle\n")):
        chemin = Path(dossier) / f"{nom}.csv"
        if contenu is not None:
            chemin.write_text(contenu, encoding="utf-8")
        try:
            charger_departements(chemin)
            verifier(f"référentiel {nom} -> ErreurTerritoires", False)
        except ErreurTerritoires as erreur:
            verifier(f"référentiel {nom} -> ErreurTerritoires, chemin cité",
                     str(chemin) in str(erreur), str(erreur))

print(f"\n{ok} tests réussis, {ko} échecs")
sys.exit(1 if ko else 0)
