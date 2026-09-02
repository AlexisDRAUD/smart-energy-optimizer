from fastapi.testclient import TestClient


def test_viewer_can_read_full_site_reference(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/sites", headers=viewer_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert {site["site_id"] for site in response.json()["items"]} == {"LYO-01", "GRE-01", "NAN-01"}
    assert set(response.json()["items"][0]) == {
        "site_id",
        "site_type",
        "site_name",
        "location",
        "capacity_kw",
        "status",
        "last_seen_at",
    }


def test_latest_reading_uses_contract_shape(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/sites/LYO-01/latest", headers=auth_headers)

    assert response.status_code == 200
    assert set(response.json()) == {
        "site_id",
        "measured_at",
        "consumption_kwh",
        "consumption_kwh_raw",
        "is_imputed",
        "imputation_method",
        "temperature_celsius",
        "humidity_percent",
        "data_quality",
        "null_reasons",
        "ingested_at",
        "age_seconds",
    }
    assert response.json()["measured_at"].endswith("Z")
