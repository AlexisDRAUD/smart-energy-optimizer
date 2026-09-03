import pytest

from tests.database_safety import validate_test_database_url


def test_main_database_is_refused_even_when_its_name_ends_with_test() -> None:
    main_url = "postgresql+psycopg://seo:secret@db:5432/seo_test"

    with pytest.raises(RuntimeError, match="must not target the DATABASE_URL database"):
        validate_test_database_url(main_url, main_url)


def test_database_name_must_end_with_test() -> None:
    with pytest.raises(RuntimeError, match="must end with '_test'"):
        validate_test_database_url(
            "postgresql+psycopg://seo:secret@db:5432/seo",
            "postgresql+psycopg://seo:secret@db:5432/seo",
        )


def test_application_database_url_is_required_for_comparison() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        validate_test_database_url(
            "postgresql+psycopg://seo:secret@db:5432/seo_test",
            None,
        )


def test_distinct_test_database_is_accepted_with_short_timeout() -> None:
    validated = validate_test_database_url(
        "postgresql+psycopg://seo:secret@db:5432/seo_test",
        "postgresql+psycopg://seo:secret@db:5432/seo",
    )

    assert validated.database == "seo_test"
    assert validated.query["connect_timeout"] == "3"
