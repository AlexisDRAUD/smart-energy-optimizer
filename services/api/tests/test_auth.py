from fastapi.testclient import TestClient


def test_login_returns_short_lived_bearer_and_identity(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "camille.martin@enervision.demo", "password": "EnerVisionDemo2026!"},
    )

    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["expires_in"] == 15 * 60
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["email"] == "camille.martin@enervision.demo"
    assert me.json()["role"] == "admin"
    assert me.json()["created_at"].endswith("Z")


def test_authentication_and_validation_use_contract_error_shape(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    rejected = client.post(
        "/api/v1/auth/login",
        json={"email": "camille.martin@enervision.demo", "password": "wrong"},
    )
    invalid = client.get("/api/v1/readings", headers=auth_headers)

    assert rejected.status_code == 401
    assert rejected.json()["error"]["code"] == "unauthorized"
    assert invalid.status_code == 422
    assert set(invalid.json()) == {"error"}
