from fastapi.testclient import TestClient


PROVISIONING_HEADERS = {
    "X-Provisioning-Key": "test-only-provisioning-key-with-32-characters",
}


def test_provisioning_requires_technical_key(client: TestClient) -> None:
    response = client.post(
        "/api/v1/provisioning/users",
        json={
            "username": "lea.manager",
            "email": "lea.manager@example.com",
            "full_name": "Lea Manager",
            "password": "UnMotDePasseRobuste2026!",
            "site_id": 1,
        },
    )

    assert response.status_code == 401


def test_provisioning_creates_user_for_one_site(client: TestClient) -> None:
    response = client.post(
        "/api/v1/provisioning/users",
        headers=PROVISIONING_HEADERS,
        json={
            "username": "lea.manager",
            "email": "lea.manager@example.com",
            "full_name": "Lea Manager",
            "password": "UnMotDePasseRobuste2026!",
            "site_id": 1,
        },
    )

    assert response.status_code == 201
    assert response.json()["site_id"] == 1
