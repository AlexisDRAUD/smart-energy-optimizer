from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import get_password_hash
from app.models.alert import Alert
from app.models.prediction import Prediction
from app.models.quality import DataQualityDaily, EtlRun, SensorStatus
from app.models.reading import Reading
from app.models.site import Site
from app.models.user import User
from app.services.prediction_service import refresh_stored_predictions


def _consumption_value(base_consumption: float, recorded_at: datetime, offset: int) -> float:
    workday_factor = 1.23 if 7 <= recorded_at.hour <= 18 else 0.72
    minute_variation = 1 + (((offset * 7) % 17) - 8) * 0.002
    return round(base_consumption * workday_factor * minute_variation, 2)


def seed_test_data(db: Session) -> None:
    """Populate an isolated PostgreSQL test database after Alembic has created the schema."""
    if db.scalar(select(Site.site_id).limit(1)) is not None:
        _ensure_demo_users(db)
        return

    sites = [
        Site(
            site_id="LYO-01",
            site_type="office",
            site_name="Atelier Lyon Gerland",
            location="Lyon, France",
            capacity_kw=850,
            status="active",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        ),
        Site(
            site_id="GRE-01",
            site_type="factory",
            site_name="Usine Grenoble Sud",
            location="Grenoble, France",
            capacity_kw=1200,
            status="active",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        ),
        Site(
            site_id="NAN-01",
            site_type="warehouse",
            site_name="Entrepôt Nantes Est",
            location="Nantes, France",
            capacity_kw=500,
            status="active",
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        ),
    ]
    db.add_all(sites)
    db.flush()

    _ensure_demo_users(db)

    now = datetime.now(UTC).replace(second=0, microsecond=0)
    history_start = now - timedelta(minutes=1439)
    base_consumption = (278.0, 436.0, 164.0)
    missing_values = {(180, 0), (720, 1), (1260, 2)}
    readings: list[Reading] = []

    for minute_offset in range(1440):
        recorded_at = history_start + timedelta(minutes=minute_offset)
        for index, site in enumerate(sites):
            value = _consumption_value(base_consumption[index], recorded_at, minute_offset + index)
            is_missing = (minute_offset, index) in missing_values
            readings.append(
                Reading(
                    site_id=site.site_id,
                    measured_at=recorded_at,
                    consumption_kwh=value,
                    consumption_kwh_raw=None if is_missing else value,
                    is_imputed=is_missing,
                    imputation_method="report" if is_missing else None,
                    temperature_celsius=20.0 + index,
                    humidity_percent=45.0 + index,
                    data_quality="partial" if is_missing else "good",
                    null_reasons=["scheduled_sensor_maintenance"] if is_missing else [],
                    ingested_at=now,
                )
            )
    db.add_all(readings)
    db.flush()
    scored_target = now - timedelta(minutes=30)
    actual_by_site = {
        reading.site_id: reading.consumption_kwh
        for reading in readings
        if reading.measured_at == scored_target
    }
    db.add_all(
        [
            Prediction(
                site_id=site.site_id,
                predicted_at=scored_target - timedelta(minutes=120),
                target_at=scored_target,
                horizon_minutes=120,
                model_name=settings.local_model_name,
                model_version=settings.local_model_version,
                predicted_kwh=round((actual_by_site[site.site_id] or 0) * 0.97, 3),
                actual_kwh=actual_by_site[site.site_id],
                scored_at=scored_target,
            )
            for site in sites
        ]
    )
    refresh_stored_predictions(db, now)

    db.add(
        Alert(
            site_id=sites[1].site_id,
            severity="high",
            type="threshold",
            message="Consommation élevée détectée sur le site Grenoble Sud.",
            detected_at=now - timedelta(minutes=30),
            value=1130,
            threshold_value=1080,
            status="open",
        )
    )
    db.add_all(
        [
            SensorStatus(
                site_id=site.site_id,
                sensor=sensor,
                observed_at=now,
                status="ok",
                failing_until=None,
            )
            for site in sites
            for sensor in ("consumption", "electrical", "temperature", "humidity", "network")
        ]
    )
    today = now.date()
    db.add_all(
        [
            DataQualityDaily(
                site_id=site.site_id,
                day=today,
                expected_points=1440,
                received_points=1440,
                missing_points=0,
                null_points=1,
                imputed_points=1,
                computed_at=now,
            )
            for site in sites
        ]
    )
    db.add(
        EtlRun(
            started_at=now - timedelta(minutes=1),
            finished_at=now,
            window_start=now - timedelta(minutes=30),
            window_end=now,
            rows_read=len(readings),
            rows_written=len(readings),
            rows_imputed=3,
            status="ok",
            error_message=None,
        )
    )
    db.commit()


def _ensure_demo_users(db: Session) -> None:
    existing_emails = set(db.scalars(select(User.email)))
    password = get_password_hash(settings.seed_user_password)
    now = datetime.now(UTC)
    demo_users = (
        ("camille.martin@enervision.demo", "admin"),
        ("lucas.bernard@enervision.demo", "operator"),
        ("marc.legrand@enervision.demo", "viewer"),
    )
    db.add_all(
        [
            User(
                email=email,
                password_hash=password,
                role=role,
                is_active=True,
                created_at=now,
            )
            for email, role in demo_users
            if email not in existing_emails
        ]
    )
    db.commit()
