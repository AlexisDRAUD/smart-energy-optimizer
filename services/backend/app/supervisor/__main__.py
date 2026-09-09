"""Point d entree du conteneur `supervisor` : python -m app.supervisor.

Cable les pieces et lance la boucle. Rien ici n est teste directement : c est
de l assemblage, chaque piece l est de son cote.
"""

import logging

from app.config import settings
from app.db.session import SessionLocal
from app.supervisor.boucle import Boucle, sites_actifs
from app.supervisor.config import SupervisorSettings
from app.supervisor.lanceur import LanceurJournal
from app.supervisor.monitoring import Moniteur
from app.supervisor.registre import seuil_mlflow
from app.supervisor.scheduler import Ordonnanceur, seuil_fixe

LOGGER = logging.getLogger("app.supervisor")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # httpx journalise chaque requete en INFO : deux lignes par site et par
    # tour qui noieraient le compte rendu.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    reglages = SupervisorSettings()

    if settings.mlflow_tracking_uri:
        seuil = seuil_mlflow(
            settings.mlflow_tracking_uri,
            settings.mlflow_model_name_prefix,
            tolerance=reglages.mae_tolerance,
        )
    else:
        LOGGER.warning("MLFLOW_TRACKING_URI absent : aucun seuil, supervision inactive partout")
        seuil = seuil_fixe(None)

    moniteur = Moniteur(
        SessionLocal,
        fenetre_decision=reglages.decision_window,
        fenetre_alerte=reglages.alert_window,
    )
    ordonnanceur = Ordonnanceur(
        sites=sites_actifs(SessionLocal),
        mesurer=moniteur.mesurer,
        lanceur=LanceurJournal(),
        seuil=seuil,
        delai_entre_lancements=reglages.lock,
        delai_de_grace=reglages.grace,
        age_maximal=reglages.max_model_age,
    )
    Boucle(ordonnanceur, reglages.interval_seconds).run()
