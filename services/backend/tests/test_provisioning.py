from fastapi.testclient import TestClient


def test_only_admin_manages_accounts(
    client: TestClient,
    auth_headers: dict[str, str],
    viewer_headers: dict[str, str],
) -> None:
    denied = client.post(
        "/api/v1/users",
        headers=viewer_headers,
        json={
            "email": "new.viewer@example.com",
            "password": "LongEnoughPassword2026!",
            "role": "viewer",
        },
    )
    created = client.post(
        "/api/v1/users",
        headers=auth_headers,
        json={
            "email": "new.viewer@example.com",
            "password": "LongEnoughPassword2026!",
            "role": "viewer",
        },
    )

    assert denied.status_code == 403
    assert created.status_code == 201
    assert created.json()["role"] == "viewer"
    removed = client.post("/api/v1/provisioning/users")
    assert removed.status_code == 404
    assert removed.json()["error"]["code"] == "not_found"
