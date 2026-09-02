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
    recommendations = client.get(
        "/api/v1/recommendations?site_id=LYO-01", headers=viewer_headers
    )

    assert overview.status_code == 200
    assert overview.json()["site_count"] == 3
    assert overview.json()["incomplete"] is False
    assert quality.status_code == 200
    assert quality.json()["total"] == 1
    assert sensors.status_code == 200
    assert len(sensors.json()["items"][0]["sensors"]) == 5
    assert service_status.status_code == 200
    assert service_status.json()["etl"]["last_result"] == "ok"
    assert recommendations.status_code == 200
    assert "estimated_savings_kwh" in recommendations.json()["recommendations"][0]
