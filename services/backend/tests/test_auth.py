from app.api.v1.endpoints.auth import REFRESH_COOKIE_NAME
from app.core.security import create_refresh_token
from fastapi.testclient import TestClient


def _login(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "camille.martin@enervision.demo", "password": "EnerVisionDemo2026!"},
    )
    assert response.status_code == 200
    return response.json()


def test_login_returns_short_lived_bearer_and_identity(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "camille.martin@enervision.demo", "password": "EnerVisionDemo2026!"},
    )

    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["expires_in"] == 60 * 60
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


def test_login_sets_an_http_only_refresh_cookie(client: TestClient) -> None:
    _login(client)

    assert REFRESH_COOKIE_NAME in client.cookies
    cookie_header = client.post(
        "/api/v1/auth/login",
        json={"email": "camille.martin@enervision.demo", "password": "EnerVisionDemo2026!"},
    ).headers["set-cookie"]
    assert "HttpOnly" in cookie_header
    assert "Path=/api/v1/auth" in cookie_header


def test_refresh_returns_a_new_access_token_accepted_by_the_api(client: TestClient) -> None:
    _login(client)

    refreshed = client.post("/api/v1/auth/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
    assert "set-cookie" in refreshed.headers
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert me.status_code == 200


def test_refresh_without_cookie_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_logout_clears_the_session_and_blocks_further_refresh(client: TestClient) -> None:
    _login(client)

    logout = client.post("/api/v1/auth/logout")

    assert logout.status_code == 204
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_a_refresh_token_cannot_be_used_as_an_access_token(client: TestClient) -> None:
    stolen = create_refresh_token("camille.martin@enervision.demo")

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {stolen}"})

    assert response.status_code == 401
