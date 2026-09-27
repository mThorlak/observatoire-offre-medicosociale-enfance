"""
sources/finess_activites.py — Couche 1 (acquisition), étape E4.

Connecteur du fichier `finess-activites-mensuel`. Il traduit, et rien d'autre.

Les deux niveaux du fichier sont ingérés, conformément à SCHEMA_PIVOT.md § 6 :
`activitesAutorisees` au niveau de l'entité juridique et `activitesExercees` au
niveau de l'établissement portent le même effectif mais des contenus
complémentaires. La zone d'intervention n'existe qu'au niveau EJ, les appareils
et les identifiants d'autorisation qu'au niveau ET. N'en ingérer qu'un seul
perdrait de l'information.

Quatre invariants sont contrôlés de façon bloquante, tous vérifiés sur les
585 746 activités de 202607 avant écriture du connecteur :
- exactement un bloc `typeActivite*` renseigné par activité ;
- ce bloc correspond toujours au `codeNature` déclaré ;
- au plus un identifiant `aa*Id` renseigné par activité ;
- au niveau ET, `caracteristiquesGeneriques.egeId` égale l'établissement
  englobant.

Un seul passage, à mémoire bornée. Aucune dépendance tierce. Python 3.9+.
"""

from __future__ import annotations

from collections import namedtuple
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from contrat_source import BLOQUANT, ContexteSource, Source
from flux_json import CLE_ENTETE, parcourir
import finess_commun as fc

__all__ = ["SourceFinessActivites"]

# --- jeux de clés, dérivés du recensement exhaustif de 202607 --------------

CLES_ENTETE_SCALAIRES = frozenset({"schemaVersion", "generatedAt"})
CLES_PMEJ = frozenset({"numFiness", "pmSmsseId", "activitesAutorisees", "ege"})
CLES_EGE = frozenset({"egeId", "numFinessEge", "activitesExercees"})
CLES_ACTIVITE = frozenset({
    "caracteristiquesGeneriques", "nature", "capacite", "evenement",
    "engagement", "zoneIntervention",
})
# Les caractéristiques génériques diffèrent selon le niveau : l'EJ porte
# l'exploitant personne morale, l'ET l'exploitant et le facturant géographiques.
CLES_GENERIQUES_EJ = frozenset({
    "activiteAeId", "typeActiviteSMSSE", "etatObjet", "egeId",
    "identifiantAutorisation", "numAutorisationArhgos",
    "dateDebutActiviteAutorisee", "dateFinActiviteAutorisee",
    "dateFinEffectiveActivite", "dateCaduciteAutorisation",
    "pmSmsseExploitanteId",
})
CLES_GENERIQUES_ET = frozenset({
    "activiteAeId", "typeActiviteSMSSE", "etatObjet", "egeId",
    "identifiantAutorisation", "numAutorisationArhgos",
    "dateDebutActiviteAutorisee", "dateFinActiviteAutorisee",
    "dateFinEffectiveActivite", "dateCaduciteAutorisation",
    "egeExploitanteId", "egeFacturante",
})
CLES_NATURE = frozenset({"codeNature", "caracteristiquesSpecifiques"})
CLES_CAPACITE = frozenset({
    "idCapacite", "activiteAeId", "nombre", "statutCapacite",
    "uniteMesureCapacite", "habilitation", "typeLogement", "genre",
    "modeFinancement", "precision", "variation", "engagementId",
})
CLES_ZONE = frozenset({
    "zoneInterventionAutoriseeId", "activiteAeId", "libelleZI", "communeZI",
})
CLES_COMMUNE_ZI = frozenset({"commune"})
CLES_APPAREIL = frozenset({"typeAppareilAMM", "nombreAppareilAMM", "statutAppareilAMM"})

# Chaque nature porte un jeu de clés qui lui est propre, identique aux deux
# niveaux et invariable : mesuré sur les 585 746 activités de 202607, aucune
# nature ne présente plus d'une forme. Le contrat est donc déclaré par nature,
# et non par union — ce qui le rend nettement plus strict.

Nature = namedtuple("Nature", "bloc cles_bloc cle_code cles_specifiques identifiant")

_AGES = ("ageMinAutorise", "ageMaxAutorise", "ageMinInstalle", "ageMaxInstalle")
_TRIPLET = frozenset({"modeFonctionnement", "public"})

NATURES: Dict[str, Nature] = {
    "ASMR": Nature(
        "typeActiviteAMSR", _TRIPLET | {"activiteSocialeRegulee"}, "activiteSocialeRegulee",
        frozenset({"activiteAeId", "aaSocialeReguleeId", "typeActiviteAMSR", *_AGES}),
        "aaSocialeReguleeId"),
    "ASOCR": Nature(
        "typeActiviteASOCR", _TRIPLET | {"activiteSocialeRegulee"}, "activiteSocialeRegulee",
        frozenset({"activiteAeId", "aaSocialeReguleeId", "typeActiviteASOCR", *_AGES}),
        "aaSocialeReguleeId"),
    "ASDR": Nature(
        "typeActiviteASDR", _TRIPLET | {"activiteSanitaireDiverseRegulee"},
        "activiteSanitaireDiverseRegulee",
        frozenset({"activiteAeId", "aaSanitaireDiverseReguleeId", "typeActiviteASDR"}),
        "aaSanitaireDiverseReguleeId"),
    "AER": Nature(
        "typeActiviteAER", _TRIPLET | {"activiteEnseignementRegulee"},
        "activiteEnseignementRegulee",
        frozenset({"activiteAeId", "typeActiviteAER"}),
        None),
    "AASA": Nature(
        "typeActiviteAASA",
        frozenset({"activiteSanitaireRegulee", "formeActivite", "modaliteActivite"}),
        "activiteSanitaireRegulee",
        frozenset({"activiteAeId", "aaAutreActSoinId", "typeActiviteAASA", "etatArhgos",
                   "numDecision", "resultatVisite", "dateLimDep",
                   "dateLimVisiteConformite", "dateVisite"}),
        "aaAutreActSoinId"),
    "AMF": Nature(
        "typeActiviteAMF",
        frozenset({"activiteAMF", "formeActivite", "modaliteActivite"}), "activiteAMF",
        frozenset({"activiteAeId", "aaSoinAmfId", "typeActiviteAMF"}),
        "aaSoinAmfId"),
    "AMM": Nature(
        "typeActiviteAMM",
        frozenset({"activiteAMM", "modaliteAMM", "mentionAMM", "ptsAMM", "declarationAMM"}),
        "activiteAMM",
        frozenset({"activiteAeId", "aaSoinAmmId", "typeActiviteAMM", "appareil"}),
        "aaSoinAmmId"),
    "EML": Nature(
        "typeActiviteEML", frozenset({"typeEmlId"}), None,
        frozenset({"activiteAeId", "aaEmlId", "typeActiviteEML", "marque", "numeroSerie"}),
        "aaEmlId"),
}

# Équivalences de codes de nature, déclarées et non déduites (OOM-114). Dérive
# constatée sur l'extrait journalier du 27/09/2026 : la nature « activité
# sociale et médico-sociale régulée » y est codée `AMSR` (227 860 occurrences,
# aucune `ASMR`), alors que 202607 et l'extrait du 19/08/2026 écrivent `ASMR`.
# Le recensement des deux extraits montre des chemins JSON identiques : seul
# le code change, et `AMSR` est l'acronyme que le bloc typé portait déjà
# (`typeActiviteAMSR`). L'équivalence ne porte que sur le contrat de clés :
# `code_nature` reste stocké tel que lu, jamais réécrit (D2/D3). Tout autre
# code reste bloquant (D6). Cf. docs/08_SOURCES_DONNEES.md.
EQUIVALENCES_NATURE: Dict[str, str] = {"AMSR": "ASMR"}

for _code, _reference in EQUIVALENCES_NATURE.items():
    NATURES[_code] = NATURES[_reference]
del _code, _reference


class SourceFinessActivites(Source):
    """Connecteur du fichier activités mensuel FINESS."""

    nom = "finess_activites"

    def __init__(self, taille_bloc: int = 1 << 18) -> None:
        self.taille_bloc = taille_bloc

    def millesime(self, chemin: Path) -> str:
        return fc.extraire_millesime(Path(chemin).name)

    def types_enregistrements(self):
        return fc.TYPES_ACTIVITES

    # -- production ---------------------------------------------------------

    def produire(self, chemin: Path, contexte: ContexteSource
                 ) -> Iterator[Tuple[str, Dict[str, Any]]]:
        lot = contexte.lot
        entete_emise = False

        for cle_racine, _rang, valeur in parcourir(chemin, taille_bloc=self.taille_bloc):

            if cle_racine == CLE_ENTETE:
                nom, contenu = valeur
                if nom not in CLES_ENTETE_SCALAIRES:
                    contexte.signaler("cle_racine_non_declaree", BLOQUANT,
                                      type_enregistrement="racine", champ=nom)
                    continue
                if entete_emise:
                    contexte.signaler("entete_tardive", BLOQUANT,
                                      type_enregistrement="racine", champ=nom)
                    continue
                if nom == "schemaVersion":
                    lot.schema_version = contenu
                else:
                    lot.genere_le = contenu
                continue

            if not entete_emise:
                yield ("entete", lot.ligne_entete())
                entete_emise = True

            if cle_racine != "pmej":
                contexte.signaler("tableau_racine_non_declare", BLOQUANT,
                                  type_enregistrement="racine", champ=cle_racine)
                contexte.compter_ignore(cle_racine)
                continue

            contexte.compter_lu("pmej")
            yield from self._entite_juridique(valeur, contexte)

    def _entite_juridique(self, pmej: Dict[str, Any], contexte: ContexteSource
                          ) -> Iterator[Tuple[str, Dict[str, Any]]]:
        fc.controler_cles(contexte, "pmej", pmej, CLES_PMEJ)
        num_ej = pmej.get("numFiness")
        pm_id = pmej.get("pmSmsseId")

        for rang, activite in enumerate(pmej.get("activitesAutorisees") or []):
            contexte.compter_lu("activite_ej")
            yield from self._activite(activite, fc.NIVEAU_EJ, rang, num_ej, pm_id,
                                      None, None, contexte)

        for ege in pmej.get("ege") or []:
            contexte.compter_lu("ege")
            fc.controler_cles(contexte, "pmej.ege", ege, CLES_EGE)
            ege_id = ege.get("egeId")
            num_et = ege.get("numFinessEge")
            for rang, activite in enumerate(ege.get("activitesExercees") or []):
                contexte.compter_lu("activite_et")
                yield from self._activite(activite, fc.NIVEAU_ET, rang, num_ej, pm_id,
                                          ege_id, num_et, contexte)

    # -- activité et ses dépendances ----------------------------------------

    def _activite(self, activite: Dict[str, Any], niveau: str, rang: int,
                  num_ej: Optional[str], pm_id: Optional[str],
                  ege_id_parent: Optional[str], num_et: Optional[str],
                  contexte: ContexteSource) -> Iterator[Tuple[str, Dict[str, Any]]]:
        lot = contexte.lot
        chemin = f"activite.{niveau}"
        fc.controler_cles(contexte, chemin, activite, CLES_ACTIVITE)

        generiques = activite.get("caracteristiquesGeneriques") or {}
        fc.controler_cles(
            contexte, f"{chemin}.caracteristiquesGeneriques", generiques,
            CLES_GENERIQUES_EJ if niveau == fc.NIVEAU_EJ else CLES_GENERIQUES_ET)

        nature = activite.get("nature") or {}
        fc.controler_cles(contexte, f"{chemin}.nature", nature, CLES_NATURE)
        specifiques = nature.get("caracteristiquesSpecifiques") or {}

        activite_ae_id = generiques.get("activiteAeId")
        code_nature = nature.get("codeNature")
        ege_id = generiques.get("egeId")

        if niveau == fc.NIVEAU_ET and ege_id != ege_id_parent:
            contexte.signaler("rattachement_incoherent", BLOQUANT,
                              type_enregistrement=chemin, champ="egeId",
                              detail=f"{ege_id} au lieu de {ege_id_parent}")

        bloc, code_activite, identifiant_nature = self._nature(
            specifiques, code_nature, chemin, contexte)

        yield ("activite", {
            "niveau": niveau,
            "activite_ae_id": activite_ae_id,
            "num_finess_ej": num_ej,
            "pm_smsse_id": pm_id,
            "ege_id": ege_id,
            "num_finess_et": num_et,
            "rang": str(rang),
            "code_nature": code_nature,
            "code_type_activite_smsse": generiques.get("typeActiviteSMSSE"),
            "etat_objet": generiques.get("etatObjet"),
            "identifiant_autorisation": generiques.get("identifiantAutorisation"),
            "num_autorisation_arhgos": generiques.get("numAutorisationArhgos"),
            "date_debut_activite_autorisee": generiques.get("dateDebutActiviteAutorisee"),
            "date_fin_activite_autorisee": generiques.get("dateFinActiviteAutorisee"),
            "date_fin_effective_activite": generiques.get("dateFinEffectiveActivite"),
            "date_caducite_autorisation": generiques.get("dateCaduciteAutorisation"),
            "pm_smsse_exploitante_id": generiques.get("pmSmsseExploitanteId"),
            "ege_exploitante_id": generiques.get("egeExploitanteId"),
            "ege_facturante": generiques.get("egeFacturante"),
            "identifiant_nature": identifiant_nature,
            "code_activite_regulee": code_activite,
            "code_mode_fonctionnement": bloc.get("modeFonctionnement"),
            "code_public": bloc.get("public"),
            "age_min_autorise": specifiques.get("ageMinAutorise"),
            "age_max_autorise": specifiques.get("ageMaxAutorise"),
            "age_min_installe": specifiques.get("ageMinInstalle"),
            "age_max_installe": specifiques.get("ageMaxInstalle"),
            "code_forme_activite": bloc.get("formeActivite"),
            "code_modalite_activite": bloc.get("modaliteActivite"),
            "code_modalite_amm": bloc.get("modaliteAMM"),
            "code_mention_amm": bloc.get("mentionAMM"),
            "code_pts_amm": bloc.get("ptsAMM"),
            "code_declaration_amm": bloc.get("declarationAMM"),
            "type_eml_id": bloc.get("typeEmlId"),
            "marque": specifiques.get("marque"),
            "numero_serie": specifiques.get("numeroSerie"),
            "code_etat_arhgos": specifiques.get("etatArhgos"),
            "num_decision": specifiques.get("numDecision"),
            "date_lim_dep": specifiques.get("dateLimDep"),
            "date_lim_visite_conformite": specifiques.get("dateLimVisiteConformite"),
            "date_visite": specifiques.get("dateVisite"),
            "code_resultat_visite": specifiques.get("resultatVisite"),
            "activite_ae_id_specifique": specifiques.get("activiteAeId"),
            "id_lot": lot.identifiant,
        })

        for rang_capacite, capacite in enumerate(activite.get("capacite") or []):
            fc.controler_cles(contexte, f"{chemin}.capacite", capacite, CLES_CAPACITE)
            yield ("capacite", {
                "id_capacite": capacite.get("idCapacite"),
                "niveau": niveau,
                "activite_ae_id": capacite.get("activiteAeId"),
                "rang": str(rang_capacite),
                "nombre": capacite.get("nombre"),
                "code_statut_capacite": capacite.get("statutCapacite"),
                "code_unite_mesure": capacite.get("uniteMesureCapacite"),
                "code_habilitation": capacite.get("habilitation"),
                "code_type_logement": capacite.get("typeLogement"),
                "code_genre": capacite.get("genre"),
                "code_mode_financement": capacite.get("modeFinancement"),
                "precision": capacite.get("precision"),
                "variation": capacite.get("variation"),
                "engagement_id": capacite.get("engagementId"),
                "id_lot": lot.identifiant,
            })

        for rang_appareil, appareil in enumerate(specifiques.get("appareil") or []):
            fc.controler_cles(contexte, f"{chemin}.appareil", appareil, CLES_APPAREIL)
            yield ("appareil", {
                "activite_ae_id": activite_ae_id,
                "rang": str(rang_appareil),
                "code_type_appareil": appareil.get("typeAppareilAMM"),
                "nombre_appareil": appareil.get("nombreAppareilAMM"),
                "code_statut_appareil": appareil.get("statutAppareilAMM"),
                "id_lot": lot.identifiant,
            })

        zone = activite.get("zoneIntervention")
        if zone:
            fc.controler_cles(contexte, f"{chemin}.zoneIntervention", zone, CLES_ZONE)
            zone_id = zone.get("zoneInterventionAutoriseeId")
            yield ("zone_intervention", {
                "zone_intervention_id": zone_id,
                "activite_ae_id": zone.get("activiteAeId"),
                "libelle_zone": zone.get("libelleZI"),
                "id_lot": lot.identifiant,
            })
            for rang_commune, commune in enumerate(zone.get("communeZI") or []):
                fc.controler_cles(contexte, f"{chemin}.zoneIntervention.communeZI",
                                  commune, CLES_COMMUNE_ZI)
                yield ("zone_intervention_commune", {
                    "zone_intervention_id": zone_id,
                    "rang": str(rang_commune),
                    "cog_commune": commune.get("commune"),
                    "id_lot": lot.identifiant,
                })

        porteur = (fc.PORTEUR_ACTIVITE_EJ if niveau == fc.NIVEAU_EJ
                   else fc.PORTEUR_ACTIVITE_ET)
        yield from self._engagements(activite.get("engagement"), porteur,
                                     activite_ae_id, contexte)
        yield from self._evenements(activite.get("evenement"), porteur,
                                    activite_ae_id, contexte)

    # -- fentes uniques -----------------------------------------------------

    @staticmethod
    def _nature(specifiques: Dict[str, Any], code_nature: Optional[str],
                chemin: str, contexte: ContexteSource
                ) -> Tuple[Dict[str, Any], Optional[str], Optional[str]]:
        """Retourne (bloc typé, code d'activité régulée, identifiant de nature).

        Le jeu de clés de `caracteristiquesSpecifiques` est contrôlé selon la
        nature déclarée : c'est ce contrôle qui garantit qu'un seul bloc typé
        et un seul identifiant peuvent être présents. Une nature inconnue, un
        jeu de clés inattendu ou un bloc nul sont bloquants.
        """
        declaration = NATURES.get(code_nature)
        if declaration is None:
            contexte.signaler("nature_non_declaree", BLOQUANT,
                              type_enregistrement=chemin, detail=str(code_nature))
            return {}, None, None
        fc.controler_cles(contexte, f"{chemin}.specifiques.{code_nature}",
                          specifiques, declaration.cles_specifiques)
        bloc = specifiques.get(declaration.bloc)
        if bloc is None:
            contexte.signaler("bloc_absent", BLOQUANT, type_enregistrement=chemin,
                              champ=declaration.bloc, detail=str(code_nature))
            return {}, None, None
        fc.controler_cles(contexte, f"{chemin}.{declaration.bloc}",
                          bloc, declaration.cles_bloc)
        code = bloc.get(declaration.cle_code) if declaration.cle_code else None
        identifiant = (specifiques.get(declaration.identifiant)
                       if declaration.identifiant else None)
        return bloc, code, identifiant

    # -- blocs partagés -----------------------------------------------------

    def _engagements(self, engagements, porteur: str, id_porteur: Optional[str],
                     contexte: ContexteSource) -> Iterator[Tuple[str, Dict[str, Any]]]:
        lot = contexte.lot
        for rang, engagement in enumerate(engagements or []):
            fc.controler_cles(contexte, f"{porteur}.engagement", engagement,
                              fc.CLES_ENGAGEMENT)
            engagement_id = engagement.get("engagementId")
            yield ("engagement", {
                "engagement_id": engagement_id,
                "type_porteur": porteur,
                "id_porteur": id_porteur,
                "num_finess_porteur": None,
                "rang": str(rang),
                "code_type_engagement": engagement.get("typeEngagement"),
                "code_sous_type_engagement": engagement.get("sousTypeEngagement"),
                "nom_engagement": engagement.get("nomEngagement"),
                "identifiant_engagement": engagement.get("identifiantEngagement"),
                "code_motif_arrete": engagement.get("motifArrete"),
                "date_effet": engagement.get("dateEffetEngagement"),
                "date_signature": engagement.get("dateSignatureEngagement"),
                "date_fin": engagement.get("dateFinEngagement"),
                "date_notification": engagement.get("dateNotificationEngagement"),
                "date_caducite": engagement.get("dateCaduciteEngagement"),
                "id_lot": lot.identifiant,
            })
            for rang_autorite, autorite in enumerate(
                    engagement.get("autoriteRegulationEngagement") or []):
                fc.controler_cles(contexte, f"{porteur}.engagement.autoriteRegulation",
                                  autorite, fc.CLES_AUTORITE)
                yield ("engagement_autorite", {
                    "engagement_id": engagement_id,
                    "rang": str(rang_autorite),
                    "code_autorite_regulation": autorite.get("autoriteRegulationid"),
                    "id_lot": lot.identifiant,
                })

    def _evenements(self, evenements, porteur: str, id_porteur: Optional[str],
                    contexte: ContexteSource) -> Iterator[Tuple[str, Dict[str, Any]]]:
        lot = contexte.lot
        for rang, evenement in enumerate(evenements or []):
            fc.controler_cles(contexte, f"{porteur}.evenement", evenement,
                              fc.CLES_EVENEMENT)
            yield ("evenement", {
                "evenement_id": evenement.get("evenementId"),
                "type_porteur": porteur,
                "id_porteur": id_porteur,
                "rang": str(rang),
                "code_evenement": evenement.get("codeEvenement"),
                "date_evenement": evenement.get("dateEvenement"),
                "date_enregistrement": evenement.get("dateEnregistrement"),
                "code_etat_objet_1": evenement.get("etatObjet1"),
                "code_type_objet_1": evenement.get("typeObjet1"),
                "identifiant_objet_1": evenement.get("identifiantObjet1"),
                "code_type_objet_2": evenement.get("typeObjet2"),
                "identifiant_objet_2": evenement.get("identifiantObjet2"),
                "code_systeme_maitre": evenement.get("systemeMaitre"),
                "id_lot": lot.identifiant,
            })


# ---------------------------------------------------------------------------
# Inspection en ligne de commande
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import resource

    from contrat_source import (CONTROLE_ECHANTILLON, CONTROLE_MINIMAL, CONTROLE_STRICT,
                                InventaireCodes, Lot, RapportIngestion, RegistreAnomalies,
                                parcourir_source)

    analyseur = argparse.ArgumentParser(description="Ingestion du fichier FINESS activités.")
    analyseur.add_argument("fichier", type=Path)
    analyseur.add_argument("--controle", default=CONTROLE_ECHANTILLON,
                           choices=[CONTROLE_MINIMAL, CONTROLE_ECHANTILLON, CONTROLE_STRICT])
    analyseur.add_argument("--codes", action="store_true")
    arguments = analyseur.parse_args()

    rapport = RapportIngestion(Lot("", "", "", "", 0), RegistreAnomalies(),
                               InventaireCodes(), arguments.controle)
    for _nom, _ligne in parcourir_source(SourceFinessActivites(), arguments.fichier,
                                         controle=arguments.controle, rapport=rapport):
        pass

    print(rapport.texte())
    print(f"RSS max    : {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.1f} Mio")
    if arguments.codes:
        for domaine in rapport.inventaire.domaines():
            valeurs = rapport.inventaire.valeurs(domaine)
            print(f"\n{domaine} ({len(valeurs)} distincts) : {list(valeurs.items())[:10]}")
