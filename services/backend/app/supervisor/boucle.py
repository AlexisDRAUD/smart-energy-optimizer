"""La boucle du superviseur : un tour, une attente, recommencer.

Meme modele que le collecteur et l ETL : la cadence vient d une boucle dans le
processus, pas d un ordonnanceur externe. Pas de cron a installer, et un
conteneur qui redemarre en boucle est plus difficile a diagnostiquer qu un
journal qui repete la meme erreur : un tour en echec est journalise, le
suivant repart.

La tolerance par site est dans l ordonnanceur (un site en erreur n empeche pas
d examiner les autres). Ici on protege le tour entier : la liste des sites qui
ne repond pas, une base tombee au mauvais moment.

L attente est injectee pour que les tests ne dorment pas.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.site import Site

LOGGER = logging.getLogger(__name__)


class Boucle:
    def __init__(
        self,
        ordonnanceur,
        intervalle_secondes: int,
        attendre: Callable[[float], None] = time.sleep,
    ):
        self.ordonnanceur = ordonnanceur
        self.intervalle_secondes = intervalle_secondes
        self.attendre = attendre

    def run(self) -> None:
        """Boucle sans fin. Un tour rate n arrete pas le superviseur."""
        LOGGER.info("Superviseur demarre, un tour toutes les %d s", self.intervalle_secondes)
        while True:
            try:
                demandes = self.ordonnanceur.tour()
                LOGGER.info("Tour termine : %d demande(s) d entrainement", len(demandes))
            except Exception:
                LOGGER.exception("Tour de supervision en echec, reprise au prochain tour")
            self.attendre(self.intervalle_secondes)


def sites_actifs(session_factory: Callable[[], Session]) -> Callable[[], list[str]]:
    """La liste des sites a surveiller, relue a chaque tour.

    Les sites viennent de la table `sites`, alimentee par la chaine de
    collecte. Un site desactive sort de la surveillance au tour suivant, un
    nouveau site y entre des que l API a emis sa premiere prediction.
    """

    def lister() -> list[str]:
        with session_factory() as db:
            return list(
                db.scalars(
                    select(Site.site_id).where(Site.status == "active").order_by(Site.site_id)
                )
            )

    return lister
