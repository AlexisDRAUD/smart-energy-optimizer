from fastapi.testclient import TestClient


def test_seeded_sites_are_listed(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/sites", headers=auth_headers)

    assert response.status_code == 200
    assert [site["code"] for site in response.json()] == ["LYO-01"]


def test_current_reading_is_persisted(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/sites/1/current", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["site_id"] == 1


def test_user_cannot_access_another_site(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/sites/2", headers=auth_headers)

    assert response.status_code == 403