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
- Outre-mer (DOM-TOM-COM) : un code commune commençant par `9` désigne, en
  principe, un département ou une collectivité à préfixe de trois chiffres
  (`971` à `978`, `986` à `988`...). C'est le chiffre `9` en tête qui signale
  ce format à trois chiffres, quelle que soit la valeur exacte du préfixe :
  cette fonction ne maintient délibérément aucune liste fermée des préfixes
  ultramarins valides, pour ne pas échouer sur un préfixe réel mais absent
  d'un échantillon de données donné.
  **Exception unique et nécessaire : le Val-d'Oise (`95`).** C'est le seul
  département métropolitain dont le préfixe à deux chiffres commence par
  `9` (aucun autre département de 01 à 95 ne partage ce chiffre de tête).
  Un code commune comme `95580` doit donc rester résolu en département
  `95`, et non être happé par la règle « 9 en tête → 3 chiffres ». Cette
  unique exception est structurelle (un seul département sur cent), non une
  table de correspondance par commune : elle ne contredit pas l'absence de
  lookup table exigée par ce module.

**Non-résolution : jamais de valeur devinée.** Conformément à D6 (« aucun
échec silencieux ») et à l'idiome déjà en usage dans ce dépôt
(`ErreurContrat`, `ErreurSchema`, `ErreurEntrepot`...), toute valeur de
`cog_commune` vide, non textuelle, de longueur inattendue ou dont le préfixe
ne correspond à aucun des trois cas ci-dessus fait lever `ErreurTerritoires`.
Aucune valeur par défaut n'est retournée : un appelant qui veut tolérer les
échecs doit le faire explicitement, avec un `try/except ErreurTerritoires`,
jamais en recevant silencieusement `None` ou une chaîne vide qui finirait
par fuiter dans un export.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

__all__ = ["ErreurTerritoires", "departement_depuis_cog"]

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

    # Outre-mer : un code commençant par 9 est de la forme XYZ + 2 chiffres,
    # le préfixe à trois chiffres portant le département ou la collectivité.
    # Aucune liste fermée de préfixes valides n'est maintenue ici : le chiffre
    # de tête suffit à identifier le format, conformément à la règle du COG —
    # à la seule exception du Val-d'Oise (95), seul département métropolitain
    # dont le préfixe à deux chiffres commence lui aussi par 9.
    if valeur[0] == "9" and valeur[:2] != "95":
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
