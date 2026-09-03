import os


def db_config() -> dict:
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": os.environ.get("POSTGRES_PORT", "5432"),
        "user": os.environ.get("POSTGRES_USER", "seo"),
        "password": os.environ["POSTGRES_PASSWORD"],
        "dbname": os.environ.get("POSTGRES_DB", "seo"),
    }


def source_api_url() -> str:
    return os.environ.get("SOURCE_API_BASE_URL", "http://127.0.0.1:8000")
