"""Agrégateur de la suite de tests (OOM-101).

Découvre dynamiquement `tests/test_*.py`, exécute chaque fichier dans un sous-processus
(même interpréteur, PYTHONPATH=src, PYTHONIOENCODING=utf-8, cwd = racine du dépôt) et
résume : fichiers passés, fichiers échoués, noms des échecs. Sort en 1 si au moins un
fichier échoue (code de retour non nul, y compris un plantage à l'import — D6), 0 sinon.

Chaque fichier reste exécutable seul ; ce script n'en modifie aucun.

    python tests/tout.py        # sortie des fichiers échoués seulement
    python tests/tout.py -v     # sortie de tous les fichiers
"""
import os
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_TESTS = RACINE / "tests"


def environnement_enfant():
    env = dict(os.environ)
    src = str(RACINE / "src")
    existant = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src + os.pathsep + existant if existant else src
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def executer(fichier, env):
    proc = subprocess.run(
        [sys.executable, str(fichier)],
        cwd=str(RACINE),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace")


def main(argv):
    # Console cp1252 sans PYTHONIOENCODING : ne pas planter sur un « → » relayé d'un enfant.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    verbeux = "-v" in argv
    fichiers = sorted(DOSSIER_TESTS.glob("test_*.py"))
    if not fichiers:
        print("Aucun fichier tests/test_*.py trouvé.")
        return 1

    env = environnement_enfant()
    passes, echecs = [], []
    for fichier in fichiers:
        code, sortie = executer(fichier, env)
        statut = "OK " if code == 0 else "KO "
        print("%s %s (code %d)" % (statut, fichier.name, code))
        if code != 0 or verbeux:
            print(sortie.rstrip())
            print("-" * 70)
        (passes if code == 0 else echecs).append(fichier.name)

    print()
    print("=" * 70)
    print("Fichiers passés : %d / %d" % (len(passes), len(fichiers)))
    print("Fichiers échoués : %d" % len(echecs))
    for nom in echecs:
        print("  - %s" % nom)
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
