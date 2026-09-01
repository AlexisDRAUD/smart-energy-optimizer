import os
from collections.abc import Generator

os.environ["DATABASE_URL"] = "sqlite:///./test_enervision.db"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-with-at-least-32-characters"
os.environ["SEED_USER_PASSWORD"] = "EnerVisionDemo2026!"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "camille.admin", "password": "EnerVisionDemo2026!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}