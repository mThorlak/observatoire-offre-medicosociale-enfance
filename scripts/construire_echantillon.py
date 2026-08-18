"""Construit l'echantillon reduit versionne de la couche 1 (etape E7).

L'echantillon est un SOUS-ENSEMBLE strict des fichiers reels : aucune valeur
n'est modifiee, seuls des enregistrements racines entiers sont retenus ou
ecartes. Il est referentiellement clos : les controles d'integrite doivent y
passer sans orphelin, ce qui impose une fermeture transitive des identifiants
references.

Usage : python construire_echantillon.py <structures.json.gz> <activites.json.gz> <dossier_sortie>
"""
import argparse
import gzip, json, sys
from pathlib import Path
from flux_json import parcourir, CLE_ENTETE

analyseur = argparse.ArgumentParser(description=__doc__)
analyseur.add_argument("structures", type=Path, help="extrait FINESS-Structures complet (.json.gz)")
analyseur.add_argument("activites", type=Path, help="extrait FINESS-Activités complet (.json.gz)")
analyseur.add_argument("sortie", type=Path, help="dossier où écrire l'échantillon")
arguments = analyseur.parse_args()

S = arguments.structures
A = arguments.activites
SORTIE = arguments.sortie
SORTIE.mkdir(exist_ok=True, parents=True)

# Cas limites reperes sur les fichiers complets, avec la raison de leur presence.
GRAINES = {
    '750721334': "plus gros enregistrement : 1 062 ET, 9,86 Mio, pire cas mémoire",
    '010783009': "DITEP 010784262, engagement DISP/DIT",
    '440023620': "établissement à 150 adresses",
    '060020443': "numéros FINESS corses 2A/2B",
    '970302477': "séquences d'échappement dans la dénomination",
    '010000016': "entité juridique sans aucun établissement",
    '010002277': "établissement actif sans aucune activité",
    '060780962': "activité de nature EML",
    '010000156': "capacités de statuts 08 et 09 sur une même activité",
    '010000339': "zone d'intervention avec communes",
    '010000255': "relation entre établissements croisée",
}
GCC_MEMBRES = {'15052', '15159', '15163', '15165', '45502', '45503', '45505',
               '15155', '15156'}

# --- 1. Relever ce qu'il faut pour la fermeture ---------------------------
pm_vers_ej, ege_vers_ej, ej_pm = {}, {}, {}
references = {}          # ej -> ensemble d'ege_id references par ses roleEge
appareils_ej = None
for cle, _r, o in parcourir(S):
    if cle != 'pmej':
        continue
    ig = o['informationsGeneralesPMEJ']
    ej = ig['numFinessPm']
    ej_pm[ej] = ig['pmSmsseId']
    pm_vers_ej[ig['pmSmsseId']] = ej
    besoins = set()
    for e in o.get('ege') or []:
        ege_vers_ej[e['informationsGeneralesEGE']['egeId']] = ej
        for role in e.get('roleEge') or []:
            besoins.add(role.get('idEgePorteuse'))
            besoins.add(role.get('idEgeNonPorteuse'))
        if any((a.get('nature') or {}).get('caracteristiquesSpecifiques', {}).get('appareil')
               for a in ()):
            pass
    references[ej] = {b for b in besoins if b}

# --- 2. Fermeture transitive ---------------------------------------------
retenus = set(GRAINES) | {pm_vers_ej[m] for m in GCC_MEMBRES if m in pm_vers_ej}
tours = 0
while True:
    tours += 1
    ajouts = set()
    for ej in retenus:
        for ege_id in references.get(ej, ()):
            proprietaire = ege_vers_ej.get(ege_id)
            if proprietaire and proprietaire not in retenus:
                ajouts.add(proprietaire)
    if not ajouts:
        break
    retenus |= ajouts
print(f"Fermeture transitive : {len(GRAINES)} graines + membres du GCC "
      f"-> {len(retenus)} entités juridiques en {tours} tours")

pm_retenus = {ej_pm[ej] for ej in retenus}

# --- 3. Écriture des deux fichiers ---------------------------------------
def ecrire(chemin_source, chemin_sortie, cle_ej, filtres_racines):
    entete, tableaux = {}, {k: [] for k in filtres_racines}
    for cle, _r, valeur in parcourir(chemin_source):
        if cle == CLE_ENTETE:
            entete[valeur[0]] = valeur[1]
            continue
        garder = filtres_racines.get(cle)
        if garder is None:
            continue
        if garder(valeur):
            tableaux[cle].append(valeur)
    document = dict(entete)
    document.update(tableaux)
    with gzip.open(chemin_sortie, 'wt', encoding='utf-8') as f:
        json.dump(document, f, ensure_ascii=False, indent=2)
    return {k: len(v) for k, v in tableaux.items()}

_gco_vides = [0]

def gco_clos(g):
    """Un GCO est retenu si ses membres sont tous dans l'échantillon. Les GCO
    sans membre — la quasi-totalité des 1 856 du fichier réel — sont retenus
    dans la limite de trois, pour que le chemin de code soit exercé sans
    gonfler l'échantillon."""
    membres = {m['pmSmsseId'] for m in g.get('pmejDuGco') or []}
    if membres:
        return membres <= pm_retenus
    if _gco_vides[0] < 3:
        _gco_vides[0] += 1
        return True
    return False

def gcc_clos(g):
    membres = {m['pmSmsseId'] for m in g.get('pmejDuGcc') or []}
    return bool(membres) and membres <= pm_retenus

vs = ecrire(S, SORTIE / 'finess-structures-mensuel-202607-echantillon_json.gz', None, {
    'gco': gco_clos, 'gcc': gcc_clos,
    'pmej': lambda o: o['informationsGeneralesPMEJ']['numFinessPm'] in retenus})
va = ecrire(A, SORTIE / 'finess-activites-mensuel-202607-echantillon_json.gz', None, {
    'pmej': lambda o: o['numFiness'] in retenus})
print(f"structures : {vs}")
print(f"activites  : {va}")
for f in sorted(SORTIE.iterdir()):
    print(f"  {f.name:<58} {f.stat().st_size / 2**20:6.2f} Mio")
