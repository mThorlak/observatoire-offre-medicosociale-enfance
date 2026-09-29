"""maj_nomenclature_categories.py — Mise à jour du référentiel des catégories (OOM-118).

Régénère `referentiels/nomenclature_categorie_finess.csv` depuis la
nomenclature qui fait foi : ANS, NOS TRE_R66-CategorieEtablissement
(décision du 29/09/2026, cf. docs/08_SOURCES_DONNEES.md).

A rejouer à chaque nouvelle version de TRE_R66 :

    py -3 scripts/maj_nomenclature_categories.py            # télécharge et écrit
    py -3 scripts/maj_nomenclature_categories.py --verifier # compare, n'écrit rien
    py -3 scripts/maj_nomenclature_categories.py --fichier TRE_R66.tabs

Règles appliquées :
- chaque code de TRE_R66 porte son « Libellé long » verbatim ; `date_fermeture`
  = « Date fin » (AAAA-MM-JJ) ; `statut` = "fermee" si cette date est atteinte
  au jour de la consultation, "ouverte" sinon ;
- un code du référentiel actuel absent de TRE_R66 n'est jamais retiré : sa ligne
  est conservée telle quelle, avec son origine dans la colonne `source` ;
- le script ne porte aucun libellé (D4) : tous viennent du fichier téléchargé ou
  du référentiel existant. L'en-tête de provenance (version, OID, empreinte) est
  réécrit à chaque exécution (D5).

Le rapport imprime les libellés et dates modifiés, avant et après, ainsi que les
codes ajoutés et conservés hors source. Code de retour non nul si le fichier
source est malformé (D6), ou, avec --verifier, si le référentiel diffère.

Aucune dépendance tierce. Compatible Python 3.9+.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import sys
import urllib.request
from pathlib import Path

URL_TABS = ("https://mos.esante.gouv.fr/NOS/TRE_R66-CategorieEtablissement/"
            "TRE_R66-CategorieEtablissement.tabs")
OID = "1.2.250.1.213.1.6.1.8"
SOURCE_TRE = "ANS_TRE_R66"
COLONNES = ["code", "libelle", "statut", "date_fermeture", "source"]
RACINE = Path(__file__).resolve().parent.parent
REFERENTIEL = RACINE / "referentiels" / "nomenclature_categorie_finess.csv"


class ErreurSource(Exception):
    """Le fichier TRE_R66 n'a pas la forme attendue : rien n'est écrit."""


def telecharger(url: str = URL_TABS) -> bytes:
    requete = urllib.request.Request(url, headers={"User-Agent": "ooms-referentiel/1.0"})
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        return reponse.read()


def _date(aaaammjj: str) -> str:
    """`19990915000000` -> `1999-09-15` ; chaîne vide conservée."""
    if not aaaammjj:
        return ""
    if len(aaaammjj) < 8 or not aaaammjj[:8].isdigit():
        raise ErreurSource(f"date illisible : {aaaammjj!r}")
    return f"{aaaammjj[:4]}-{aaaammjj[4:6]}-{aaaammjj[6:8]}"


def lire_tabs(contenu: bytes) -> tuple[dict, dict]:
    """Analyse le fichier .tabs de TRE_R66.

    Retourne (entete, concepts) : `entete` porte la version (`date_maj`) et
    l'OID ; `concepts` associe chaque code à (libellé long, date fin).
    """
    lignes = contenu.decode("utf-8-sig").splitlines()
    if len(lignes) < 4 or not lignes[0].startswith("<OID>"):
        raise ErreurSource("en-tête .tabs absent ou inattendu")
    meta = lignes[1].split(";")
    noms = [c.strip() for c in lignes[2].split(";")]
    attendus = ["<OID>", "<Code>", "<Libellé adapté>", "<Libellé court>",
                "<Libellé long>", "<Date valid>", "<Date fin>", "<Date MàJ>"]
    if len(meta) != 8 or meta[0] != OID or noms != attendus:
        raise ErreurSource(f"structure .tabs inattendue : {meta[:1]} / {noms}")
    entete = {"oid": meta[0], "nom": meta[2], "date_maj": meta[7]}
    concepts: dict = {}
    for numero, ligne in enumerate(lignes[3:], start=4):
        if not ligne.strip():
            continue
        champs = ligne.split(";")
        if len(champs) != 8 or champs[0] != OID:
            raise ErreurSource(f"ligne {numero} malformée : {ligne!r}")
        code, libelle, date_fin = champs[1].strip(), champs[4].strip(), champs[6].strip()
        if not code or not libelle:
            raise ErreurSource(f"ligne {numero} : code ou libellé long vide")
        if code in concepts:
            raise ErreurSource(f"code {code!r} en double dans TRE_R66")
        concepts[code] = (libelle, _date(date_fin))
    if not concepts:
        raise ErreurSource("aucun concept dans le fichier")
    return entete, concepts


def lire_referentiel(chemin: Path) -> dict:
    """Lignes actuelles du référentiel, par code (en-tête `#` ignoré)."""
    if not chemin.exists():
        return {}
    with open(chemin, encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader((l for l in f if not l.startswith("#")), delimiter=";")
        return {ligne["code"].strip(): ligne for ligne in lecteur if (ligne.get("code") or "").strip()}


def construire(concepts: dict, actuel: dict, jour: str) -> list:
    """Lignes du nouveau référentiel : TRE_R66, plus les codes actuels hors TRE_R66."""
    lignes = []
    for code, (libelle, date_fin) in concepts.items():
        statut = "fermee" if date_fin and date_fin <= jour else "ouverte"
        lignes.append({"code": code, "libelle": libelle, "statut": statut,
                       "date_fermeture": date_fin, "source": SOURCE_TRE})
    for code, ligne in actuel.items():
        if code not in concepts:  # jamais retiré : ligne conservée, origine indiquée
            conservee = {c: (ligne.get(c) or "") for c in COLONNES}
            if not conservee["source"] or conservee["source"] == SOURCE_TRE:
                conservee["source"] = "hors_TRE_R66"
            lignes.append(conservee)
    return sorted(lignes, key=lambda l: l["code"])


def comparer(actuel: dict, lignes: list) -> dict:
    ecarts = {"libelles": [], "dates": [], "ajouts": [], "hors_source": []}
    for l in lignes:
        avant = actuel.get(l["code"])
        if l["source"] != SOURCE_TRE:
            ecarts["hors_source"].append(l)
        elif avant is None:
            ecarts["ajouts"].append(l)
        else:
            if avant["libelle"] != l["libelle"]:
                ecarts["libelles"].append((l["code"], avant["libelle"], l["libelle"]))
            if (avant["statut"], avant["date_fermeture"] or "") != (l["statut"], l["date_fermeture"]):
                ecarts["dates"].append((l["code"], f'{avant["statut"]} {avant["date_fermeture"] or "—"}',
                                        f'{l["statut"]} {l["date_fermeture"] or "—"}'))
    return ecarts


def entete(meta: dict, empreinte: str, jour: str, nb_tre: int, nb_total: int, nb_hors: int) -> str:
    return f"""# Référentiel — nomenclature des catégories d'établissements FINESS
# (domaine "categorie_etablissement", champ etablissement.code_categorie /
# entite_juridique.code_categorie du pivot ; source JSON FINESS :
# categorieentiteGeographiqueExercice).
#
# FICHIER GÉNÉRÉ par scripts/maj_nomenclature_categories.py : ne pas éditer à
# la main, rejouer le script à chaque nouvelle version de la source.
#
# Source qui fait foi (décision OOM-118 du 29/09/2026) :
#   Agence du Numérique en Santé, NOS (Nomenclatures des Objets de Santé),
#   {meta["nom"]}, OID {meta["oid"]},
#   version {meta["date_maj"]} ({nb_tre} codes) :
#   {URL_TABS}
#   Consultée le {jour} ; SHA-256 du fichier .tabs :
#   {empreinte}
#   libelle = colonne « Libellé long », verbatim ; date_fermeture = « Date fin »
#   (AAAA-MM-JJ) ; statut = "fermee" si cette date est atteinte au jour de la
#   consultation, "ouverte" sinon.
#
# Historique : 274 lignes venaient des PDF DREES/DMSI de 2021 (data.gouv.fr
# « FINESS - Extraction des principales nomenclatures », OOM-12), 40 de
# TRE_R66 (OOM-117). Depuis OOM-118, toutes les lignes présentes dans TRE_R66
# en portent le libellé et les dates. Aucun code n'est jamais retiré : un code
# du référentiel absent de la source garde sa ligne, son origine en colonne
# `source` ({nb_hors} ligne(s) dans ce cas). Couverture : {nb_total} codes.
# Un code observé hors référentiel reste signalé par
# nomenclatures.resoudre_categorie, jamais approximé (D6).
#
# Colonnes :
#   code            code catégorie FINESS, tel qu'émis par la source (aucun
#                   remplissage de zéros, aucune transformation).
#   libelle         libellé long officiel de la catégorie.
#   statut          "ouverte" ou "fermee" (voir ci-dessus). Une catégorie
#                   fermée peut subsister sur des établissements existants
#                   non encore requalifiés.
#   date_fermeture  « Date fin » de la source, vide si elle n'en donne pas.
#   source          {SOURCE_TRE} pour une ligne tirée de la source qui fait
#                   foi ; sinon l'origine de la ligne conservée.
"""


def ecrire(chemin: Path, texte_entete: str, lignes: list) -> None:
    tampon = io.StringIO()
    tampon.write(texte_entete)
    ecrivain = csv.DictWriter(tampon, fieldnames=COLONNES, delimiter=";", lineterminator="\n")
    ecrivain.writeheader()
    ecrivain.writerows(lignes)
    chemin.write_text(tampon.getvalue(), encoding="utf-8", newline="")


def imprimer(ecarts: dict) -> None:
    print(f"Libellés modifiés : {len(ecarts['libelles'])}")
    for code, avant, apres in ecarts["libelles"]:
        print(f"  {code} : {avant!r} -> {apres!r}")
    print(f"Statuts / dates de fin modifiés : {len(ecarts['dates'])}")
    for code, avant, apres in ecarts["dates"]:
        print(f"  {code} : {avant} -> {apres}")
    print(f"Codes ajoutés : {len(ecarts['ajouts'])}")
    for l in ecarts["ajouts"]:
        print(f"  {l['code']} : {l['libelle']!r} ({l['statut']} {l['date_fermeture'] or '—'})")
    print(f"Codes absents de la source, conservés : {len(ecarts['hors_source'])}")
    for l in ecarts["hors_source"]:
        print(f"  {l['code']} : {l['libelle']!r} (source {l['source']})")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fichier", type=Path, help="fichier .tabs local (sinon téléchargé)")
    parser.add_argument("--sortie", type=Path, default=REFERENTIEL)
    parser.add_argument("--jour", default=datetime.date.today().isoformat(),
                        help="date de consultation AAAA-MM-JJ (défaut : aujourd'hui)")
    parser.add_argument("--verifier", action="store_true",
                        help="n'écrit rien ; code 1 si le référentiel diffère de la source")
    args = parser.parse_args(argv)

    contenu = args.fichier.read_bytes() if args.fichier else telecharger()
    try:
        meta, concepts = lire_tabs(contenu)
    except ErreurSource as erreur:
        print(f"ERREUR source TRE_R66 : {erreur}", file=sys.stderr)
        return 2
    empreinte = hashlib.sha256(contenu).hexdigest()
    actuel = lire_referentiel(args.sortie)
    lignes = construire(concepts, actuel, args.jour)
    ecarts = comparer(actuel, lignes)

    print(f"TRE_R66 version {meta['date_maj']} : {len(concepts)} codes ; "
          f"référentiel actuel : {len(actuel)} codes ; nouveau : {len(lignes)} codes")
    imprimer(ecarts)
    retires = set(actuel) - {l["code"] for l in lignes}
    if retires:  # garde-fou : construire() ne doit jamais retirer un code
        print(f"ERREUR : codes retirés {sorted(retires)}", file=sys.stderr)
        return 2

    if args.verifier:
        a_jour = not any(ecarts[k] for k in ("libelles", "dates", "ajouts"))
        print("Référentiel à jour." if a_jour else "Référentiel à mettre à jour.")
        return 0 if a_jour else 1
    ecrire(args.sortie, entete(meta, empreinte, args.jour, len(concepts), len(lignes),
                               len(ecarts["hors_source"])), lignes)
    print(f"Écrit : {args.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
