"""Decider et lancer, sans rien mesurer ni promouvoir.

L ordonnanceur passe chaque site au moniteur puis applique cinq regles, dans
cet ordre. La premiere qui conclut l emporte.

1. Pas de version en production : rien a surveiller. L entrainement initial
   est du ressort du service ML, pas du superviseur.
2. Pas de seuil : la version en production n a pas de modele dans le registre
   MLflow (regle simple de l API, ou registre injoignable). Le site n est pas
   supervise du tout, ni derive ni filet : le premier entrainement d un site
   est une decision manuelle. Un avertissement est journalise, on passe au
   suivant.
3. Verrou : un entrainement a ete demande pour ce site il y a moins de
   `delai_entre_lancements`. On ne redemande pas, que l entrainement soit
   encore en cours ou qu il ait produit un modele juge moins bon et non promu.
   Sans ce verrou, une derive persistante relancerait l entrainement a chaque
   tour.
4. Filet : la version en production est notee depuis plus de `age_maximal` et
   rien n a ete demande depuis aussi longtemps. On reentraine meme sans derive,
   au cas ou le signal d erreur ne remonterait plus rien.
5. Derive : la MAE de decision depasse le seuil du modele, et le modele est
   note depuis au moins `delai_de_grace`. L unite est le temps, pas un nombre
   de points : un modele frais a droit a une journee de donnees avant d etre
   juge.

La fenetre d alerte ne decide rien : quand elle depasse le seuil, un
avertissement est journalise, pour voir venir une derive avant que la fenetre
de decision ne la confirme.

Le lanceur ne recoit que le site_id : c est tout ce qu un entrainement a
besoin de savoir. La raison, la MAE et le seuil restent dans la
DemandeEntrainement rendue par `tour()`, pour le journal.

Tout ce qui touche le monde exterieur est injecte : la liste des sites, la
mesure, la source du seuil, le lanceur et l horloge. Le journal des lancements
est en memoire : un redemarrage l efface, et le filet peut alors demander un
entrainement de plus pour un site dont le modele a passe l age maximal. C est
borne, un par site et par redemarrage, et prefere a une table de plus tant que
le lanceur reel n existe pas.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.contract import utc_now
from app.supervisor.monitoring import RapportSite

LOGGER = logging.getLogger(__name__)

DELAI_ENTRE_LANCEMENTS = timedelta(hours=24)
DELAI_DE_GRACE = timedelta(hours=24)
AGE_MAXIMAL = timedelta(days=7)


@dataclass(frozen=True)
class DemandeEntrainement:
    """Ce que `tour()` rend. Assez pour tracer pourquoi on reentraine."""

    site_id: str
    # "filet" ou "derive".
    raison: str
    demandee_at: datetime
    version_en_production: str
    mae_decision: float | None
    seuil: float | None


# Recoit le site_id, rien d autre.
Lanceur = Callable[[str], None]
# (site_id, version) -> seuil de MAE, ou None quand aucun seuil n est connu.
SourceDeSeuil = Callable[[str, str], float | None]


def seuil_fixe(valeur: float | None) -> SourceDeSeuil:
    """Le meme seuil pour tous les sites et toutes les versions. None : aucun."""

    def source(site_id: str, version: str) -> float | None:
        return valeur

    return source


class Ordonnanceur:
    def __init__(
        self,
        sites: Callable[[], Iterable[str]],
        mesurer: Callable[[str], RapportSite],
        lanceur: Lanceur,
        seuil: SourceDeSeuil,
        horloge: Callable[[], datetime] = utc_now,
        delai_entre_lancements: timedelta = DELAI_ENTRE_LANCEMENTS,
        delai_de_grace: timedelta = DELAI_DE_GRACE,
        age_maximal: timedelta = AGE_MAXIMAL,
    ):
        self.sites = sites
        self.mesurer = mesurer
        self.lanceur = lanceur
        self.seuil = seuil
        self.horloge = horloge
        self.delai_entre_lancements = delai_entre_lancements
        self.delai_de_grace = delai_de_grace
        self.age_maximal = age_maximal
        self._derniers_lancements: dict[str, datetime] = {}

    def tour(self) -> list[DemandeEntrainement]:
        """Un passage sur tous les sites. Rend les demandes emises.

        Un site qui echoue (base, lanceur) n empeche pas d examiner les autres.
        """
        demandes = []
        for site_id in self.sites():
            try:
                demande = self.examiner(site_id)
            except Exception:
                LOGGER.exception("Site %s : examen interrompu", site_id)
                continue
            if demande is not None:
                demandes.append(demande)
        return demandes

    def examiner(self, site_id: str) -> DemandeEntrainement | None:
        maintenant = self.horloge()
        rapport = self.mesurer(site_id)
        version = rapport.version_en_production
        if version is None:
            return None
        seuil = self.seuil(site_id, version)
        if seuil is None:
            LOGGER.warning(
                "Site %s : sans modele MLflow, supervision inactive (version %s)",
                site_id,
                version,
            )
            return None
        raison = self._decider(rapport, seuil, maintenant)
        if raison is None:
            return None
        demande = DemandeEntrainement(
            site_id=site_id,
            raison=raison,
            demandee_at=maintenant,
            version_en_production=version,
            mae_decision=rapport.mae_decision,
            seuil=seuil,
        )
        self.lanceur(site_id)
        self._derniers_lancements[site_id] = maintenant
        LOGGER.info(
            "Site %s : entrainement demande (%s), version %s, MAE %s, seuil %s",
            site_id,
            raison,
            demande.version_en_production,
            demande.mae_decision,
            demande.seuil,
        )
        return demande

    def _decider(self, rapport: RapportSite, seuil: float, maintenant: datetime) -> str | None:
        dernier = self._derniers_lancements.get(rapport.site_id)
        if dernier is not None and maintenant - dernier < self.delai_entre_lancements:
            return None

        notee_depuis = (
            None if rapport.premiere_notation is None else maintenant - rapport.premiere_notation
        )
        if (
            notee_depuis is not None
            and notee_depuis >= self.age_maximal
            and (dernier is None or maintenant - dernier >= self.age_maximal)
        ):
            return "filet"

        self._avertir(rapport, seuil)
        if notee_depuis is None or notee_depuis < self.delai_de_grace:
            return None
        if rapport.mae_decision is not None and rapport.mae_decision > seuil:
            return "derive"
        return None

    @staticmethod
    def _avertir(rapport: RapportSite, seuil: float) -> None:
        if rapport.mae_alerte is not None and rapport.mae_alerte > seuil:
            LOGGER.warning(
                "Site %s : MAE sur 24 h a %.3f, au-dessus du seuil %.3f (%d notees)",
                rapport.site_id,
                rapport.mae_alerte,
                seuil,
                rapport.notees_alerte,
            )
