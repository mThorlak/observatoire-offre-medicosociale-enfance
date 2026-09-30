"""test_export_geo.py — Critères de sortie d'OOM-110 (GeoJSON des établissements,
contrat C).

Vérifie `export_geo.exporter` :

1. de bout en bout sur l'échantillon FINESS versionné, chargé dans un dossier
   temporaire : GeoJSON RFC 7946 (FeatureCollection de Point, coordonnées
   `[longitude, latitude]` = `[coordonnee_x, coordonnee_y]`, jamais les
   `direction_*`), un point par établissement localisé, compteurs attendus
   (voir ÉCHANTILLON ci-dessous), établissements sans coordonnées exclus et
   comptés, propriétés du contrat C ; le `lien` de chaque point comparé à un
   rendu réel d'`export_html` (borne réduite, plusieurs sous-pages, puis
   borne par défaut) : la sous-page désignée porte bien l'établissement ;
2. invariants (D6) : `localises + non_localises = total`, somme de
   `par_departement` = total ;
3. cas synthétiques : département hors référentiel (`975`) et commune
   illisible en `indetermine`, adresse absente, coordonnées illisibles ou hors
   WGS84, score BAN non numérique gardé brut ;
4. échecs bloquants : entrepôt non ouvert, vide, borne invalide, lecture
   incomplète — `ErreurExportGeo`, fichier existant intact, aucun résidu ;
5. stdlib seule, écriture en flux (D1) — par inspection du module.

ÉCHANTILLON — la note d'OOM-110 annonçait « 2 000 adresses d'établissement,
dont 1 142 localisées et 858 exclues ». Ces chiffres comptent les adresses,
secondaires ('04', '06') comprises ; le contrat C est au niveau établissement
(adresse principale '03') : 1 753 établissements, 1 142 avec coordonnées, dont
une (010002285) porte du Lambert 93 dans `coordonnee_*` — hors WGS84, donc
exclue et comptée. D'où 1 141 localisés et 612 exclus. Le test vérifie cette
décomposition sur l'entrepôt plutôt que de poser les chiffres en dur seuls.
"""
from __future__ import annotations
import ast, json, math, re, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import finess_commun as fc
from chargement import charger
from contrat_source import CONTROLE_MINIMAL
from entrepot import Entrepot
from finess_activites import SourceFinessActivites
from finess_structures import SourceFinessStructures
from territoires import charger_departements
import export_geo as eg
import export_html as eh

ECHANTILLON = Path(__file__).resolve().parent / "echantillon"
S = ECHANTILLON / "finess-structures-mensuel-202607-echantillon_json.gz"
A = ECHANTILLON / "finess-activites-mensuel-202607-echantillon_json.gz"
SOURCE = Path(__file__).resolve().parent.parent / "src" / "export_geo.py"
DEPARTEMENTS = charger_departements()
BORNE = 100  # comme test_export_html : 44 et 01 tiennent en plusieurs sous-pages
PROPRIETES = {"finess", "nom", "categorie", "dep", "lien", "score_ban", "etat"}
LAMBERT = "010002285"  # coordonnee_* en Lambert 93 dans l'échantillon
# Une ligne de sous-page, dont l'ancre (OOM-113) est celle de son numéro FINESS.
_LIGNE = re.compile(r'<tr id="et-([^"]*)" data-cat="[^"]*" data-etat="[^"]*"><td>\1</td>')

ok = ko = 0


def verifier(intitule, condition, detail=""):
    global ok, ko
    if condition: ok += 1; print(f"  OK    {intitule}")
    else: ko += 1; print(f"  ECHEC {intitule} — {detail}")


def refuser_constante(nom):
    raise ValueError(f"constante JSON non standard : {nom}")


def lire_geojson(chemin):
    # NaN/Infinity refusés : ils ne sont pas du JSON (RFC 8259), donc pas du GeoJSON.
    with open(chemin, encoding="utf-8") as f:
        return json.load(f, parse_constant=refuser_constante)


def lignes_des_sous_pages(site, bilan):
    """{chemin de sous-page: [num_finess rendus]} lus dans le HTML écrit."""
    return {eh.chemin_sous_page(code, n): _LIGNE.findall(
                (site / eh.chemin_sous_page(code, n)).read_text(encoding="utf-8"))
            for code, effectifs in bilan["sous_pages_departement"].items()
            for n in range(1, len(effectifs) + 1)}


def verifier_liens(intitule, geo, site, bilan):
    rendues = lignes_des_sous_pages(site, bilan)
    sous_page_de = {num: page for page, nums in rendues.items() for num in nums}
    fautifs = [(f["properties"]["finess"], f["properties"]["lien"])
               for f in geo["features"]
               if f["properties"]["lien"].split("#")[0] != sous_page_de.get(
                   f["properties"]["finess"])]
    verifier(f"{intitule} : chaque lien désigne la sous-page que le rendu écrit pour "
             f"l'établissement", not fautifs, fautifs[:3])
    verifier(f"{intitule} : ancre #et-<finess>",
             all(f["properties"]["lien"].endswith("#et-" + f["properties"]["finess"])
                 for f in geo["features"]))
    return rendues


_TYPES = {t.nom: t for t in fc.TOUS_LES_TYPES}


def inserer(connexion, table, **valeurs):
    colonnes = _TYPES[table].noms
    connexion.execute(
        f"INSERT INTO {table} ({','.join(colonnes)}) VALUES ({','.join('?' for _ in colonnes)})",
        tuple(valeurs.get(c) for c in colonnes))


LOT = dict(id_lot="l:202607:0000", source="finess_structures", millesime="202607",
           schema_version="v1.0.0", nom_fichier="f", empreinte="e", octets="1")
EJ = dict(num_finess_ej="010008400", pm_smsse_id="100", denomination="A",
          denomination_longue="A LONGUE", code_statut_juridique="60",
          code_type_personne_morale="1", date_creation="1980-01-01",
          etat_objet="A", date_derniere_maj="2026-01-01", id_lot=LOT["id_lot"])


def etablissement(num, ege_id, etat="A"):
    return dict(num_finess_et=num, ege_id=ege_id, num_finess_ej=EJ["num_finess_ej"],
                pm_smsse_id=EJ["pm_smsse_id"], nom_court="", nom_long=f"ET {num}",
                code_categorie="183", date_ouverture="1990-01-01", etat_objet=etat,
                date_derniere_maj="2026-01-01", id_lot=LOT["id_lot"])


def adresse(ege_id, cog, x=None, y=None, score=None, usage="03", rang="1"):
    return dict(type_porteur="ET", id_porteur=ege_id, num_finess_porteur=ege_id, rang=rang,
                code_usage_adresse=usage, code_postal="01000", cog_commune=cog,
                coordonnee_x=x, coordonnee_y=y, score_ban=score, id_lot=LOT["id_lot"])


with tempfile.TemporaryDirectory(prefix="test_export_geo_") as temporaire:
    TMP = Path(temporaire)

    # -----------------------------------------------------------------------
    print("1. Échantillon versionné : GeoJSON, compteurs, liens comparés au rendu")
    sortie = TMP / "geo" / "etablissements.geojson"
    sortie_defaut = TMP / "etablissements_defaut.geojson"
    with Entrepot(TMP / "echantillon.db") as e:
        e.creer()
        charger(e, SourceFinessStructures(), S, controle=CONTROLE_MINIMAL)
        charger(e, SourceFinessActivites(), A, controle=CONTROLE_MINIMAL)
        bilan = eg.exporter(e, sortie, lignes_par_sous_page=BORNE)
        bilan_defaut = eg.exporter(e, sortie_defaut)
        rendu = eh.rendre(e, eh.DOSSIER_GABARITS, TMP / "site", lignes_par_sous_page=BORNE)
        rendu_defaut = eh.rendre(e, eh.DOSSIER_GABARITS, TMP / "site_defaut")
        cadres = eg.emprises(e, DEPARTEMENTS)

        c = e.connexion
        nb_et = c.execute("SELECT COUNT(*) FROM etablissement").fetchone()[0]
        adresses_et = c.execute("SELECT COUNT(*), SUM(coordonnee_x IS NOT NULL) FROM adresse "
                                "WHERE type_porteur = 'ET'").fetchone()
        principales = c.execute(
            "SELECT e.num_finess_et, a.coordonnee_x, a.coordonnee_y, a.direction_longitude, "
            "a.direction_latitude FROM etablissement e JOIN adresse a ON a.type_porteur = 'ET' "
            "AND a.id_porteur = e.ege_id AND a.code_usage_adresse = '03'").fetchall()
        brut = {n: (x, y, dx, dy) for n, x, y, dx, dy in principales}
        etats = dict(c.execute("SELECT num_finess_et, etat_objet FROM etablissement"))
        categories = dict(c.execute("SELECT num_finess_et, code_categorie FROM etablissement"))

    geo = lire_geojson(sortie)
    points = geo["features"]
    print("   (note du ticket : 2 000 adresses ET dont 1 142 localisées — voir ÉCHANTILLON)")
    verifier("échantillon : 2 000 adresses ET, 1 142 avec coordonnées (chiffres de la note)",
             tuple(adresses_et) == (2000, 1142), adresses_et)
    verifier("échantillon : 1 753 établissements, une adresse principale chacun, "
             "1 142 avec coordonnées",
             nb_et == 1753 and len(brut) == 1753
             and sum(1 for v in brut.values() if v[0] is not None) == 1142, (nb_et, len(brut)))
    verifier(f"échantillon : {LAMBERT} a du Lambert 93 dans coordonnee_* (hors WGS84)",
             float(brut[LAMBERT][0]) > 180 and float(brut[LAMBERT][1]) > 90, brut[LAMBERT])
    verifier("compteurs : 1 753 = 1 141 localisés + 612 exclus (611 sans, 1 hors WGS84)",
             (bilan["total"], bilan["localises"], bilan["non_localises"],
              bilan["sans_coordonnees"], bilan["coordonnees_invalides"])
             == (1753, 1141, 612, 611, 1), bilan)
    verifier("millésime retourné et écrit (membre étranger, D5)",
             bilan["millesime"] == "202607" and geo.get("millesime") == "202607")
    verifier("octets retournés = taille du fichier", bilan["octets"] == sortie.stat().st_size)

    print("\n   RFC 7946")
    verifier("FeatureCollection, sans membre crs (WGS84 implicite)",
             geo["type"] == "FeatureCollection" and "crs" not in geo
             and isinstance(points, list))
    verifier("un Feature par établissement localisé",
             len(points) == bilan["localises"]
             and len({p["properties"]["finess"] for p in points}) == len(points))
    verifier("chaque géométrie : Point, deux nombres finis dans [-180,180] × [-90,90]",
             all(p["type"] == "Feature" and p["geometry"]["type"] == "Point"
                 and len(p["geometry"]["coordinates"]) == 2
                 and all(isinstance(v, float) and math.isfinite(v)
                         for v in p["geometry"]["coordinates"])
                 and -180 <= p["geometry"]["coordinates"][0] <= 180
                 and -90 <= p["geometry"]["coordinates"][1] <= 90 for p in points))
    decalees = [p["properties"]["finess"] for p in points
                if p["geometry"]["coordinates"] != [float(brut[p["properties"]["finess"]][0]),
                                                    float(brut[p["properties"]["finess"]][1])]]
    verifier("[longitude, latitude] = [coordonnee_x, coordonnee_y] de l'adresse principale",
             not decalees, decalees[:3])
    verifier("jamais les direction_* (Lambert 93)",
             all(p["geometry"]["coordinates"][0] != float(brut[p["properties"]["finess"]][2])
                 for p in points if brut[p["properties"]["finess"]][2] is not None))
    premier = points[0]["geometry"]["coordinates"]
    verifier("ordre [longitude, latitude] : premier point dans l'Ain (lon ≈ 5, lat ≈ 46)",
             4 < premier[0] < 7 and 45 < premier[1] < 47, premier)

    print("\n   exclusions (D6)")
    attendus = {n for n, v in brut.items() if v[0] is not None and n != LAMBERT}
    verifier("points = établissements aux coordonnées WGS84 valides, rien d'autre",
             {p["properties"]["finess"] for p in points} == attendus)
    verifier(f"{LAMBERT} exclu, jamais « réparé » depuis ses direction_*",
             LAMBERT not in {p["properties"]["finess"] for p in points})
    verifier("aucun point à une position par défaut ([0, 0])",
             all(p["geometry"]["coordinates"] != [0.0, 0.0] for p in points))

    print("\n   propriétés du contrat C")
    verifier("exactement finess, nom, categorie, dep, lien, score_ban, etat",
             all(set(p["properties"]) == PROPRIETES for p in points))
    verifier("categorie = code brut de l'entrepôt",
             all(p["properties"]["categorie"] == categories[p["properties"]["finess"]]
                 for p in points))
    verifier("etat : « actif » ssi etat_objet = A, « fermé » sinon ; les deux présents",
             all(p["properties"]["etat"] == ("actif" if etats[p["properties"]["finess"]] == "A"
                                             else "fermé") for p in points)
             and {p["properties"]["etat"] for p in points} == {"actif", "fermé"})
    verifier("dep : texte, du référentiel ou « indetermine »",
             all(isinstance(p["properties"]["dep"], str)
                 and (p["properties"]["dep"] in DEPARTEMENTS
                      or p["properties"]["dep"] == eh.PAGE_INDETERMINEE) for p in points))
    verifier("score_ban : nombre sur l'échantillon",
             all(isinstance(p["properties"]["score_ban"], float) for p in points))
    verifier("nom renseigné", all(p["properties"]["nom"] for p in points))

    print("\n   liens comparés au rendu d'export_html")
    rendues = verifier_liens(f"borne {BORNE}", geo, TMP / "site", rendu)
    verifier(f"borne {BORNE} : des liens au-delà de la sous-page 1 (01, 44)",
             any(p["properties"]["lien"].startswith("departement/44/3.html") for p in points)
             and any(p["properties"]["lien"].startswith("departement/01/2.html")
                     for p in points))
    verifier("le rendu compte les mêmes établissements que le GeoJSON (total)",
             sum(len(n) for n in rendues.values()) == bilan["total"])
    geo_defaut = lire_geojson(sortie_defaut)
    verifier_liens("borne par défaut", geo_defaut, TMP / "site_defaut", rendu_defaut)
    verifier("borne par défaut = LIGNES_PAR_SOUS_PAGE d'export_html",
             bilan_defaut["lignes_par_sous_page"] == eh.LIGNES_PAR_SOUS_PAGE)

    # -----------------------------------------------------------------------
    print("\n2. Invariants (D6)")
    for nom, b in (("borne 100", bilan), ("borne par défaut", bilan_defaut)):
        verifier(f"{nom} : localises + non_localises = total",
                 b["localises"] + b["non_localises"] == b["total"])
        verifier(f"{nom} : somme de par_departement = total",
                 sum(v["localises"] + v["non_localises"] for v in b["par_departement"].values())
                 == b["total"])
    verifier("par_departement : 101 départements du référentiel + indetermine, même vides",
             list(bilan["par_departement"]) == list(DEPARTEMENTS) + [eh.PAGE_INDETERMINEE])
    verifier("par_departement[dep].localises = points de ce dep",
             all(v["localises"] == sum(1 for p in points if p["properties"]["dep"] == d)
                 for d, v in bilan["par_departement"].items()))
    verifier("par_departement = effectif de la page départementale du rendu",
             all(v["localises"] + v["non_localises"] == rendu["pages_departement"][d]
                 for d, v in bilan["par_departement"].items()))

    # Emprises (OOM-113) : mêmes points que le GeoJSON, regroupés par dep.
    attendues = {}
    for p in points:
        x, y = p["geometry"]["coordinates"]
        r = attendues.setdefault(p["properties"]["dep"], [x, y, x, y])
        attendues[p["properties"]["dep"]] = [min(r[0], x), min(r[1], y), max(r[2], x), max(r[3], y)]
    verifier("emprises : 101 départements + indetermine, localisés = par_departement, rectangle "
             "englobant des points du GeoJSON, None sans point",
             list(cadres) == list(DEPARTEMENTS) + [eh.PAGE_INDETERMINEE]
             and all(v["localises"] == bilan["par_departement"][d]["localises"]
                     and v["emprise"] == attendues.get(d) for d, v in cadres.items()),
             [(d, v, attendues.get(d)) for d, v in cadres.items()
              if v["emprise"] != attendues.get(d)][:2])

    # -----------------------------------------------------------------------
    print("\n3. Cas synthétiques : indéterminés, coordonnées absentes ou invalides")
    synth = TMP / "synthetique.geojson"
    with Entrepot(TMP / "synthetique.db") as e:
        e.creer()
        c = e.connexion
        inserer(c, "entete", **LOT)
        inserer(c, "entite_juridique", **EJ)
        cas = [  # num, ege, cog, x, y, score
            ("010000001", "G1", "01053", "5.2", "46.2", "0.9"),
            ("010000002", "G2", "01053", None, None, None),
            ("010000003", "G3", "01053", "abc", "46.2", None),
            ("010000004", "G4", "01053", "5.2", "nan", None),
            ("010000005", "G5", "01053", "5.2", "46.2", "inconnu"),
            ("970000006", "G6", "97502", "-56.18", "46.78", None),   # 975 : hors référentiel
            ("010000007", "G7", "ABCDE", "5.2", "46.2", None),       # commune illisible
            ("2A0000008", "G8", "2A004", "8.73", "41.92", None),
        ]
        for num, ege, cog, x, y, score in cas:
            inserer(c, "etablissement", **etablissement(num, ege, etat="I" if ege == "G8" else "A"))
            inserer(c, "adresse", **adresse(ege, cog, x, y, score))
        inserer(c, "etablissement", **etablissement("010000009", "G9"))  # sans adresse
        inserer(c, "adresse", **adresse("G9", "01053", "5.2", "46.2", usage="04"))
        b = eg.exporter(e, synth)
        rendu_synth = eh.rendre(e, eh.DOSSIER_GABARITS, TMP / "site_synth")
    g = {p["properties"]["finess"]: p for p in lire_geojson(synth)["features"]}
    verifier("compteurs : 9 = 5 localisés + 4 exclus (2 sans, 2 invalides)",
             (b["total"], b["localises"], b["non_localises"], b["sans_coordonnees"],
              b["coordonnees_invalides"]) == (9, 5, 4, 2, 2), b)
    verifier("exclus : sans coordonnées, x illisible, y NaN, sans adresse principale "
             "(l'adresse '04' localisée n'est pas prise)",
             not {"010000002", "010000003", "010000004", "010000009"} & set(g))
    verifier("975 → dep indetermine, lien vers la page indéterminée",
             g["970000006"]["properties"]["dep"] == "indetermine"
             and g["970000006"]["properties"]["lien"]
             == "departement/indetermine/1.html#et-970000006", g.get("970000006"))
    verifier("commune illisible → indetermine",
             g["010000007"]["properties"]["dep"] == "indetermine")
    verifier("Corse : dep « 2A » en texte, état fermé",
             g["2A0000008"]["properties"]["dep"] == "2A"
             and g["2A0000008"]["properties"]["lien"] == "departement/2A/1.html#et-2A0000008"
             and g["2A0000008"]["properties"]["etat"] == "fermé")
    verifier("score BAN : nombre, ou texte brut s'il ne se lit pas, None s'il manque",
             g["010000001"]["properties"]["score_ban"] == 0.9
             and g["010000005"]["properties"]["score_ban"] == "inconnu"
             and g["2A0000008"]["properties"]["score_ban"] is None)
    verifier("nom : à défaut du nom court, le nom long",
             g["010000001"]["properties"]["nom"] == "ET 010000001")
    verifier("indetermine : 2 localisés, 1 exclu (sans adresse principale, donc sans "
             "commune) ; 01 : 2 localisés, 3 exclus",
             b["par_departement"]["indetermine"] == {"localises": 2, "non_localises": 1}
             and b["par_departement"]["01"] == {"localises": 2, "non_localises": 3},
             (b["par_departement"]["indetermine"], b["par_departement"]["01"]))
    verifier("cas synthétiques : liens = sous-pages du rendu (exclus compris dans le rang)",
             all(p["properties"]["lien"].split("#")[0] in lignes_des_sous_pages(
                 TMP / "site_synth", rendu_synth)
                 and p["properties"]["finess"] in lignes_des_sous_pages(
                     TMP / "site_synth", rendu_synth)[p["properties"]["lien"].split("#")[0]]
                 for p in g.values()))

    # -----------------------------------------------------------------------
    print("\n4. Échecs bloquants")
    intact = TMP / "intact.geojson"
    intact.write_text("ancien", encoding="utf-8")

    def echoue(intitule, appel, motif):
        try:
            appel()
            verifier(intitule, False, "aucune exception")
        except eg.ErreurExportGeo as erreur:
            verifier(intitule, motif in str(erreur), str(erreur))

    echoue("entrepôt non ouvert", lambda: eg.exporter(Entrepot(TMP / "x.db"), intact),
           "non ouvert")
    with Entrepot(TMP / "vide.db") as e:
        e.creer()
        echoue("entrepôt vide", lambda: eg.exporter(e, intact), "vide")
    with Entrepot(TMP / "echantillon.db") as e:
        echoue("borne invalide", lambda: eg.exporter(e, intact, lignes_par_sous_page=0),
               "borne")
        requete = eg._REQUETE
        eg._REQUETE = requete + " LIMIT 5"  # une lecture qui perdrait des établissements
        try:
            echoue("lecture incomplète : invariant total = table etablissement",
                   lambda: eg.exporter(e, intact), "lecture incohérente")
        finally:
            eg._REQUETE = requete
    verifier("après chaque échec : fichier existant intact, aucun .partiel",
             intact.read_text(encoding="utf-8") == "ancien"
             and not list(TMP.glob("*.partiel")))

    # -----------------------------------------------------------------------
    print("\n5. Stdlib seule, écriture en flux (D1)")
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    modules = {(n.module if isinstance(n, ast.ImportFrom) else a.name).split(".")[0]
               for n in ast.walk(arbre) if isinstance(n, (ast.Import, ast.ImportFrom))
               for a in (n.names if isinstance(n, ast.Import) else [n])}
    locaux = {p.stem for p in SOURCE.parent.glob("*.py")}
    stdlib = getattr(sys, "stdlib_module_names",
                     {"__future__", "argparse", "json", "math", "os", "pathlib", "sys",
                      "typing"})
    verifier("imports : stdlib ou modules de src/", modules <= set(stdlib) | locaux,
             modules - set(stdlib) - locaux)
    texte = SOURCE.read_text(encoding="utf-8")
    verifier("aucun fetchall ni json.dump de la collection entière (curseur + écriture "
             "point par point)", "fetchall" not in texte and "json.dump(" not in texte)

print(f"\n{ok} OK, {ko} ÉCHEC(s)")
sys.exit(1 if ko else 0)
