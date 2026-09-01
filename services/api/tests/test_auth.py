from fastapi.testclient import TestClient


def test_seeded_admin_can_obtain_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "camille.admin", "password": "EnerVisionDemo2026!"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_invalid_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "camille.admin", "password": "not-the-demo-password"},
    )

    assert response.status_code == 401