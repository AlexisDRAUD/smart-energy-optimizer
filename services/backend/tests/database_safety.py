"""Pure validation helpers for destructive PostgreSQL test setup."""

from sqlalchemy.engine import URL, make_url


def _database_identity(database_url: URL) -> tuple[str, int, str]:
    host = (database_url.host or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        host = "loopback"
    return host, database_url.port or 5432, database_url.database or ""


def validate_test_database_url(test_url: str, application_url: str | None) -> URL:
    """Validate destructive test configuration without opening a connection."""
    candidate = make_url(test_url)
    if candidate.get_backend_name() != "postgresql" or not candidate.database:
        raise RuntimeError("TEST_DATABASE_URL must point to a PostgreSQL database.")
    if not candidate.database.endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL database name must end with '_test'.")

    if not application_url:
        raise RuntimeError("DATABASE_URL is required to verify that the test database is distinct.")

    application = make_url(application_url)
    if application.get_backend_name() != "postgresql" or not application.database:
        raise RuntimeError("DATABASE_URL must point to a PostgreSQL database.")
    if _database_identity(candidate) == _database_identity(application):
        raise RuntimeError("TEST_DATABASE_URL must not target the DATABASE_URL database.")

    return candidate.update_query_dict({"connect_timeout": "3"})
