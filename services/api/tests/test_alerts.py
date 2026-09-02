from fastapi.testclient import TestClient


def test_alerts_are_paginated_and_operator_acknowledges(
    client: TestClient,
    viewer_headers: dict[str, str],
    operator_headers: dict[str, str],
) -> None:
    listed = client.get("/api/v1/alerts", headers=viewer_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    alert = listed.json()["items"][0]
    assert set(alert) == {
        "id",
        "site_id",
        "detected_at",
        "type",
        "severity",
        "message",
        "value",
        "threshold_value",
        "status",
        "acknowledged_at",
    }

    forbidden = client.post(f"/api/v1/alerts/{alert['id']}/acknowledge", headers=viewer_headers)
    acknowledged = client.post(
        f"/api/v1/alerts/{alert['id']}/acknowledge", headers=operator_headers
    )

    assert forbidden.status_code == 403
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["acknowledged_at"].endswith("Z")


def test_alert_summary_counts_by_severity(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/alerts/summary?period=week", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["by_severity"]["high"] == 1
    assert sum(response.json()["by_day"].values()) == 1
