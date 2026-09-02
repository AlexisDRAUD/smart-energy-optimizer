import os
from collections.abc import Generator
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE = API_ROOT / "test_enervision.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE}"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-with-at-least-32-characters"
os.environ["SEED_USER_PASSWORD"] = "EnerVisionDemo2026!"

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.db.session import engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def database() -> Generator[None, None, None]:
    engine.dispose()
    TEST_DATABASE.unlink(missing_ok=True)
    config = Config(str(API_ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    yield
    engine.dispose()
    TEST_DATABASE.unlink(missing_ok=True)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def _headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "EnerVisionDemo2026!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    return _headers(client, "camille.martin@enervision.demo")


@pytest.fixture
def operator_headers(client: TestClient) -> dict[str, str]:
    return _headers(client, "lucas.bernard@enervision.demo")


@pytest.fixture
def viewer_headers(client: TestClient) -> dict[str, str]:
    return _headers(client, "marc.legrand@enervision.demo")
