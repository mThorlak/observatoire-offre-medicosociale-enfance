"""Mesure du poids du site rendu par export_html.py, contre le budget D9 (OOM-109).

D9 : aucune page ne dépasse 500 Ko de données au chargement initial. La charge
initiale d'une page est son HTML plus les actifs qu'elle référence
(`<link href>`, `<script src>`, `<img src>` relatifs) ; les fragments
`donnees/activites/*.json`, chargés à la demande par activites.js au premier
clic, n'en font pas partie. Ils sont mesurés à part, pour information.

Le budget s'applique à la taille brute (octets sur disque). La taille gzip
(niveau 6, celui d'un serveur web par défaut) est donnée à titre indicatif :
elle dépend de l'hébergeur, le budget non.

1 Ko = 1024 octets, comme dans le bilan d'export_html.py.

Usage :
    python mesures/poids_site.py site/ [--rapport mesures/poids_site.md]

Code de retour 1 si une page dépasse le budget : un dépassement se signale,
il ne se tolère pas (D6, D9).
"""
import argparse, gzip, re, statistics, sys
from pathlib import Path

BUDGET = 500 * 1024
REFERENCE = re.compile(r'<(?:link|script|img)\b[^>]*?\b(?:href|src)="([^"#?]+)"', re.I)


def ko(octets):
    return f"{octets / 1024:.1f}"


def gz(chemin):
    return len(gzip.compress(chemin.read_bytes(), compresslevel=6))


def type_de(relatif):
    if relatif.parts[0] == "departement":
        return "departement/*.html"
    return relatif.as_posix()


def actifs_references(page, racine):
    """Actifs locaux référencés par la page, résolus depuis son dossier."""
    trouves = []
    for cible in REFERENCE.findall(page.read_text(encoding="utf-8")):
        if "://" in cible or cible.startswith("//"):
            continue
        chemin = (page.parent / cible).resolve()
        if chemin.is_file() and racine in chemin.parents:
            trouves.append(chemin)
    return sorted(set(trouves))


def mesurer(racine):
    racine = racine.resolve()
    pages = []
    for page in sorted(racine.rglob("*.html")):
        relatif = page.relative_to(racine)
        actifs = actifs_references(page, racine)
        html = page.stat().st_size
        brut = html + sum(a.stat().st_size for a in actifs)
        comprime = gz(page) + sum(gz(a) for a in actifs)
        pages.append({"page": relatif.as_posix(), "type": type_de(relatif),
                      "html": html, "initial": brut, "initial_gz": comprime,
                      "actifs": [a.relative_to(racine).as_posix() for a in actifs]})
    fragments = [{"page": f.relative_to(racine).as_posix(), "brut": f.stat().st_size,
                  "gz": gz(f)} for f in sorted((racine / "donnees").rglob("*.json"))]
    actifs = [{"page": a.relative_to(racine).as_posix(), "brut": a.stat().st_size,
               "gz": gz(a)} for a in sorted((racine / "actifs").rglob("*")) if a.is_file()]
    return pages, fragments, actifs


def synthese(lignes, cle, cle_gz):
    valeurs = [l[cle] for l in lignes]
    lourde = max(lignes, key=lambda l: l[cle])
    return {"n": len(lignes), "mediane": statistics.median(valeurs),
            "max": lourde[cle], "max_gz": lourde[cle_gz], "lourde": lourde["page"],
            "total": sum(valeurs)}


def rapport(racine, pages, fragments, actifs):
    types = sorted({p["type"] for p in pages})
    hors_budget = sorted((p for p in pages if p["initial"] > BUDGET),
                         key=lambda p: -p["initial"])
    lourde = max(pages, key=lambda p: p["initial"])
    l = []
    l.append(f"# Poids du site — mesure D9 (OOM-109)\n")
    l.append(f"Site mesuré : `{racine}` · {len(pages)} pages HTML, "
             f"{len(fragments)} fragments, {len(actifs)} actifs.  ")
    l.append(f"Budget D9 : {ko(BUDGET)} Ko bruts au chargement initial "
             f"(HTML + actifs référencés, hors fragments chargés à la demande).\n")
    l.append("## Chargement initial, par type de page\n")
    l.append("| Type | Pages | Médiane (Ko) | Max (Ko) | Max gzip (Ko) | Page la plus lourde | Hors budget |")
    l.append("|---|---:|---:|---:|---:|---|---:|")
    for t in types:
        groupe = [p for p in pages if p["type"] == t]
        s = synthese(groupe, "initial", "initial_gz")
        n_hors = sum(1 for p in groupe if p["initial"] > BUDGET)
        l.append(f"| `{t}` | {s['n']} | {ko(s['mediane'])} | {ko(s['max'])} | "
                 f"{ko(s['max_gz'])} | `{s['lourde']}` | {n_hors} |")
    l.append("")
    l.append(f"**Page la plus lourde : `{lourde['page']}`, {ko(lourde['initial'])} Ko "
             f"au chargement initial** (HTML {ko(lourde['html'])} Ko + actifs "
             f"{', '.join('`' + a + '`' for a in lourde['actifs'])} ; "
             f"{ko(lourde['initial_gz'])} Ko en gzip), soit "
             f"{lourde['initial'] / BUDGET:.1f} × le budget.\n")
    l.append("## Fragments chargés à la demande (hors budget initial)\n")
    s = synthese(fragments, "brut", "gz")
    l.append("| Type | Fichiers | Médiane (Ko) | Max (Ko) | Max gzip (Ko) | Plus lourd | Total (Ko) |")
    l.append("|---|---:|---:|---:|---:|---|---:|")
    l.append(f"| `donnees/activites/*.json` | {s['n']} | {ko(s['mediane'])} | {ko(s['max'])} | "
             f"{ko(s['max_gz'])} | `{s['lourde']}` | {ko(s['total'])} |\n")
    l.append("## Actifs\n")
    l.append("| Actif | Brut (Ko) | gzip (Ko) |")
    l.append("|---|---:|---:|")
    for a in actifs:
        l.append(f"| `{a['page']}` | {ko(a['brut'])} | {ko(a['gz'])} |")
    l.append("")
    l.append(f"## Verdict D9\n")
    if hors_budget:
        l.append(f"**Budget dépassé : {len(hors_budget)} page(s) sur {len(pages)} au-delà de "
                 f"{ko(BUDGET)} Ko.**\n")
        l.append("| Page | Initial (Ko) | gzip (Ko) | × budget |")
        l.append("|---|---:|---:|---:|")
        for p in hors_budget:
            l.append(f"| `{p['page']}` | {ko(p['initial'])} | {ko(p['initial_gz'])} | "
                     f"{p['initial'] / BUDGET:.1f} |")
    else:
        l.append(f"Budget tenu : aucune page au-delà de {ko(BUDGET)} Ko.")
    l.append("")
    return "\n".join(l), hors_budget


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyseur.add_argument("site", type=Path)
    analyseur.add_argument("--rapport", type=Path, default=None,
                           help="écrit aussi le rapport Markdown dans ce fichier")
    args = analyseur.parse_args()
    if not (args.site / "index.html").is_file():
        sys.exit(f"ÉCHEC : {args.site / 'index.html'} absent — rendre le site d'abord "
                 f"(python src/export_html.py <base.sqlite> --sortie {args.site})")
    pages, fragments, actifs = mesurer(args.site)
    texte, hors_budget = rapport(args.site.as_posix().rstrip("/") + "/", pages, fragments, actifs)
    print(texte)
    if args.rapport:
        args.rapport.write_text(texte, encoding="utf-8")
    sys.exit(1 if hors_budget else 0)
