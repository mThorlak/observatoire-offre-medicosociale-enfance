"""
territoires.py — Couche 3 (référentiels).

Référentiel territoires minimal : dérivation provisoire du département à
partir de `adresse.cog_commune` (code commune du COG, code officiel
géographique de l'INSEE).

**Statut provisoire.** L'architecture cible (`docs/architecture/
01_ARCHITECTURE_GLOBALE.md` §3 et §6) prévoit que `territoires` soit à terme
alimenté par INSEE (libellés, hiérarchie complète commune → EPCI →
département → région, population). Ce module n'implémente que le strict
minimum permettant, dès aujourd'hui, d'obtenir un code département fiable à
partir d'une adresse déjà chargée : c'est une dérivation purement
algorithmique du code commune, sans aucun appel à un référentiel externe et
sans aucune table de correspondance par commune.

**Contrat de compatibilité ascendante (D3/D6).** Quand INSEE remplacera cette
dérivation, la signature et le contrat de `departement_depuis_cog` ne
doivent pas changer : même entrée (`cog_commune: str`), même sortie (le code
département sous forme de chaîne), même mécanisme de signalement de la
non-résolution. Un futur connecteur INSEE viendra se brancher *derrière*
cette fonction (par exemple en la remplaçant par une consultation de table),
jamais en la contournant. Aucun appelant ne doit avoir à changer.

**Règle de dérivation.** Le code commune du COG encode le département dans
son préfixe :

- Métropole : les deux premiers caractères, numériques (`01` à `95`,
  `20` n'existant plus depuis la partition de la Corse en 1976).
- Corse : les deux premiers caractères valent `2A` ou `2B` directement dans
  `cog_commune` (ex. `2A247`, `2B033`) ; ce sont eux le code département,
  pas une valeur numérique.
- Outre-mer (DOM-TOM-COM) : un code commune dont les deux premiers
  chiffres dépassent la borne métropolitaine (`96` à `99`) désigne un
  département ou une collectivité à préfixe de trois chiffres (`971` à
  `978`, `986` à `988`...). Ce sont ces deux chiffres de tête qui signalent
  le format à trois chiffres, quelle que soit la valeur exacte du troisième :
  cette fonction ne maintient délibérément aucune liste fermée des préfixes
  ultramarins valides, pour ne pas échouer sur un préfixe réel mais absent
  d'un échantillon de données donné.
  **Les départements métropolitains `90` à `95` commencent aussi par `9`**
  (Territoire de Belfort, Essonne, Hauts-de-Seine, Seine-Saint-Denis,
  Val-de-Marne, Val-d'Oise) : un code commune comme `91228` ou `95580` reste
  résolu sur deux chiffres (`91`, `95`). Jusqu'à OOM-106, seule l'exception
  `95` était traitée et `90` à `94` étaient dérivés à tort en `900`…`940` ;
  la borne numérique ci-dessus corrige cette erreur sans table par commune.

**Non-résolution : jamais de valeur devinée.** Conformément à D6 (« aucun
échec silencieux ») et à l'idiome déjà en usage dans ce dépôt
(`ErreurContrat`, `ErreurSchema`, `ErreurEntrepot`...), toute valeur de
`cog_commune` vide, non textuelle, de longueur inattendue ou dont le préfixe
ne correspond à aucun des trois cas ci-dessus fait lever `ErreurTerritoires`.
Aucune valeur par défaut n'est retournée : un appelant qui veut tolérer les
échecs doit le faire explicitement, avec un `try/except ErreurTerritoires`,
jamais en recevant silencieusement `None` ou une chaîne vide qui finirait
par fuiter dans un export.

**Liste des départements (OOM-106) — donnée versionnée (D4).** La dérivation
ci-dessus ne dit pas quels départements *existent* : il en faut la liste
fermée pour énumérer les pages départementales du site, y compris celles d'un
département sans établissement. Elle vit dans `referentiels/departements.csv`
(code, libellé ; source et millésime du COG INSEE en en-tête), chargée par
`charger_departements` — jamais écrite dans le code. Les deux mécanismes
restent distincts : un code dérivé absent de cette liste (collectivité
d'outre-mer `975`, `98x`…) n'est pas une erreur de dérivation, c'est à
l'appelant de le traiter comme « département non résolu au référentiel ».

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Optional

__all__ = ["ErreurTerritoires", "departement_depuis_cog",
           "CHEMIN_REFERENTIEL_DEPARTEMENTS", "charger_departements"]

# Racine du dépôt : src/territoires.py -> src/ -> racine.
CHEMIN_REFERENTIEL_DEPARTEMENTS = (
    Path(__file__).resolve().parent.parent / "referentiels" / "departements.csv")

# Bornes numériques des départements métropolitains. 20 est exclu : depuis la
# partition de la Corse en 1976, aucune commune n'est plus rattachée au
# département 20, remplacé par 2A et 2B.
_DEPARTEMENT_METROPOLE_MIN = 1
_DEPARTEMENT_METROPOLE_MAX = 95
_DEPARTEMENT_CORSE_EXCLU = 20

_LONGUEUR_COG_COMMUNE = 5


class ErreurTerritoires(Exception):
    """`cog_commune` ne peut pas être résolu en département de façon fiable.

    Levée plutôt que de retourner une valeur devinée ou un sentinel silencieux
    (`None`, chaîne vide) : la non-résolution doit interrompre l'appelant qui
    ne la traite pas explicitement, jamais se propager sans bruit jusqu'à un
    indicateur ou un export.
    """


def departement_depuis_cog(cog_commune: str) -> str:
    """Dérive le code département à partir d'un code commune du COG.

    Fonction pure : aucune table de correspondance par commune, aucun accès
    disque ou réseau. Ne fait qu'appliquer la règle de préfixage du COG
    décrite dans le docstring du module.

    Retourne le code département tel qu'il figure dans le COG : deux chiffres
    (`"01"`, ...), `"2A"`/`"2B"` pour la Corse, ou trois chiffres pour
    l'outre-mer (`"971"`, ...).

    Lève `ErreurTerritoires` si `cog_commune` est vide, non textuel, de
    longueur inattendue, ou de préfixe non reconnu. Ne retourne jamais de
    valeur par défaut : il n'existe aucun département "inconnu" valide.
    """
    if not isinstance(cog_commune, str):
        raise ErreurTerritoires(
            f"cog_commune doit être une chaîne, reçu {type(cog_commune).__name__!r}")

    valeur = cog_commune.strip()
    if not valeur:
        raise ErreurTerritoires("cog_commune vide : département non résolu")

    if len(valeur) != _LONGUEUR_COG_COMMUNE:
        raise ErreurTerritoires(
            f"cog_commune de longueur inattendue ({len(valeur)}, "
            f"{_LONGUEUR_COG_COMMUNE} attendus) : {cog_commune!r}")

    # Outre-mer : deux premiers chiffres au-delà de la borne métropolitaine
    # (96 à 99) -> préfixe à trois chiffres portant le département ou la
    # collectivité. Aucune liste fermée de préfixes valides n'est maintenue
    # ici. Les départements 90 à 95, métropolitains, restent à deux chiffres.
    if valeur[:2].isdigit() and int(valeur[:2]) > _DEPARTEMENT_METROPOLE_MAX:
        prefixe = valeur[:3]
        if not prefixe.isdigit():
            raise ErreurTerritoires(
                f"préfixe ultramarin non numérique : {cog_commune!r}")
        return prefixe

    prefixe = valeur[:2]

    # Corse : préfixe alphanumérique 2A/2B, pas une valeur numérique.
    if prefixe.upper() in ("2A", "2B"):
        return prefixe.upper()

    # Métropole : préfixe numérique dans les bornes valides.
    if not prefixe.isdigit():
        raise ErreurTerritoires(f"préfixe de département non reconnu : {cog_commune!r}")
    numero = int(prefixe)
    if (numero < _DEPARTEMENT_METROPOLE_MIN or numero > _DEPARTEMENT_METROPOLE_MAX
            or numero == _DEPARTEMENT_CORSE_EXCLU):
        raise ErreurTerritoires(
            f"préfixe de département hors bornes valides : {cog_commune!r}")
    return prefixe


def charger_departements(chemin: Optional[Path] = None) -> Dict[str, str]:
    """Charge la liste versionnée des départements : code -> libellé.

    L'ordre du dictionnaire est celui du fichier (ordre du COG : `01`…`29`,
    `2A`, `2B`, `30`…`95`, `971`…`976`). Les lignes commençant par `#`
    (en-tête de provenance) sont ignorées. Les codes restent du texte, tels
    qu'écrits dans le fichier : aucun n'est converti en nombre.

    Lève `ErreurTerritoires` si le fichier est absent, s'il n'a pas les
    colonnes `code;libelle`, si une ligne a un code ou un libellé vide, ou si
    un code y figure deux fois — un référentiel incomplet ne se tait pas (D6).
    """
    chemin = Path(chemin) if chemin is not None else CHEMIN_REFERENTIEL_DEPARTEMENTS
    if not chemin.is_file():
        raise ErreurTerritoires(f"référentiel des départements introuvable : {chemin}")

    departements: Dict[str, str] = {}
    with open(chemin, encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader((l for l in f if not l.startswith("#")), delimiter=";")
        if lecteur.fieldnames is None or not {"code", "libelle"} <= set(lecteur.fieldnames):
            raise ErreurTerritoires(
                f"référentiel {chemin} : colonnes code;libelle attendues, "
                f"reçu {lecteur.fieldnames!r}")
        for numero, ligne in enumerate(lecteur, start=1):
            code = (ligne["code"] or "").strip()
            libelle = (ligne["libelle"] or "").strip()
            if not code or not libelle:
                raise ErreurTerritoires(
                    f"référentiel {chemin} : ligne de données {numero} incomplète {ligne!r}")
            if code in departements:
                raise ErreurTerritoires(f"référentiel {chemin} : code {code!r} en double")
            departements[code] = libelle
    if not departements:
        raise ErreurTerritoires(f"référentiel {chemin} : aucun département")
    return departements
