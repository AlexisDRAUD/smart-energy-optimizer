import os


def database_url() -> str:
    return os.environ["DATABASE_URL"]


def source_api_url() -> str:
    return os.environ.get("SOURCE_API_BASE_URL", "http://127.0.0.1:8000")
