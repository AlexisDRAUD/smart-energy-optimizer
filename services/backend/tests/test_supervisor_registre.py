"""Tests de la source de seuil MLflow : lire le seuil d une version.

Aucun MLflow ici : les reponses de son API REST sont simulees. Ce qui est
verifie, c est la precedence (drift_threshold_mae si le run la fournit, sinon
MAE holdout x tolerance), les deux appels dans le bon ordre, et surtout que
tout echec rend None sans lever, pour que l ordonnanceur declare le site sans
supervision et passe au suivant.
"""

import json

import httpx
import pytest
from app.supervisor.registre import seuil_mlflow

TRACKING = "http://mlflow:5000"
PREFIXE = "EnerVision_RF_Predictor"


class FauxMlflow:
    """Un registre avec ses versions et ses runs, servi par un transport httpx simule."""

    def __init__(self):
        self.versions: dict[tuple[str, str], str] = {}  # (nom, version) -> run_id
        self.runs: dict[str, dict[str, float]] = {}  # run_id -> metriques
        self.appels: list[str] = []
        self.panne = False

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self._repondre))

    def _repondre(self, requete: httpx.Request) -> httpx.Response:
        self.appels.append(requete.url.path)
        if self.panne:
            raise httpx.ConnectError("connection refused", request=requete)
        params = requete.url.params
        if requete.url.path == "/api/2.0/mlflow/model-versions/get":
            run_id = self.versions.get((params["name"], params["version"]))
            if run_id is None:
                return _erreur(404, "RESOURCE_DOES_NOT_EXIST")
            return httpx.Response(200, json={"model_version": {"run_id": run_id}})
        if requete.url.path == "/api/2.0/mlflow/runs/get":
            metriques = self.runs.get(params["run_id"])
            if metriques is None:
                return _erreur(404, "RESOURCE_DOES_NOT_EXIST")
            return httpx.Response(
                200,
                json={
                    "run": {
                        "data": {"metrics": [{"key": k, "value": v} for k, v in metriques.items()]}
                    }
                },
            )
        return _erreur(404, "ENDPOINT_NOT_FOUND")


def _erreur(statut: int, code: str) -> httpx.Response:
    return httpx.Response(statut, content=json.dumps({"error_code": code}))


@pytest.fixture
def registre() -> FauxMlflow:
    registre = FauxMlflow()
    registre.versions[(f"{PREFIXE}_SITE001", "3")] = "run-abc"
    registre.runs["run-abc"] = {"rmse": 12.5, "mae": 8.0}
    return registre


def test_le_seuil_est_drift_threshold_mae_quand_le_run_la_fournit(registre):
    registre.runs["run-abc"] = {"rmse": 12.5, "mae": 8.0, "drift_threshold_mae": 9.0}
    source = seuil_mlflow(TRACKING, PREFIXE, tolerance=1.5, client=registre.client())

    assert source("SITE001", "3") == pytest.approx(9.0)
    assert registre.appels == ["/api/2.0/mlflow/model-versions/get", "/api/2.0/mlflow/runs/get"]


def test_a_defaut_le_seuil_est_la_mae_holdout_fois_la_tolerance(registre):
    source = seuil_mlflow(TRACKING, PREFIXE, tolerance=1.5, client=registre.client())

    assert source("SITE001", "3") == pytest.approx(12.0)
    assert registre.appels == ["/api/2.0/mlflow/model-versions/get", "/api/2.0/mlflow/runs/get"]


def test_la_tolerance_par_defaut_est_de_une_fois_et_demie(registre):
    source = seuil_mlflow(TRACKING, PREFIXE, client=registre.client())

    assert source("SITE001", "3") == pytest.approx(12.0)


def test_une_tolerance_de_un_rend_la_mae_telle_quelle(registre):
    source = seuil_mlflow(TRACKING, PREFIXE, tolerance=1.0, client=registre.client())

    assert source("SITE001", "3") == pytest.approx(8.0)


def test_une_version_inconnue_ne_donne_pas_de_seuil(registre, caplog):
    source = seuil_mlflow(TRACKING, PREFIXE, tolerance=1.5, client=registre.client())

    with caplog.at_level("WARNING", logger="app.supervisor.registre"):
        assert source("SITE001", "4") is None

    assert "EnerVision_RF_Predictor_SITE001 version 4" in caplog.text


def test_un_site_sans_modele_ne_donne_pas_de_seuil(registre):
    source = seuil_mlflow(TRACKING, PREFIXE, tolerance=1.5, client=registre.client())

    assert source("SITE999", "1") is None


def test_un_run_sans_aucune_des_deux_metriques_ne_donne_pas_de_seuil(registre, caplog):
    registre.runs["run-abc"] = {"rmse": 12.5}
    source = seuil_mlflow(TRACKING, PREFIXE, tolerance=1.5, client=registre.client())

    with caplog.at_level("WARNING", logger="app.supervisor.registre"):
        assert source("SITE001", "3") is None

    assert "ni drift_threshold_mae ni mae" in caplog.text


def test_un_mlflow_injoignable_ne_donne_pas_de_seuil_et_ne_leve_pas(registre, caplog):
    registre.panne = True
    source = seuil_mlflow(TRACKING, PREFIXE, tolerance=1.5, client=registre.client())

    with caplog.at_level("WARNING", logger="app.supervisor.registre"):
        assert source("SITE001", "3") is None

    assert "Seuil indisponible" in caplog.text


def test_une_reponse_mal_formee_ne_leve_pas():
    def repondre(requete: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"inattendu": True})

    client = httpx.Client(transport=httpx.MockTransport(repondre))
    source = seuil_mlflow(TRACKING, PREFIXE, tolerance=1.5, client=client)

    assert source("SITE001", "3") is None


def test_l_adresse_du_registre_supporte_une_barre_finale(registre):
    source = seuil_mlflow(TRACKING + "/", PREFIXE, tolerance=1.5, client=registre.client())

    assert source("SITE001", "3") == pytest.approx(12.0)


def test_une_tolerance_nulle_ou_negative_est_refusee():
    with pytest.raises(ValueError):
        seuil_mlflow(TRACKING, PREFIXE, tolerance=0)
    with pytest.raises(ValueError):
        seuil_mlflow(TRACKING, PREFIXE, tolerance=-1)
