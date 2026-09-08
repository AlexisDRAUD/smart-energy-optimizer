import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models.quality import SensorStatus
from app.db.session import SessionLocal
from app.etl.main import load_sensor_directory
from sqlalchemy import delete, select, text

SITE_ID = "SEN-01"
SENSORS = ("consumption", "electrical", "temperature", "humidity", "network")
# Loin de l historique du seed : ce module ne doit rien changer aux observations
# que les autres tests regardent.
FIRST_AT = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _snapshot(received_at: datetime, status: str) -> None:
    """Ecrit un instantane de capteurs comme le ferait le collecteur."""
    payload = {SITE_ID: {"sensors": {sensor: {"status": status} for sensor in SENSORS}}}
    with SessionLocal() as db:
        db.execute(
            text(
                "INSERT INTO raw_snapshots (source, received_at, payload) "
                "VALUES ('api_sensors', :received_at, CAST(:payload AS jsonb))"
            ),
            {"received_at": received_at, "payload": json.dumps(payload)},
        )
        db.commit()


def _observed_at() -> list[datetime]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(SensorStatus.observed_at)
                .where(SensorStatus.site_id == SITE_ID, SensorStatus.sensor == "consumption")
                .order_by(SensorStatus.observed_at)
            )
        )


@pytest.fixture
def three_snapshots(database: None) -> Generator[None, None, None]:
    """Trois instantanes a une minute d ecart, dont un changement d etat."""
    _snapshot(FIRST_AT, "ok")
    _snapshot(FIRST_AT + timedelta(minutes=1), "failing")
    _snapshot(FIRST_AT + timedelta(minutes=2), "ok")
    yield
    with SessionLocal() as db:
        db.execute(delete(SensorStatus).where(SensorStatus.site_id == SITE_ID))
        db.execute(
            text("DELETE FROM raw_snapshots WHERE source = 'api_sensors' AND payload ? :site_id"),
            {"site_id": SITE_ID},
        )
        db.commit()


def test_every_snapshot_of_the_window_is_historised(three_snapshots: None) -> None:
    """Le coeur du sujet : un seul passage doit rattraper tout son retard."""
    with SessionLocal() as db:
        load_sensor_directory(db, FIRST_AT, FIRST_AT + timedelta(minutes=10))

    assert _observed_at() == [
        FIRST_AT,
        FIRST_AT + timedelta(minutes=1),
        FIRST_AT + timedelta(minutes=2),
    ]


def test_the_intermediate_failure_survives(three_snapshots: None) -> None:
    """Un capteur tombe puis reparti entre deux passages laissait zero trace."""
    with SessionLocal() as db:
        load_sensor_directory(db, FIRST_AT, FIRST_AT + timedelta(minutes=10))

    with SessionLocal() as db:
        statuses = list(
            db.scalars(
                select(SensorStatus.status)
                .where(SensorStatus.site_id == SITE_ID, SensorStatus.sensor == "network")
                .order_by(SensorStatus.observed_at)
            )
        )

    assert statuses == ["ok", "failing", "ok"]


def test_replaying_the_window_changes_nothing(three_snapshots: None) -> None:
    with SessionLocal() as db:
        load_sensor_directory(db, FIRST_AT, FIRST_AT + timedelta(minutes=10))
        load_sensor_directory(db, FIRST_AT, FIRST_AT + timedelta(minutes=10))

    assert len(_observed_at()) == 3


def test_a_snapshot_after_the_window_is_left_to_the_next_pass(three_snapshots: None) -> None:
    """La fenetre borne le travail : rien n est saute, rien n est pris d avance."""
    with SessionLocal() as db:
        load_sensor_directory(db, FIRST_AT, FIRST_AT + timedelta(minutes=2))

    assert _observed_at() == [FIRST_AT, FIRST_AT + timedelta(minutes=1)]

    with SessionLocal() as db:
        load_sensor_directory(db, FIRST_AT + timedelta(minutes=2), FIRST_AT + timedelta(minutes=10))

    assert len(_observed_at()) == 3
