from fastapi.testclient import TestClient


def test_readings_preserve_missing_raw_values(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/readings?site_id=1", headers=auth_headers)

    assert response.status_code == 200
    readings = response.json()
    missing_reading = next(reading for reading in readings if reading["consumption_kwh_raw"] is None)
    assert missing_reading["consumption_kwh_imputed"] is not None
    assert missing_reading["null_reasons"] == ["scheduled_sensor_maintenance"]


def test_missing_raw_value_requires_reason(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/readings/sites/1",
        headers=auth_headers,
        json={
            "recorded_at": "2026-09-01T09:00:00Z",
            "consumption_kwh_raw": None,
            "data_quality": "partial",
        },
    )

    assert response.status_code == 422


def test_readings_for_another_site_are_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/readings?site_id=2", headers=auth_headers)

    assert response.status_code == 403