"""
chargement.py — Couche 2 (entrepôt), étape F3.

Écrit dans l'entrepôt les lignes émises par la couche 1. Ne transforme rien :
les tuples reçus sont insérés tels quels, dans l'ordre figé des colonnes
déclarées. Aucune conversion, aucune normalisation, aucun tri.

STRATÉGIE DE CHARGEMENT, ÉTABLIE PAR MESURE EN F2
--------------------------------------------------

Le chargement s'exécute **contraintes de clé étrangère désactivées**, suivi
d'une vérification par `PRAGMA foreign_key_check`. Motif établi en F2 : l'ordre
du document de la couche 1 n'est pas un ordre d'insertion valide — les
groupements y précèdent les entités juridiques qu'ils référencent, et
l'insertion est rejetée contraintes actives. La vérification différée offre la
même garantie sans imposer d'ordre, ce qui a été vérifié y compris sur un
orphelin réel. Toute violation relevée après chargement est bloquante.

Les contraintes de clé primaire, d'unicité et de non-nullité, elles, restent
actives pendant tout le chargement : SQLite les applique toujours, et rien ne
justifie de s'en priver.

La vérification qui suit le chargement comprend **les deux mécanismes** que le
schéma déclare : `PRAGMA foreign_key_check` pour les douze relations couvertes
par une clé étrangère, et les cinq contrôles après chargement pour les
rattachements polymorphes et la treizième relation, qu'aucune clé étrangère ne
peut exprimer. Une anomalie de l'un ou de l'autre place l'ingestion en échec.

TAILLE DES LOTS
----------------

La mesure de F2 a montré que la taille des lots n'a **aucun effet mesurable sur
la vitesse** : de 500 à 100 000 lignes, tout tient en 0,89 s sur 200 000 lignes.
Elle n'est donc pas un réglage de performance. Elle est dimensionnée par le
budget mémoire de 100 Mio hérité de la couche 1, sur mesure dédiée.

IDEMPOTENCE ET COHÉRENCE DU MILLÉSIME
--------------------------------------

Un fichier déjà chargé est reconnu à son empreinte, consignée dans `entete`. La
politique par défaut est le **refus** : elle ne détruit jamais rien. Le
remplacement est possible sur consigne explicite.

L'entrepôt de la V1 est **mono-millésime**, par arbitrage : les clés primaires
justifiées par les artefacts n'admettent qu'un exemplaire de chaque
établissement, et la comparaison entre millésimes relève des couches
supérieures. Encore fallait-il que cette propriété soit garantie. Mesuré en F6
avant correctif : charger le fichier structures de 202607 puis le fichier
activités de 202608 réussissait sans le moindre signal, sans violation de clé
étrangère, et produisait une base silencieusement incohérente.

Deux vérifications préalables sont donc opérées avant toute écriture :
un millésime différent de celui déjà présent est refusé ; une seconde ingestion
de la même source est refusée sauf remplacement explicite. Elles sont dites
préalables parce qu'elles s'appuient sur le nom du fichier et n'exigent aucune
lecture de son contenu.

Aucune dépendance tierce. Compatible Python 3.9+.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from mesure_rss import rss_max_mio

from contrat_source import (CONTROLE_ECHANTILLON, InventaireCodes, Lot,
                            RapportIngestion, RegistreAnomalies,
                            empreinte_fichier, parcourir_source)
from entrepot import Entrepot, ErreurEntrepot, REGLAGES_CHARGEMENT
from schema import ARTEFACT, BESOIN, MESURE, Justification

__all__ = ["REFUSER", "REMPLACER", "RapportChargement", "charger",
           "ErreurChargement", "LOT_DEFAUT"]

REFUSER = "refuser"
REMPLACER = "remplacer"

LOT_DEFAUT = 2_000

JUSTIFICATION_LOT = Justification(
    MESURE,
    "La taille des lots est sans effet sur la vitesse et détermine seule la "
    "mémoire. Mesuré sur le fichier structures complet, 1 530 465 lignes, un "
    "processus neuf par valeur : lot=500 → 65,6 Mio en 28,9 s ; lot=2 000 → "
    "69,5 Mio en 29,8 s ; lot=10 000 → 101,3 Mio en 31,9 s ; lot=50 000 → "
    "237,2 Mio en 32,8 s ; lot=200 000 → 616,7 Mio en 34,0 s. La mémoire croît "
    "linéairement, la durée varie de 18 % sur une plage de 1 à 400 et se dégrade "
    "quand le lot grossit. 2 000 est retenu comme la plus grande valeur laissant "
    "une marge sous le budget de 100 Mio hérité de la couche 1, sachant que le "
    "seul lecteur du fichier activités en occupe déjà 100,1",
    "mesurer_chargement.py, fichiers complets 202607")

JUSTIFICATION_ROWID = Justification(
    MESURE,
    "WITHOUT ROWID n'est pas retenu. Mesuré sur le chargement complet des "
    "5 242 334 lignes, appliqué aux 15 tables pourvues d'une clé primaire : "
    "637,4 Mio en 114,0 s contre 663,8 Mio en 94,8 s pour le mode par défaut, "
    "soit 4,0 % de taille gagnée pour 20,2 % de durée perdue. Le gain n'est pas "
    "décisif, le coût l'est. La table engagement_autorite en serait de toute "
    "façon exclue, faute de clé primaire",
    "mesurer_rowid.py, fichiers complets 202607")


JUSTIFICATION_MONO_MILLESIME = Justification(
    BESOIN,
    "L'entrepôt de la V1 est mono-millésime : décision d'arbitrage prise en F3, "
    "au vu du fait que les clés primaires justifiées par les artefacts "
    "n'admettent qu'un exemplaire de chaque établissement, et que la "
    "comparaison entre millésimes relève des couches supérieures. Sans "
    "vérification, la propriété n'était pas garantie : mesuré en F6, un fichier "
    "structures de 202607 et un fichier activités de 202608 se chargeaient l'un "
    "après l'autre sans erreur, sans violation de clé étrangère, produisant une "
    "base incohérente que rien ne signalait",
    "arbitrage F3 ; démonstration en F6, test_chargement.py section 8")


class ErreurChargement(Exception):
    """Lot déjà présent, millésime divergent, schéma absent, ou violation."""


class RapportChargement:
    __slots__ = ("id_lot", "source", "millesime", "empreinte", "fichier",
                 "inserees", "duree_s", "rss_max_mio", "octets_base",
                 "violations", "controles", "rapport_ingestion", "taille_lot",
                 "remplacement")

    def __init__(self) -> None:
        self.id_lot = ""
        self.source = ""
        self.millesime = ""
        self.empreinte = ""
        self.fichier = ""
        self.inserees: Dict[str, int] = {}
        self.duree_s = 0.0
        self.rss_max_mio = 0.0
        self.octets_base = 0
        self.violations: List[dict] = []
        self.controles: List[dict] = []
        self.rapport_ingestion: Optional[RapportIngestion] = None
        self.taille_lot = LOT_DEFAUT
        self.remplacement = False

    @property
    def total(self) -> int:
        return sum(self.inserees.values())

    @property
    def anomalies_controles(self) -> int:
        return sum(int(c["anomalies"]) for c in self.controles)

    @property
    def statut(self) -> str:
        if self.violations or self.anomalies_controles:
            return "ECHEC"
        if self.rapport_ingestion is not None and self.rapport_ingestion.statut != "SUCCES":
            return "ECHEC"
        return "SUCCES"

    def texte(self) -> str:
        lignes = [
            f"Fichier    : {self.fichier}",
            f"Lot        : {self.id_lot}"
            + (" (remplacement)" if self.remplacement else ""),
            f"Statut     : {self.statut} · {self.duree_s:.1f} s · "
            f"{self.total / max(self.duree_s, 1e-9) / 1000:.0f} kl/s · "
            f"RSS max {self.rss_max_mio:.1f} Mio · lots de {self.taille_lot}",
            f"Insérées   : {self.total} lignes",
        ]
        for nom, n in sorted(self.inserees.items(), key=lambda x: -x[1]):
            lignes.append(f"    {nom:<30}{n:>10}")
        lignes.append(f"Base       : {self.octets_base / 2**20:.1f} Mio")
        lignes.append(f"Violations de clé étrangère : {len(self.violations)}")
        for violation in self.violations[:5]:
            lignes.append(f"    {violation}")
        if self.controles:
            lignes.append(
                f"Contrôles après chargement  : {len(self.controles)} exécutés, "
                f"{self.anomalies_controles} anomalie(s)")
            for controle in self.controles:
                if controle["anomalies"]:
                    lignes.append(f"    {controle['nom']} : "
                                  f"{controle['anomalies']} · {controle['detail']}")
        return "\n".join(lignes)


def _verifier_coherence(entrepot: Entrepot, source_nom: str, millesime: str,
                        doublon: str) -> None:
    """Refuse toute ingestion qui rendrait l'entrepôt incohérent.

    S'appuie sur le nom du fichier seul : aucune lecture de contenu n'est
    nécessaire, la vérification est donc gratuite et précède l'écriture.
    """
    connexion = entrepot._requiert_connexion()
    presents = list(connexion.execute(
        "SELECT DISTINCT source, millesime FROM entete"))
    millesimes = {m for _s, m in presents}
    if millesimes and millesime not in millesimes:
        raise ErreurChargement(
            f"L'entrepôt porte déjà le millésime {sorted(millesimes)[0]!r} et la "
            f"V1 est mono-millésime ; refus de charger {millesime!r}. Utiliser "
            f"une base distincte par millésime, ou reconstruire celle-ci")
    if len(millesimes) > 1:
        raise ErreurChargement(
            f"L'entrepôt porte déjà plusieurs millésimes {sorted(millesimes)} : "
            f"il est incohérent et doit être reconstruit")
    deja = [m for s_, m in presents if s_ == source_nom]
    if deja and doublon != REMPLACER:
        raise ErreurChargement(
            f"La source {source_nom!r} est déjà chargée pour le millésime "
            f"{deja[0]!r}. Utiliser doublon=REMPLACER pour l'écraser")


def _lot_deja_present(entrepot: Entrepot, empreinte: str) -> Optional[str]:
    connexion = entrepot._requiert_connexion()
    trouve = list(connexion.execute(
        "SELECT id_lot FROM entete WHERE empreinte = ?", (empreinte,)))
    return trouve[0][0] if trouve else None


def _effacer_lot(entrepot: Entrepot, id_lot: str) -> Dict[str, int]:
    """Retire toutes les lignes d'un lot. Les tables sont parcourues à
    l'envers de leur ordre de déclaration, les enfants avant les parents."""
    connexion = entrepot._requiert_connexion()
    effacees: Dict[str, int] = {}
    for table in reversed(entrepot.schema.tables):
        curseur = connexion.execute(
            f"DELETE FROM {table.nom} WHERE id_lot = ?", (id_lot,))
        if curseur.rowcount:
            effacees[table.nom] = curseur.rowcount
    return effacees


def charger(entrepot: Entrepot, source, chemin: Path,
            taille_lot: int = LOT_DEFAUT,
            controle: str = CONTROLE_ECHANTILLON,
            doublon: str = REFUSER,
            verifier_apres: bool = True) -> RapportChargement:
    """Charge un fichier dans l'entrepôt, en flux et à mémoire bornée."""
    chemin = Path(chemin)
    if doublon not in (REFUSER, REMPLACER):
        raise ErreurChargement(f"Politique de doublon inconnue : {doublon!r}")
    conforme, ecarts = entrepot.schema_conforme()
    if not conforme:
        raise ErreurChargement(f"Schéma non conforme : {ecarts}")

    rapport = RapportChargement()
    rapport.fichier = chemin.name
    rapport.taille_lot = taille_lot
    _verifier_coherence(entrepot, source.nom, source.millesime(chemin), doublon)
    empreinte, _octets = empreinte_fichier(chemin)
    rapport.empreinte = empreinte

    existant = _lot_deja_present(entrepot, empreinte)
    if existant is None and doublon == REMPLACER:
        # Remplacer une source par un fichier différent du même millésime :
        # l'ancien lot de cette source est retiré avant écriture.
        anciens = [r[0] for r in entrepot._requiert_connexion().execute(
            "SELECT id_lot FROM entete WHERE source = ?", (source.nom,))]
        existant = anciens[0] if anciens else None
    if existant is not None:
        if doublon == REFUSER:
            raise ErreurChargement(
                f"Fichier déjà chargé sous le lot {existant!r} (empreinte "
                f"{empreinte[:12]}…). Utiliser doublon=REMPLACER pour l'écraser")
        with entrepot.reglages_temporaires(REGLAGES_CHARGEMENT):
            with entrepot.transaction():
                _effacer_lot(entrepot, existant)
        rapport.remplacement = True

    tables = {t.nom: t for t in entrepot.schema.tables}
    requetes = {
        nom: f"INSERT INTO {nom} VALUES ({','.join('?' * len(t.colonnes))})"
        for nom, t in tables.items()}
    tampons: Dict[str, List[tuple]] = {nom: [] for nom in tables}

    rapport_ingestion = RapportIngestion(Lot("", "", "", "", 0), RegistreAnomalies(),
                                         InventaireCodes(), controle)
    rapport.rapport_ingestion = rapport_ingestion
    depart = time.time()

    with entrepot.reglages_temporaires(REGLAGES_CHARGEMENT):
        connexion = entrepot._requiert_connexion()
        connexion.execute("BEGIN")
        try:
            for nom_type, ligne in parcourir_source(
                    source, chemin, controle=controle, rapport=rapport_ingestion,
                    inventorier_codes=False):
                tampon = tampons[nom_type]
                tampon.append(ligne)
                if len(tampon) >= taille_lot:
                    connexion.executemany(requetes[nom_type], tampon)
                    rapport.inserees[nom_type] = (
                        rapport.inserees.get(nom_type, 0) + len(tampon))
                    tampon.clear()
            for nom_type, tampon in tampons.items():
                if tampon:
                    connexion.executemany(requetes[nom_type], tampon)
                    rapport.inserees[nom_type] = (
                        rapport.inserees.get(nom_type, 0) + len(tampon))
                    tampon.clear()
        except BaseException:
            connexion.execute("ROLLBACK")
            raise
        connexion.execute("COMMIT")

        if verifier_apres:
            rapport.violations = entrepot.verifier_integrite()[
                "violations_cles_etrangeres"]
            # Les cinq contrôles déclarés couvrent les relations que SQL ne peut
            # pas exprimer : rattachements polymorphes, et clé étrangère visant
            # une colonne non unique. Les déclarer sans les exécuter sur le
            # chemin nominal reviendrait à annoncer une garantie qui n'en est
            # pas une. Coût mesuré : 1,4 s sur la base complète.
            rapport.controles = entrepot.executer_controles()

    rapport.duree_s = time.time() - depart
    rapport.rss_max_mio = rss_max_mio()
    rapport.octets_base = entrepot.octets()
    rapport.id_lot = rapport_ingestion.lot.identifiant
    rapport.source = rapport_ingestion.lot.source
    rapport.millesime = rapport_ingestion.lot.millesime
    return rapport


if __name__ == "__main__":
    import argparse

    from finess_activites import SourceFinessActivites
    from finess_structures import SourceFinessStructures
    from contrat_source import CONTROLE_MINIMAL, CONTROLE_STRICT

    SOURCES = {"structures": SourceFinessStructures, "activites": SourceFinessActivites}

    analyseur = argparse.ArgumentParser(description="Chargement dans l'entrepôt.")
    analyseur.add_argument("base", type=Path)
    analyseur.add_argument("fichier", type=Path, nargs="+")
    analyseur.add_argument("--creer", action="store_true")
    analyseur.add_argument("--lot", type=int, default=LOT_DEFAUT)
    analyseur.add_argument("--controle", default=CONTROLE_ECHANTILLON,
                           choices=[CONTROLE_MINIMAL, CONTROLE_ECHANTILLON,
                                    CONTROLE_STRICT])
    analyseur.add_argument("--remplacer", action="store_true")
    arguments = analyseur.parse_args()

    with Entrepot(arguments.base) as entrepot:
        if arguments.creer:
            entrepot.creer(ecraser=True)
        code = 0
        for fichier in arguments.fichier:
            nom = fichier.name.lower()
            candidats = [c for c in SOURCES if c in nom]
            if len(candidats) != 1:
                raise SystemExit(f"Connecteur indéterminable pour {fichier.name!r}")
            rapport = charger(entrepot, SOURCES[candidats[0]](), fichier,
                              taille_lot=arguments.lot, controle=arguments.controle,
                              doublon=REMPLACER if arguments.remplacer else REFUSER)
            print(rapport.texte())
            print()
            code |= 0 if rapport.statut == "SUCCES" else 1
        print(entrepot.rapport())
        raise SystemExit(code)
