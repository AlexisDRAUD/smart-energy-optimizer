from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def test_readings_aggregate_paginate_and_report_completeness(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=2)
    response = client.get(
        "/api/v1/readings",
        headers=viewer_headers,
        params={
            "site_id": "LYO-01",
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "granularity": "hour",
            "limit": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["site_id"] == "LYO-01"
    assert body["granularity"] == "hour"
    assert len(body["points"]) == 1
    assert body["total"] == 2
    assert body["completeness"]["expected_points"] == 2
    assert body["completeness"]["received_points"] == 2
    assert set(body["points"][0]) == {
        "measured_at",
        "consumption_kwh",
        "is_imputed",
        "data_quality",
    }


def test_empty_or_invalid_reading_windows_follow_contract(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    empty = client.get(
        "/api/v1/readings",
        headers=auth_headers,
        params={
            "site_id": "LYO-01",
            "start": "2020-01-01T00:00:00Z",
            "end": "2020-01-01T01:00:00Z",
        },
    )
    invalid = client.get(
        "/api/v1/readings",
        headers=auth_headers,
        params={
            "site_id": "LYO-01",
            "start": "2026-01-01T00:00:00",
            "end": "2026-01-01T01:00:00Z",
        },
    )

    assert empty.status_code == 200
    assert empty.json()["points"] == []
    assert empty.json()["completeness"]["missing_points"] == 60
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
