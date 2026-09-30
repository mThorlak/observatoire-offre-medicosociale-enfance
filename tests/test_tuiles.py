"""test_tuiles.py — Critères d'OOM-111 vérifiables hors CI (archive PMTiles).

tippecanoe n'est pas installé localement (il est compilé par le workflow) : la
chaîne `scripts/tuiles.py generer` est exercée avec un faux tippecanoe, un
script Python qui lit le GeoJSON d'export_geo et écrit une archive PMTiles v3
synthétique (en-tête 127 octets, métadonnées gzip, `tilestats`). Vérifie :

1. paramètres versionnés : couche `etablissements`, zooms, propriétés du
   contrat C (ni plus ni moins), version épinglée par tag ET commit ;
   arguments identiques à paramètres et millésime égaux ;
2. de bout en bout sur l'échantillon : GeoJSON écrit hors de `site/`, archive
   recopiée dans `site/tuiles/` seulement après contrôle, compteurs
   d'export_geo et empreinte dans le résumé, deux générations = même empreinte ;
3. échecs bloquants (D6), destination jamais créée ni modifiée : archive au-delà
   du plafond, tronquée, points perdus, couche ou propriété absente, tippecanoe
   en échec ou introuvable, fichier qui n'est pas du PMTiles.
"""
from __future__ import annotations
import gzip, json, os, struct, subprocess, sys, tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))
sys.path.insert(0, str(RACINE / "scripts"))

from chargement import charger
from contrat_source import CONTROLE_MINIMAL
from entrepot import Entrepot
from finess_activites import SourceFinessActivites
from finess_structures import SourceFinessStructures
import tuiles as tu

ECHANTILLON = RACINE / "tests" / "echantillon"
S = ECHANTILLON / "finess-structures-mensuel-202607-echantillon_json.gz"
A = ECHANTILLON / "finess-activites-mensuel-202607-echantillon_json.gz"
PROPRIETES = {"finess", "nom", "categorie", "dep", "lien", "score_ban", "etat"}

ok = ko = 0


def verifier(intitule, condition, detail=""):
    global ok, ko
    if condition: ok += 1; print(f"  OK    {intitule}")
    else: ko += 1; print(f"  ECHEC {intitule} — {detail}")


def pmtiles(metadonnees, tuiles=b"\x1f\x8btuiles", tronquer=0, signature=b"PMTiles",
            type_tuiles=1):
    """Archive PMTiles v3 minimale : en-tête, répertoire racine, métadonnées
    gzip, données de tuiles."""
    racine = b"\x01\x00\x01\x08\x00"
    meta = gzip.compress(json.dumps(metadonnees).encode("utf-8"), mtime=0)
    o_racine = tu.TAILLE_ENTETE
    o_meta = o_racine + len(racine)
    o_tuiles = o_meta + len(meta)
    entete = struct.pack(tu._FORMAT_ENTETE, signature, 3,
                         o_racine, len(racine), o_meta, len(meta), o_tuiles, 0,
                         o_tuiles, len(tuiles), 1, 1, 1,
                         1, 2, 2, type_tuiles, 0, 14,
                         -50000000, 400000000, 100000000, 520000000, 5, 20000000, 460000000)
    assert len(entete) == tu.TAILLE_ENTETE
    octets = entete + racine + meta + tuiles
    return octets[:len(octets) - tronquer] if tronquer else octets


def metadonnees(points, couche=tu.COUCHE, champs=PROPRIETES):
    return {"generator": "faux-tippecanoe",
            "vector_layers": [{"id": couche, "fields": {c: "String" for c in sorted(champs)}}],
            "tilestats": {"layerCount": 1, "layers": [{"layer": couche, "count": points}]}}


FAUX = r'''
import sys
sys.path.insert(0, sys.argv[1])
from test_tuiles_faux import ecrire
ecrire(sys.argv[2:])
'''

MODULE_FAUX = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ["RACINE_TESTS"])
from test_tuiles import pmtiles, metadonnees, PROPRIETES

def ecrire(arguments):
    Path(os.environ["JOURNAL_FAUX"]).write_text(json.dumps(arguments), encoding="utf-8")
    mode = os.environ.get("MODE_FAUX", "ok")
    if mode == "echec":
        sys.exit(3)
    sortie = next(a.split("=", 1)[1] for a in arguments if a.startswith("--output="))
    with open(arguments[-1], encoding="utf-8") as f:
        points = len(json.load(f)["features"])
    if mode == "silence":
        return
    champs = PROPRIETES - {"lien"} if mode == "champ" else PROPRIETES
    couche = "autre" if mode == "couche" else "etablissements"
    octets = pmtiles(metadonnees(points - (mode == "perdu"), couche, champs),
                     tuiles=b"x" * (5000 if mode == "lourd" else 10),
                     tronquer=7 if mode == "tronque" else 0)
    Path(sortie).write_bytes(octets)
'''

if __name__ == "__main__":
    # -----------------------------------------------------------------------
    print("1. Paramètres versionnés")
    args = tu.arguments_tippecanoe("t/e.geojson", "t/e.pmtiles", "202607")
    inclus = {a.split("=", 1)[1] for a in args if a.startswith("--include=")}
    verifier("propriétés conservées = contrat C, ni plus ni moins", inclus == PROPRIETES, inclus)
    verifier("couche etablissements", "--layer=etablissements" in args)
    verifier("zooms versionnés", f"--minimum-zoom={tu.ZOOM_MIN}" in args
             and f"--maximum-zoom={tu.ZOOM_MAX}" in args)
    verifier("éclaircissement des petits zooms versionné", "--drop-densest-as-needed" in args)
    verifier("entrée en dernier, sortie explicite",
             args[-1] == "t/e.geojson" and "--output=t/e.pmtiles" in args)
    verifier("mêmes paramètres et millésime → mêmes arguments",
             args == tu.arguments_tippecanoe("t/e.geojson", "t/e.pmtiles", "202607"))
    verifier("aucun argument de lecture parallèle (ordre d'entrée non déterministe)",
             not any(a in ("-P", "--read-parallel") for a in args))
    verifier("tippecanoe épinglé par tag et commit complet",
             tu.TIPPECANOE_VERSION.count(".") == 2 and len(tu.TIPPECANOE_COMMIT) == 40
             and all(c in "0123456789abcdef" for c in tu.TIPPECANOE_COMMIT))
    verifier("plafond sous les 100 Mio d'un fichier Pages", tu.PLAFOND_OCTETS <= 100 * 1024 * 1024)
    sortie = subprocess.run([sys.executable, str(RACINE / "scripts" / "tuiles.py"), "version"],
                            capture_output=True, text=True)
    verifier("`tuiles.py version` donne tag et commit",
             sortie.stdout.split() == [tu.TIPPECANOE_VERSION, tu.TIPPECANOE_COMMIT], sortie)

    with tempfile.TemporaryDirectory(prefix="test_tuiles_") as temporaire:
        TMP = Path(temporaire)
        (TMP / "test_tuiles_faux.py").write_text(MODULE_FAUX, encoding="utf-8")
        (TMP / "faux.py").write_text(FAUX, encoding="utf-8")
        faux = (sys.executable, str(TMP / "faux.py"), str(TMP))
        os.environ["RACINE_TESTS"] = str(RACINE / "tests")
        os.environ["JOURNAL_FAUX"] = str(TMP / "journal.json")

        base = TMP / "echantillon.db"
        with Entrepot(base) as e:
            e.creer()
            charger(e, SourceFinessStructures(), S, controle=CONTROLE_MINIMAL)
            charger(e, SourceFinessActivites(), A, controle=CONTROLE_MINIMAL)

        # -------------------------------------------------------------------
        print("\n2. De bout en bout sur l'échantillon (faux tippecanoe)")
        os.environ["MODE_FAUX"] = "ok"
        travail, site = TMP / "travail", TMP / "site"
        publiee = site / "tuiles" / tu.NOM_ARCHIVE
        bilan = tu.generer(base, travail, publiee, tippecanoe=faux)
        geo, archive = bilan["geo"], bilan["archive"]
        verifier("GeoJSON écrit hors de site/", (travail / tu.NOM_GEOJSON).is_file()
                 and not list(site.rglob("*.geojson")))
        verifier("archive publiée sous site/tuiles/etablissements.pmtiles", publiee.is_file())
        verifier("archive publiée = archive contrôlée",
                 publiee.read_bytes() == (travail / tu.NOM_ARCHIVE).read_bytes())
        verifier("points de l'archive = localisés d'export_geo (1 141 sur l'échantillon)",
                 archive["points"] == geo["localises"] == 1141, (archive, geo["localises"]))
        verifier("Lambert 93 de l'échantillon compté à part (coordonnees_invalides = 1)",
                 geo["coordonnees_invalides"] == 1, geo["coordonnees_invalides"])
        appel = json.loads((TMP / "journal.json").read_text(encoding="utf-8"))
        verifier("tippecanoe appelé avec les paramètres versionnés",
                 appel == tu.arguments_tippecanoe((travail / tu.NOM_GEOJSON).as_posix(),
                                                  (travail / tu.NOM_ARCHIVE).as_posix(),
                                                  "202607"), appel)
        texte = tu.resume_markdown(bilan)
        verifier("résumé : taille, empreinte, points et compteurs d'export_geo",
                 all(str(v) in texte for v in (archive["octets"], archive["sha256"],
                                               archive["points"], geo["sans_coordonnees"],
                                               geo["coordonnees_invalides"])))
        bis = tu.generer(base, TMP / "travail2", TMP / "site2" / "tuiles" / tu.NOM_ARCHIVE,
                         tippecanoe=faux)
        verifier("deux générations à millésime égal : même empreinte du GeoJSON et de "
                 "l'archive",
                 (travail / tu.NOM_GEOJSON).read_bytes()
                 == (TMP / "travail2" / tu.NOM_GEOJSON).read_bytes()
                 and bis["archive"]["sha256"] == archive["sha256"])
        controle = tu.verifier_archive(publiee, points_attendus=1141)
        verifier("`verifier` relit l'archive publiée", controle["sha256"] == archive["sha256"])

        # -------------------------------------------------------------------
        print("\n3. Échecs bloquants : destination jamais créée ni modifiée (D6)")
        publiee.write_bytes(b"ancienne")

        def echoue(intitule, mode, attendu, plafond=tu.PLAFOND_OCTETS):
            os.environ["MODE_FAUX"] = mode
            try:
                tu.generer(base, travail, publiee, tippecanoe=faux, plafond=plafond)
            except tu.ErreurTuiles as erreur:
                verifier(f"{intitule} : ErreurTuiles", attendu in str(erreur), str(erreur))
            else:
                verifier(f"{intitule} : ErreurTuiles", False, "aucune erreur levée")
            verifier(f"{intitule} : archive publiée intacte, aucun .partiel",
                     publiee.read_bytes() == b"ancienne"
                     and not list(publiee.parent.glob("*.partiel")))

        echoue("archive au-delà du plafond", "lourd", "au-delà du plafond", plafond=4000)
        echoue("archive tronquée", "tronque", "tronquée")
        echoue("points perdus entre GeoJSON et archive", "perdu", "1140 point(s)")
        echoue("couche absente", "couche", "couche 'etablissements' absente")
        echoue("propriété du contrat C absente", "champ", "['lien']")
        echoue("tippecanoe en échec", "echec", "code 3")
        echoue("tippecanoe sans archive", "silence", "n'a pas écrit")
        try:
            tu.generer(base, travail, publiee, tippecanoe=(str(TMP / "absent"),))
            verifier("tippecanoe introuvable : ErreurTuiles", False, "aucune erreur")
        except tu.ErreurTuiles as erreur:
            verifier("tippecanoe introuvable : ErreurTuiles", "introuvable" in str(erreur))
        try:
            tu.generer(TMP / "absente.db", travail, publiee, tippecanoe=faux)
            verifier("entrepôt absent : ErreurTuiles", False)
        except tu.ErreurTuiles:
            verifier("entrepôt absent : ErreurTuiles", True)
        verifier("après tous les échecs : archive publiée intacte",
                 publiee.read_bytes() == b"ancienne")

        faux_fichier = TMP / "pas.pmtiles"
        for intitule, octets, attendu in (
                ("signature", pmtiles(metadonnees(3), signature=b"PMTilez"), "signature"),
                ("fichier trop court", b"PMTiles\x03", "moins que l'en-tête"),
                ("tuiles non vectorielles", pmtiles(metadonnees(3), type_tuiles=2), "MVT"),
                ("tilestats absent", pmtiles({"vector_layers": metadonnees(3)["vector_layers"]}),
                 "tilestats")):
            faux_fichier.write_bytes(octets)
            try:
                tu.verifier_archive(faux_fichier)
                verifier(f"verifier_archive refuse : {intitule}", False, "accepté")
            except tu.ErreurTuiles as erreur:
                verifier(f"verifier_archive refuse : {intitule}", attendu in str(erreur),
                         str(erreur))
        faux_fichier.write_bytes(pmtiles(metadonnees(3)))
        cli = subprocess.run([sys.executable, str(RACINE / "scripts" / "tuiles.py"), "verifier",
                              str(faux_fichier), "--points", "4"], capture_output=True, text=True,
                             env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        verifier("CLI verifier : code 1 et message sur un écart de points",
                 cli.returncode == 1 and "3 point(s)" in cli.stderr, cli)
        cli = subprocess.run([sys.executable, str(RACINE / "scripts" / "tuiles.py"), "generer",
                              str(base), "--travail", str(TMP / "t4"), "--archive",
                              str(TMP / "s4" / "e.pmtiles"), "--tippecanoe",
                              str(TMP / "absent")], capture_output=True, text=True,
                             env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        verifier("CLI generer : code 1, rien de publié",
                 cli.returncode == 1 and not (TMP / "s4").exists(), cli)

    print(f"\n{ok} OK, {ko} ÉCHEC(s)")
    sys.exit(1 if ko else 0)
