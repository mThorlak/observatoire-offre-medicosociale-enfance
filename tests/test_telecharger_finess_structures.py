"""test_telecharger_finess_structures.py — Acquisition automatisée, hors réseau réel.

data.gouv.fr est injoignable depuis les environnements d'exécution
automatisés dont on dispose pour écrire ce test (confirmé le 13/08/2026 :
tunnel réseau sortant refusé). `urllib.request.urlopen` est donc remplacé
par un double qui rejoue la forme exacte de réponse constatée le même jour
en interrogeant l'API à la main, plus un contenu de fichier synthétique. Ce
n'est pas un renoncement : ça sépare ce qui est du ressort de ce script
(sélection de la ressource, vérification taille/checksum, écriture des
métadonnées) de ce qui est du ressort du réseau, imprévisible et hors de
portée d'un test reproductible.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import telecharger_finess_structures as tfs  # noqa: E402

BASE = Path("/tmp/tests_telecharger_finess")
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


CONTENU_FICHIER = gzip.compress(b'{"schemaVersion": "v1.0.0", "pmej": []}')
SHA1_CONTENU = hashlib.sha1(CONTENU_FICHIER).hexdigest()


def api_reponse(resources):
    return {"id": "finess-structures-1", "resources": resources}


def resource(titre="finess-structures-journalier-20260812.json.gz",
            checksum=None, filesize=None, format_="json.gz"):
    return {
        "id": "cd493959-fb03-41e5-9347-0edd14dfbc22",
        "title": titre,
        "format": format_,
        "url": "https://static.data.gouv.fr/resources/finess-structures-1/x.json.gz",
        "filesize": filesize if filesize is not None else len(CONTENU_FICHIER),
        "checksum": {"type": "sha1", "value": checksum or SHA1_CONTENU},
        "last_modified": "2026-08-12T02:16:25.817000+00:00",
    }


class FausseReponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_exception):
        return False


def urlopen_pour(donnees_api, contenu_fichier):
    """Faux urlopen : sert le JSON de l'API pour API_DATASET, les octets du
    fichier pour toute autre URL (celle de téléchargement)."""
    corps_api = json.dumps(donnees_api).encode("utf-8")

    def _urlopen(requete, timeout=None):
        if requete.full_url == tfs.API_DATASET:
            return FausseReponse(corps_api)
        return FausseReponse(contenu_fichier)

    return _urlopen


print("1. Cas nominal — une seule ressource journalière, taille et checksum corrects")
donnees = api_reponse([
    resource(),
    resource(titre="finess-structures-mensuel-202607.json.gz"),
])
dest = BASE / "structures.json.gz"
if dest.exists():
    dest.unlink()
with mock.patch.object(urllib.request, "urlopen", urlopen_pour(donnees, CONTENU_FICHIER)):
    resultat = tfs.executer(dest)
verifier("fichier écrit avec le bon contenu", dest.read_bytes() == CONTENU_FICHIER)
verifier("le mensuel n'est pas confondu avec le journalier",
         resultat["resource"]["title"].startswith(tfs.PREFIXE_JOURNALIER),
         resultat["resource"]["title"])
verifier("métadonnées écrites", resultat["metadata"].exists())
meta = json.loads(resultat["metadata"].read_text(encoding="utf-8"))
verifier("empreinte consignée dans les métadonnées",
         meta["checksum_sha1"] == SHA1_CONTENU)
verifier("provenance consignée (url, taille, date de téléchargement)",
         meta["url_source"] and meta["filesize"] and meta["telecharge_le"])

print("2. Checksum divergent → échec explicite, rien de silencieux")
donnees_corrompues = api_reponse([resource(checksum="0" * 40)])
dest2 = BASE / "structures_corrompu.json.gz"
if dest2.exists():
    dest2.unlink()
try:
    with mock.patch.object(urllib.request, "urlopen",
                           urlopen_pour(donnees_corrompues, CONTENU_FICHIER)):
        tfs.executer(dest2)
    verifier("checksum divergent détecté", False)
except tfs.ErreurTelechargement as erreur:
    verifier("checksum divergent détecté", "Checksum divergent" in str(erreur), str(erreur))
verifier("le fichier corrompu reste sur disque pour inspection, non supprimé",
         dest2.exists())

print("3. Ressource journalière absente ou ambiguë → refus explicite, pas de choix arbitraire")
donnees_absente = api_reponse([resource(titre="finess-structures-mensuel-202607.json.gz")])
try:
    tfs.resource_courante(donnees_absente)
    verifier("aucune ressource journalière → refus", False)
except tfs.ErreurTelechargement:
    verifier("aucune ressource journalière → refus", True)

donnees_doublon = api_reponse([
    resource(),
    resource(titre="finess-structures-journalier-20260811.json.gz"),
])
try:
    tfs.resource_courante(donnees_doublon)
    verifier("deux ressources journalières → refus", False)
except tfs.ErreurTelechargement:
    verifier("deux ressources journalières → refus", True)

print("4. Taille divergente → échec explicite, avant même de calculer le checksum")
donnees_taille = api_reponse([resource(filesize=999999)])
dest3 = BASE / "structures_taille.json.gz"
if dest3.exists():
    dest3.unlink()
try:
    with mock.patch.object(urllib.request, "urlopen",
                           urlopen_pour(donnees_taille, CONTENU_FICHIER)):
        tfs.executer(dest3)
    verifier("taille divergente détectée", False)
except tfs.ErreurTelechargement as erreur:
    verifier("taille divergente détectée", "Taille divergente" in str(erreur), str(erreur))

print("5. CLI (main) — code de retour et messages")
dest4 = BASE / "structures_cli.json.gz"
if dest4.exists():
    dest4.unlink()
with mock.patch.object(urllib.request, "urlopen", urlopen_pour(donnees, CONTENU_FICHIER)):
    retour = tfs.main([str(dest4)])
verifier("code de retour nul sur succès", retour == 0)

dest5 = BASE / "structures_cli_echec.json.gz"
if dest5.exists():
    dest5.unlink()
with mock.patch.object(urllib.request, "urlopen",
                       urlopen_pour(donnees_corrompues, CONTENU_FICHIER)):
    retour = tfs.main([str(dest5)])
verifier("code de retour non nul sur échec de vérification", retour == 1)

print("6. Mensuel figé (OOM-54) — sélection par millésime exact, jamais de repli")
donnees_mensuels = api_reponse([
    resource(titre="finess-structures-mensuel-202608.json.gz"),
    resource(titre="finess-structures-mensuel-202607.json.gz"),
    resource(),
    resource(titre="finess-structures-mensuel-202606.csv", format_="csv"),
    resource(titre="finess-structures-mensuel-2026-05.json.gz"),
])
verifier("mensuels disponibles listés, triés, formats et titres hors motif écartés",
         tfs.mensuels_disponibles(donnees_mensuels) == ["202607", "202608"],
         tfs.mensuels_disponibles(donnees_mensuels))
verifier("le mensuel demandé est sélectionné",
         tfs.resource_mensuelle(donnees_mensuels, "202607")["title"]
         == "finess-structures-mensuel-202607.json.gz")

try:
    tfs.resource_mensuelle(donnees_mensuels, "202609")
    verifier("mensuel non publié → refus", False)
except tfs.ErreurTelechargement as erreur:
    message = str(erreur)
    verifier("mensuel non publié → refus qui liste les mensuels disponibles",
             "202607" in message and "202608" in message, message)

for invalide in ("2026-08", "202613", "20260801", "", "abcdef"):
    try:
        tfs.resource_mensuelle(donnees_mensuels, invalide)
        verifier(f"millésime invalide {invalide!r} → refus", False)
    except tfs.ErreurTelechargement:
        verifier(f"millésime invalide {invalide!r} → refus", True)

try:
    tfs.resource_mensuelle(api_reponse([resource()]), "202608")
    verifier("aucun mensuel publié → refus, sans repli sur le journalier", False)
except tfs.ErreurTelechargement as erreur:
    verifier("aucun mensuel publié → refus, sans repli sur le journalier",
             "aucun" in str(erreur), str(erreur))

try:
    tfs.resource_mensuelle(api_reponse([
        resource(titre="finess-structures-mensuel-202608.json.gz"),
        resource(titre="finess-structures-mensuel-202608.json.gz"),
    ]), "202608")
    verifier("mensuel publié en double → refus", False)
except tfs.ErreurTelechargement:
    verifier("mensuel publié en double → refus", True)

dest6 = BASE / "finess-structures-mensuel-202608.json.gz"
if dest6.exists():
    dest6.unlink()
with mock.patch.object(urllib.request, "urlopen",
                       urlopen_pour(donnees_mensuels, CONTENU_FICHIER)):
    resultat = tfs.executer(dest6, mensuel="202608")
verifier("executer(mensuel=...) télécharge le mensuel demandé",
         resultat["resource"]["title"] == "finess-structures-mensuel-202608.json.gz"
         and dest6.read_bytes() == CONTENU_FICHIER)
meta = json.loads(resultat["metadata"].read_text(encoding="utf-8"))
verifier("titre source du mensuel consigné (porte le millésime, OOM-116)",
         meta["titre"] == "finess-structures-mensuel-202608.json.gz", meta["titre"])

donnees_mensuel_corrompu = api_reponse([
    resource(titre="finess-structures-mensuel-202608.json.gz", checksum="0" * 40)])
try:
    with mock.patch.object(urllib.request, "urlopen",
                           urlopen_pour(donnees_mensuel_corrompu, CONTENU_FICHIER)):
        tfs.executer(BASE / "mensuel_corrompu.json.gz", mensuel="202608")
    verifier("checksum du mensuel vérifié comme pour le journalier", False)
except tfs.ErreurTelechargement as erreur:
    verifier("checksum du mensuel vérifié comme pour le journalier",
             "Checksum divergent" in str(erreur), str(erreur))

print("7. CLI — --mensuel et --lister-mensuels")
dest7 = BASE / "cli_mensuel.json.gz"
if dest7.exists():
    dest7.unlink()
with mock.patch.object(urllib.request, "urlopen",
                       urlopen_pour(donnees_mensuels, CONTENU_FICHIER)):
    retour = tfs.main([str(dest7), "--mensuel", "202607"])
verifier("--mensuel publié → code 0", retour == 0)
with mock.patch.object(urllib.request, "urlopen",
                       urlopen_pour(donnees_mensuels, CONTENU_FICHIER)):
    retour = tfs.main([str(BASE / "cli_absent.json.gz"), "--mensuel", "202609"])
verifier("--mensuel non publié → code 1", retour == 1)
verifier("--mensuel non publié → aucun fichier écrit",
         not (BASE / "cli_absent.json.gz").exists())

sortie = io.StringIO()
with mock.patch.object(urllib.request, "urlopen",
                       urlopen_pour(donnees_mensuels, CONTENU_FICHIER)), \
        mock.patch.object(sys, "stdout", sortie):
    retour = tfs.main(["--lister-mensuels"])
verifier("--lister-mensuels → un millésime par ligne, croissants, code 0",
         retour == 0 and sortie.getvalue().split() == ["202607", "202608"],
         repr(sortie.getvalue()))
with mock.patch.object(urllib.request, "urlopen",
                       urlopen_pour(api_reponse([resource()]), CONTENU_FICHIER)):
    retour = tfs.main(["--lister-mensuels"])
verifier("--lister-mensuels sans aucun mensuel → code 1", retour == 1)

print(f"\n{ok} tests réussis, {ko} échecs")
sys.exit(1 if ko else 0)
