"""Point d entree du conteneur `supervisor` : python -m app.supervisor.

Cable les pieces et lance la boucle. Rien ici n est teste directement : c est
de l assemblage, chaque piece l est de son cote.
"""

import logging

from app.config import settings
from app.db.session import SessionLocal
from app.supervisor.boucle import Boucle, sites_actifs
from app.supervisor.lanceur import LanceurJournal
from app.supervisor.monitoring import Moniteur
from app.supervisor.registre import seuil_mlflow
from app.supervisor.scheduler import Ordonnanceur, seuil_fixe

LOGGER = logging.getLogger("app.supervisor")

INTERVALLE_SECONDES = 300

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # httpx journalise chaque requete en INFO : deux lignes par site et par
    # tour qui noieraient le compte rendu.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if settings.mlflow_tracking_uri:
        seuil = seuil_mlflow(settings.mlflow_tracking_uri, settings.mlflow_model_name_prefix)
    else:
        LOGGER.warning("MLFLOW_TRACKING_URI absent : aucun seuil, supervision inactive partout")
        seuil = seuil_fixe(None)

    moniteur = Moniteur(SessionLocal)
    ordonnanceur = Ordonnanceur(
        sites=sites_actifs(SessionLocal),
        mesurer=moniteur.mesurer,
        lanceur=LanceurJournal(),
        seuil=seuil,
    )
    Boucle(ordonnanceur, INTERVALLE_SECONDES).run()
