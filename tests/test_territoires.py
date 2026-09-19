"""test_territoires.py — Critère de sortie de OOM-11."""
from __future__ import annotations
import sys

from territoires import ErreurTerritoires, departement_depuis_cog

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
# 95 est le seul département métropolitain dont le préfixe commence par 9 :
# la règle « 9 en tête => 3 chiffres » ne doit pas l'absorber par erreur.
verifier("95000 -> 95, non confondu avec un préfixe ultramarin à 3 chiffres",
         departement_depuis_cog("95000") == "95")

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
# liste fermée (cf. docstring) : tout préfixe numérique après un « 9 » de tête
# est accepté, y compris un préfixe non observé dans un échantillon donné.
verifier("préfixe ultramarin non whitelisté mais bien formé -> résolu, pas une erreur",
         departement_depuis_cog("99901") == "999")

try:
    departement_depuis_cog(12345)  # type: ignore[arg-type]
    verifier("cog_commune non textuel -> ErreurTerritoires", False)
except ErreurTerritoires:
    verifier("cog_commune non textuel -> ErreurTerritoires", True)

print(f"\n{ok} tests réussis, {ko} échecs")
sys.exit(1 if ko else 0)
