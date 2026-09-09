"""Le seuil d un modele, lu dans le registre MLflow.

L entrainement (services/ml/main.py) logge les metriques de chaque modele dans
le run qui enregistre sa version. Le seuil d un site vient de ce run, dans cet
ordre :

1. `drift_threshold_mae`, si l entrainement l a posee : c est le seuil choisi
   pour ce modele, on le prend tel quel.
2. A defaut, `mae` (la MAE holdout) multipliee par une tolerance, 1,5 par
   defaut : en production, le modele a le droit de se tromper un peu plus qu a
   l entrainement, pas beaucoup plus. Un seuil fixe en kWh ne convient pas, les
   sites n ont pas la meme echelle de consommation.

On passe par l API REST de MLflow avec httpx plutot que par le client mlflow :
le backend n embarque pas ce paquet et n a pas a le faire pour lire deux
champs. Deux appels : la version du modele donne son run, le run donne ses
metriques.

Tout echec rend None : MLflow injoignable, modele ou version inconnus (la
regle simple de l API n est pas dans le registre), aucune des deux metriques.
L ordonnanceur declare alors le site sans supervision et passe au suivant.
L echec est journalise, pas propage : un MLflow en panne ne doit pas arreter
le superviseur.
"""

from __future__ import annotations

import logging

import httpx

from app.supervisor.scheduler import SourceDeSeuil

LOGGER = logging.getLogger(__name__)

METRIQUE_SEUIL = "drift_threshold_mae"
METRIQUE_MAE = "mae"
TOLERANCE = 1.5


def seuil_mlflow(
    tracking_uri: str,
    prefixe_modele: str,
    tolerance: float = TOLERANCE,
    client: httpx.Client | None = None,
) -> SourceDeSeuil:
    """Seuil = drift_threshold_mae du run, a defaut MAE holdout x tolerance."""
    if tolerance <= 0:
        raise ValueError("La tolerance doit etre strictement positive")
    base = tracking_uri.rstrip("/")
    http = client or httpx.Client(timeout=5.0)

    def source(site_id: str, version: str) -> float | None:
        nom = f"{prefixe_modele}_{site_id}"
        try:
            run_id = _run_de_la_version(http, base, nom, version)
            metriques = _metriques(http, base, run_id)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as erreur:
            LOGGER.warning("Seuil indisponible pour %s version %s : %s", nom, version, erreur)
            return None
        if METRIQUE_SEUIL in metriques:
            return metriques[METRIQUE_SEUIL]
        if METRIQUE_MAE in metriques:
            return metriques[METRIQUE_MAE] * tolerance
        LOGGER.warning(
            "Seuil indisponible pour %s version %s : ni %s ni %s dans le run",
            nom,
            version,
            METRIQUE_SEUIL,
            METRIQUE_MAE,
        )
        return None

    return source


def _run_de_la_version(http: httpx.Client, base: str, nom: str, version: str) -> str:
    reponse = http.get(
        f"{base}/api/2.0/mlflow/model-versions/get",
        params={"name": nom, "version": version},
    )
    reponse.raise_for_status()
    return str(reponse.json()["model_version"]["run_id"])


def _metriques(http: httpx.Client, base: str, run_id: str) -> dict[str, float]:
    reponse = http.get(f"{base}/api/2.0/mlflow/runs/get", params={"run_id": run_id})
    reponse.raise_for_status()
    metriques = reponse.json()["run"]["data"].get("metrics", [])
    return {m["key"]: float(m["value"]) for m in metriques}
