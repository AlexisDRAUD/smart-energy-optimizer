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


def test_model_contract_has_local_mlflow_fallback_and_metrics(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    model = client.get("/api/v1/model", headers=auth_headers)
    performance = client.get("/api/v1/model/performance?site_id=LYO-01", headers=auth_headers)

    assert model.status_code == 200
    assert model.json()["availability"] == "local_fallback"
    assert model.json()["model_name"] == "local-moving-average"
    assert model.json()["model_version"] == "local-1"
    assert model.json()["trained_at"] is None
    assert set(model.json()["test_metrics"]) == {"mae", "rmse", "mape_percent"}
    assert model.json()["mlflow_available"] is False
    assert performance.status_code == 200
    assert performance.json()["sample_size"] == 1
    assert performance.json()["model"]["mae"] is not None
    assert set(performance.json()) == {
        "sample_size",
        "model",
        "persistence_baseline",
        "linear_baseline",
    }
