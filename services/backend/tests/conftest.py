import os
from collections.abc import Generator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://seo:change_moi@127.0.0.1:5432/seo_test",
)
test_database_url = make_url(TEST_DATABASE_URL)
if test_database_url.get_backend_name() != "postgresql" or not test_database_url.database:
    raise RuntimeError("TEST_DATABASE_URL must point to a PostgreSQL database.")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET_KEY"] = "test-only-secret-with-at-least-32-characters"
os.environ["SEED_USER_PASSWORD"] = "EnerVisionDemo2026!"


def _admin_database_url() -> str:
    return test_database_url.set(
        drivername="postgresql",
        database="postgres",
    ).render_as_string(hide_password=False)


def _recreate_test_database() -> None:
    with psycopg.connect(_admin_database_url(), autocommit=True) as connection:
        database = sql.Identifier(test_database_url.database)
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(database))
        connection.execute(sql.SQL("CREATE DATABASE {}").format(database))


def _drop_test_database() -> None:
    with psycopg.connect(_admin_database_url(), autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(test_database_url.database)
            )
        )


@pytest.fixture(scope="session", autouse=True)
def database() -> Generator[None, None, None]:
    from app.db.seed import seed_demo_data
    from app.db.session import SessionLocal, engine

    engine.dispose()
    _recreate_test_database()
    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(alembic_config, "head")
    with SessionLocal() as db:
        seed_demo_data(db)
    yield
    engine.dispose()
    _drop_test_database()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    from app.main import app

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
