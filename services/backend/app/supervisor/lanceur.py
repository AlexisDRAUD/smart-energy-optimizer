"""Lancer l entrainement d un site, quand l ordonnanceur l a decide.

Le contrat est celui de `scheduler.Lanceur` : un appelable qui recoit le
site_id et rien d autre. L ordonnanceur ne sait pas ce qu il y a derriere, et
c est voulu : la decision et le declenchement n ont pas la meme duree de vie.

Une seule implementation pour l instant. LanceurJournal ecrit une ligne et ne
declenche rien : le point d entree du service ML (services/ml) n est pas encore
appelable proprement par une machine, et le superviseur ne doit pas en
inventer un. Quand il le sera, une seconde implementation prendra sa place
dans __main__.py sans toucher a l ordonnanceur.
"""

from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)


class LanceurJournal:
    """Journalise la demande, ne lance rien."""

    def __call__(self, site_id: str) -> None:
        LOGGER.info(
            "Lancement demande pour %s (journal seulement, aucun entrainement declenche)",
            site_id,
        )
