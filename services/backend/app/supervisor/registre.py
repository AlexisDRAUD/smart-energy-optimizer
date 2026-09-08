"""Le seuil d un modele, lu dans le registre MLflow.

L entrainement (services/ml/main.py) logge la MAE holdout de chaque modele
dans le run qui enregistre sa version. Le seuil d un site est cette MAE
multipliee par une tolerance : en production, le modele a le droit de se
tromper un peu plus qu a l entrainement, pas beaucoup plus. Un seuil fixe en
kWh ne convient pas, les sites n ont pas la meme echelle de consommation.

On passe par l API REST de MLflow avec httpx plutot que par le client mlflow :
le backend n embarque pas ce paquet et n a pas a le faire pour lire deux
champs. Deux appels : la version du modele donne son run, le run donne ses
metriques.

Tout echec rend None : MLflow injoignable, modele ou version inconnus,
metrique absente. L ordonnanceur ne juge alors pas la derive et seul le filet
s applique. L echec est journalise, pas propage : un MLflow en panne ne doit
pas arreter le superviseur.
"""

from __future__ import annotations

import logging

import httpx

from app.supervisor.scheduler import SourceDeSeuil

LOGGER = logging.getLogger(__name__)

METRIQUE = "mae"


def seuil_mlflow(
    tracking_uri: str,
    prefixe_modele: str,
    tolerance: float,
    client: httpx.Client | None = None,
) -> SourceDeSeuil:
    """Seuil = MAE holdout de la version en production x tolerance."""
    if tolerance <= 0:
        raise ValueError("La tolerance doit etre strictement positive")
    base = tracking_uri.rstrip("/")
    http = client or httpx.Client(timeout=5.0)

    def source(site_id: str, version: str) -> float | None:
        nom = f"{prefixe_modele}_{site_id}"
        try:
            run_id = _run_de_la_version(http, base, nom, version)
            mae = _metrique(http, base, run_id, METRIQUE)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as erreur:
            LOGGER.warning("Seuil indisponible pour %s version %s : %s", nom, version, erreur)
            return None
        if mae is None:
            LOGGER.warning(
                "Seuil indisponible pour %s version %s : pas de %s", nom, version, METRIQUE
            )
            return None
        return mae * tolerance

    return source


def _run_de_la_version(http: httpx.Client, base: str, nom: str, version: str) -> str:
    reponse = http.get(
        f"{base}/api/2.0/mlflow/model-versions/get",
        params={"name": nom, "version": version},
    )
    reponse.raise_for_status()
    return str(reponse.json()["model_version"]["run_id"])


def _metrique(http: httpx.Client, base: str, run_id: str, cle: str) -> float | None:
    reponse = http.get(f"{base}/api/2.0/mlflow/runs/get", params={"run_id": run_id})
    reponse.raise_for_status()
    metriques = reponse.json()["run"]["data"].get("metrics", [])
    for metrique in metriques:
        if metrique["key"] == cle:
            return float(metrique["value"])
    return None
