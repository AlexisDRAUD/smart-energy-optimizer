from fastapi.testclient import TestClient


def test_admin_acknowledges_all_open_critical_alerts(
    client: TestClient,
    database,
    auth_headers: dict[str, str],
    viewer_headers: dict[str, str],
) -> None:
    from datetime import UTC, datetime

    from app.db.models.alert import Alert
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        alert = Alert(
            site_id="LYO-01",
            detected_at=datetime.now(UTC),
            type="outage",
            severity="critical",
            message="Critique à acquitter en test",
            value=900,
            threshold_value=850,
            status="open",
            origin="source",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        alert_id = alert.id

    forbidden = client.post("/api/v1/alerts/acknowledge-all-critical", headers=viewer_headers)
    assert forbidden.status_code == 403

    acknowledged = client.post("/api/v1/alerts/acknowledge-all-critical", headers=auth_headers)
    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged_count"] >= 1

    with SessionLocal() as db:
        stored = db.get(Alert, alert_id)
        assert stored is not None
        assert stored.status == "acknowledged"
        assert stored.acknowledged_at is not None
        db.delete(stored)
        db.commit()


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
        "origin",
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
