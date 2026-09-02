from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def test_prediction_matches_reading_shape(client: TestClient, auth_headers: dict[str, str]) -> None:
    current = client.get("/api/v1/sites/1/current", headers=auth_headers)
    prediction = client.get("/api/v1/predictions/sites/1/next", headers=auth_headers)

    assert current.status_code == 200
    assert prediction.status_code == 200
    assert set(prediction.json()) == set(current.json())
    assert prediction.json()["id"] > 0
    assert prediction.json()["site_id"] == 1
    assert prediction.json()["consumption_kwh_raw"] is not None
    assert prediction.json()["consumption_kwh_imputed"] is None
    assert prediction.json()["data_quality"] == "predicted"
    assert prediction.json()["null_reasons"] is None
    assert prediction.json()["source"] == "prediction"
    assert prediction.json()["recorded_at"] == (
        datetime.fromisoformat(
            current.json()["recorded_at"].replace("Z", "+00:00")
        )
        + timedelta(minutes=1)
    ).isoformat()


def test_seeded_predictions_cover_two_future_hours(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/readings?site_id=1", headers=auth_headers)

    assert response.status_code == 200
    readings = response.json()
    assert len(readings) == 1560
    assert sum(reading["source"] == "seed" for reading in readings) == 1440
    assert sum(reading["source"] == "prediction" for reading in readings) == 120
