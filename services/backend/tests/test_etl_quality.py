from collections.abc import Generator
from datetime import UTC, datetime, time, timedelta

import pytest
from app.db.models.quality import DataQualityDaily
from app.db.models.reading import Reading
from app.db.models.site import Site
from app.db.session import SessionLocal
from app.etl.main import run_once
from app.etl.quality import (
    MINUTES_PER_DAY,
    compute_daily_quality,
    days_touched,
    expected_points,
)
from sqlalchemy import delete, select

SITE_ID = "QUA-01"
# Un jour bien avant l historique du seed : ce module ne doit rien changer aux
# journees que les autres tests observent.
DAY = (datetime.now(UTC) - timedelta(days=30)).date()
DAY_START = datetime.combine(DAY, time.min, tzinfo=UTC)


def _reading(minute: int, raw: float | None, imputed: bool) -> Reading:
    return Reading(
        site_id=SITE_ID,
        measured_at=DAY_START + timedelta(minutes=minute),
        consumption_kwh=raw if raw is not None else 100.0 if imputed else None,
        consumption_kwh_raw=raw,
        is_imputed=imputed,
        imputation_method="report" if imputed else None,
        temperature_celsius=None,
        humidity_percent=None,
        data_quality="good" if raw is not None else "partial",
        null_reasons=[] if raw is not None else ["sensor_failure"],
        ingested_at=DAY_START,
    )


@pytest.fixture
def measured_day(database: None) -> Generator[None, None, None]:
    """Une journee de mesures : trois valeurs recues, deux nulles dont une reparee."""
    with SessionLocal() as db:
        db.add(
            Site(
                site_id=SITE_ID,
                site_type="office",
                site_name="Site de qualite",
                location="Niort, France",
                capacity_kw=100,
                status="active",
                first_seen_at=DAY_START,
                last_seen_at=DAY_START,
            )
        )
        db.add_all(
            [
                _reading(0, 10.0, False),
                _reading(1, 11.0, False),
                _reading(2, None, True),
                _reading(3, None, False),
                _reading(4, 12.0, False),
            ]
        )
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(delete(DataQualityDaily).where(DataQualityDaily.day == DAY))
        db.execute(delete(Reading).where(Reading.site_id == SITE_ID))
        db.execute(delete(Site).where(Site.site_id == SITE_ID))
        db.commit()


def _summary(site_id: str) -> DataQualityDaily | None:
    with SessionLocal() as db:
        return db.scalar(
            select(DataQualityDaily).where(
                DataQualityDaily.site_id == site_id, DataQualityDaily.day == DAY
            )
        )


def test_summary_counts_received_null_and_imputed_points(measured_day: None) -> None:
    with SessionLocal() as db:
        compute_daily_quality(db, [DAY])

    summary = _summary(SITE_ID)
    assert summary is not None
    assert summary.expected_points == MINUTES_PER_DAY
    assert summary.received_points == 5
    # Ce qui n est jamais arrive : le trou de collecte.
    assert summary.missing_points == MINUTES_PER_DAY - 5
    # Recus sans valeur, que la reparation les ait remplis ou non.
    assert summary.null_points == 2
    assert summary.imputed_points == 1


def test_a_site_silent_all_day_gets_a_zero_summary(measured_day: None) -> None:
    """Sans ligne, le trou ne se lit nulle part ailleurs : il faut l ecrire."""
    with SessionLocal() as db:
        compute_daily_quality(db, [DAY])

    summary = _summary("LYO-01")
    assert summary is not None
    assert summary.received_points == 0
    assert summary.missing_points == MINUTES_PER_DAY


def test_recomputing_the_same_day_writes_the_same_figures(measured_day: None) -> None:
    with SessionLocal() as db:
        compute_daily_quality(db, [DAY])
        first = _summary(SITE_ID)
        assert first is not None
        expected = (first.received_points, first.null_points, first.imputed_points)

        compute_daily_quality(db, [DAY])

    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(DataQualityDaily).where(
                    DataQualityDaily.site_id == SITE_ID, DataQualityDaily.day == DAY
                )
            )
        )

    assert len(rows) == 1
    assert (rows[0].received_points, rows[0].null_points, rows[0].imputed_points) == expected


def test_the_current_day_expects_only_elapsed_minutes() -> None:
    """Sinon la journee pas encore vecue passerait pour un trou de collecte."""
    now = datetime(2026, 9, 8, 8, 30, tzinfo=UTC)

    assert expected_points(now.date(), now) == 8 * 60 + 30 + 1
    assert expected_points(now.date() - timedelta(days=1), now) == MINUTES_PER_DAY
    assert expected_points(now.date() + timedelta(days=1), now) == 0


def test_touched_days_cover_both_bounds() -> None:
    start = datetime(2026, 9, 6, 23, 50, tzinfo=UTC)
    end = datetime(2026, 9, 8, 0, 10, tzinfo=UTC)

    assert days_touched(start, end) == {start.date(), start.date() + timedelta(days=1), end.date()}


def test_the_etl_pass_writes_the_daily_summary(database: None) -> None:
    """Sans cet appel dans la passe, /api/v1/quality reste vide au demarrage."""
    today = datetime.now(UTC).date()
    with SessionLocal() as db:
        db.execute(delete(DataQualityDaily).where(DataQualityDaily.day == today))
        db.commit()

    assert run_once() == 0

    with SessionLocal() as db:
        rows = list(db.scalars(select(DataQualityDaily).where(DataQualityDaily.day == today)))

    assert {row.site_id for row in rows} == {"LYO-01", "GRE-01", "NAN-01"}
    lyon = next(row for row in rows if row.site_id == "LYO-01")
    assert lyon.received_points > 0
    assert lyon.expected_points <= MINUTES_PER_DAY
