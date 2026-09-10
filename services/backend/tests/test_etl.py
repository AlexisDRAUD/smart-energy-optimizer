from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def test_dashboard_data_is_served_from_transformed_tables(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    now = datetime.now(UTC)
    overview = client.get("/api/v1/overview", headers=viewer_headers)
    quality = client.get(
        "/api/v1/quality",
        headers=viewer_headers,
        params={
            "site_id": "LYO-01",
            "start": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "end": now.isoformat().replace("+00:00", "Z"),
        },
    )
    sensors = client.get("/api/v1/quality/sensors", headers=viewer_headers)
    service_status = client.get("/api/v1/status", headers=viewer_headers)

    assert overview.status_code == 200
    assert overview.json()["site_count"] == 3
    assert overview.json()["incomplete"] is False
    # Chaque site expose sa prevision H+2 en cours (derniere ligne de predictions).
    sites_with_prediction = [s for s in overview.json()["by_site"] if s["prediction"] is not None]
    assert sites_with_prediction, "le seed pose une prevision par site"
    sample = sites_with_prediction[0]["prediction"]
    assert sample["horizon_minutes"] == 120
    assert isinstance(sample["predicted_kwh"], (int, float))
    assert sample["model_name"] and sample["model_version"]
    assert quality.status_code == 200
    assert quality.json()["total"] == 1
    assert sensors.status_code == 200
    site_sensors = sensors.json()["items"][0]
    assert site_sensors["sensors"], "le seed pose des observations pour ce site"
    assert all(sensor["observed_at"] is not None for sensor in site_sensors["sensors"])
    assert site_sensors["overall"] in {"ok", "failing"}
    assert service_status.status_code == 200
    assert service_status.json()["etl"]["last_result"] == "ok"
