import json
from datetime import UTC, datetime, timedelta

from app.db.models.alert import Alert
from app.db.models.site import Site
from app.db.session import SessionLocal
from app.etl.alerts import transform_alert_snapshot
from app.etl.main import load_alert_directory
from sqlalchemy import delete, select, text

START = datetime(2026, 9, 8, 8, 0, tzinfo=UTC)
SITE = "ALERT-SOURCE-01"


def payload(status="active"):
    return {
        "items": [
            {
                "site_id": SITE,
                "triggered_at": "2026-09-08T08:05:00Z",
                "alert_type": "threshold",
                "severity": "warning",
                "message": "Seuil source depasse",
                "current_value": 420.5,
                "threshold": 400,
                "is_active": status == "active",
            }
        ]
    }


def setup_source_alert(database):
    with SessionLocal() as db:
        db.add(
            Site(
                site_id=SITE,
                site_type="office",
                site_name="Alert source",
                location="Paris",
                capacity_kw=500,
                status="active",
                first_seen_at=START,
                last_seen_at=START,
            )
        )
        db.execute(
            text(
                "INSERT INTO raw_snapshots (source, received_at, payload) "
                "VALUES ('api_alerts', :received_at, CAST(:payload AS jsonb))"
            ),
            {"received_at": START, "payload": json.dumps(payload())},
        )
        db.commit()


def cleanup_source_alert():
    with SessionLocal() as db:
        db.execute(delete(Alert).where(Alert.site_id == SITE))
        db.execute(delete(Site).where(Site.site_id == SITE))
        db.execute(text("DELETE FROM raw_snapshots WHERE source = 'api_alerts'"))
        db.commit()


def test_aliases_and_invalid_items_are_validated_independently():
    alerts, rejected = transform_alert_snapshot(
        {"alerts": [payload()["items"][0], {"site_id": "", "message": "bad"}, "bad"]}
    )
    assert rejected == 2
    assert len(alerts) == 1
    assert alerts[0].severity == "medium"
    assert alerts[0].status == "open"
    assert alerts[0].value == 420.5
    assert alerts[0].threshold_value == 400


def test_source_snapshot_is_materialized_replayed_and_exposed(database, client, viewer_headers):
    setup_source_alert(database)
    try:
        with SessionLocal() as db:
            load_alert_directory(db, START - timedelta(seconds=1), START + timedelta(minutes=1))
            load_alert_directory(db, START - timedelta(seconds=1), START + timedelta(minutes=1))
            stored = list(db.scalars(select(Alert).where(Alert.site_id == SITE)))
        assert len(stored) == 1
        assert stored[0].origin == "source"
        assert stored[0].value == 420.5

        response = client.get(
            "/api/v1/alerts",
            headers=viewer_headers,
            params={
                "site_id": SITE,
                "start": "2026-09-08T08:00:00Z",
                "end": "2026-09-08T09:00:00Z",
            },
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["origin"] == "source"
    finally:
        cleanup_source_alert()


def test_replayed_source_state_never_removes_local_acknowledgement(database):
    setup_source_alert(database)
    try:
        with SessionLocal() as db:
            load_alert_directory(db, START - timedelta(seconds=1), START + timedelta(minutes=1))
            alert = db.scalar(select(Alert).where(Alert.site_id == SITE))
            alert.status = "acknowledged"
            db.commit()
            db.execute(
                text(
                    "INSERT INTO raw_snapshots (source, received_at, payload) "
                    "VALUES ('api_alerts', :received_at, CAST(:payload AS jsonb))"
                ),
                {"received_at": START + timedelta(minutes=1), "payload": json.dumps(payload())},
            )
            db.commit()
            load_alert_directory(db, START, START + timedelta(minutes=2))
            db.refresh(alert)
            assert alert.status == "acknowledged"
    finally:
        cleanup_source_alert()
