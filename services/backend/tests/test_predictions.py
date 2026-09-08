from fastapi.testclient import TestClient


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
