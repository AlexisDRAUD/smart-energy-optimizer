from fastapi.testclient import TestClient


def test_summary_uses_local_seeded_database(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/stats/summary", headers=auth_headers)

    assert response.status_code == 200
    summary = response.json()
    assert summary["site_count"] == 1
    assert summary["reading_count"] == 1560
    assert summary["active_alert_count"] == 0