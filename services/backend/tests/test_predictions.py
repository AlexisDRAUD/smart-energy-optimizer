from datetime import UTC, datetime, timedelta

from app.db.models.prediction import Prediction
from app.db.models.site import Site
from app.db.session import SessionLocal
from fastapi.testclient import TestClient
from sqlalchemy import delete


def test_predictions_use_dedicated_service_table_and_null_score_keys(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/predictions/latest?site_id=LYO-01", headers=auth_headers)
    history = client.get("/api/v1/predictions?site_id=LYO-01", headers=auth_headers)

    assert response.status_code == 200
    assert set(response.json()) == {
        "site_id",
        "predicted_at",
        "target_at",
        "horizon_minutes",
        "predicted_kwh",
        "model_version",
        "actual_kwh",
        "absolute_error",
    }
    assert response.json()["actual_kwh"] is None
    assert "absolute_error" in response.json()
    assert history.status_code == 200
    assert history.json()["total"] >= 1


def test_model_describes_only_what_the_predictions_table_contains(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    model = client.get("/api/v1/model", headers=auth_headers)
    performance = client.get("/api/v1/model/performance?site_id=LYO-01", headers=auth_headers)
    latest = client.get("/api/v1/predictions/latest?site_id=LYO-01", headers=auth_headers)

    assert model.status_code == 200
    assert set(model.json()) == {
        "model_name",
        "model_version",
        "horizon_minutes",
        "last_prediction_at",
        "predictions_total",
        "predictions_scored",
    }
    # Les valeurs sont celles des lignes ecrites, pas des constantes du code.
    assert model.json()["model_version"] == latest.json()["model_version"]
    assert model.json()["horizon_minutes"] == latest.json()["horizon_minutes"]
    assert model.json()["predictions_total"] >= 1
    assert model.json()["predictions_scored"] <= model.json()["predictions_total"]
    assert model.json()["last_prediction_at"].endswith("Z")
    assert performance.status_code == 200
    assert performance.json()["sample_size"] == 1
    assert performance.json()["model"]["mae"] is not None
    assert set(performance.json()) == {
        "sample_size",
        "model",
        "persistence_baseline",
        "linear_baseline",
    }


def test_model_can_be_scoped_to_a_single_site(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    fleet = client.get("/api/v1/model", headers=auth_headers).json()
    listing = client.get("/api/v1/sites", headers=auth_headers).json()
    sites = [s["site_id"] for s in listing["items"]]

    per_site = {
        site: client.get(f"/api/v1/model?site_id={site}", headers=auth_headers).json()
        for site in sites
    }
    for site, model in per_site.items():
        latest = client.get(
            f"/api/v1/predictions/latest?site_id={site}", headers=auth_headers
        ).json()
        assert model["model_version"] == latest["model_version"]
        assert model["model_name"] is not None
        assert model["predictions_scored"] <= model["predictions_total"]
        assert model["predictions_total"] <= fleet["predictions_total"]

    # Le parc, c'est la somme des sites : rien n'est compte deux fois ni oublie.
    assert sum(m["predictions_total"] for m in per_site.values()) == fleet["predictions_total"]

    missing = client.get("/api/v1/model?site_id=UNKNOWN", headers=auth_headers)
    assert missing.status_code == 404


def test_prediction_history_only_returns_the_sites_active_model(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    site_id = "HIST-ACTIVE"
    base = datetime(2025, 3, 1, tzinfo=UTC)

    def row(predicted_at: datetime, version: str, kwh: float) -> Prediction:
        return Prediction(
            site_id=site_id,
            predicted_at=predicted_at,
            target_at=predicted_at + timedelta(minutes=120),
            horizon_minutes=120,
            model_name=f"EnerVision_RF_Predictor_{site_id}",
            model_version=version,
            predicted_kwh=kwh,
            actual_kwh=None,
            scored_at=None,
        )

    try:
        with SessionLocal() as db:
            db.add(
                Site(
                    site_id=site_id,
                    site_type="office",
                    site_name="hist",
                    location="x",
                    capacity_kw=10,
                    status="active",
                    first_seen_at=base,
                    last_seen_at=base,
                )
            )
            db.add_all(
                [
                    row(base, "1", 100.0),
                    row(base + timedelta(minutes=1), "1", 101.0),
                    # reentrainement : version 2, previsions plus recentes -> modele actif
                    row(base + timedelta(minutes=2), "2", 200.0),
                    row(base + timedelta(minutes=3), "2", 201.0),
                ]
            )
            db.commit()

        body = client.get(f"/api/v1/predictions?site_id={site_id}", headers=auth_headers).json()
        assert body["total"] == 2
        assert {item["model_version"] for item in body["items"]} == {"2"}
    finally:
        with SessionLocal() as db:
            db.execute(delete(Prediction).where(Prediction.site_id == site_id))
            db.execute(delete(Site).where(Site.site_id == site_id))
            db.commit()
