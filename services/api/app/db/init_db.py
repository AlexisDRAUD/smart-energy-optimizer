from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import engine
from app.models.alert import Alert
from app.models.reading import Reading
from app.models.site import Site
from app.models.user import User
from app.services.prediction_service import refresh_stored_predictions


def _consumption_value(base_consumption: float, recorded_at: datetime, offset: int) -> float:
    workday_factor = 1.23 if 7 <= recorded_at.hour <= 18 else 0.72
    minute_variation = 1 + (((offset * 7) % 17) - 8) * 0.002
    return round(base_consumption * workday_factor * minute_variation, 2)


def initialize_database(db: Session) -> None:
    """Create the schema and populate the local demonstration dataset once."""
    Base.metadata.create_all(bind=engine)
    if db.scalar(select(User.id).limit(1)) is not None:
        return

    sites = [
        Site(code="LYO-01", name="Atelier Lyon Gerland", city="Lyon", surface_m2=4200, subscribed_power_kw=850),
        Site(code="GRE-01", name="Usine Grenoble Sud", city="Grenoble", surface_m2=6800, subscribed_power_kw=1200),
        Site(code="NAN-01", name="Entrepot Nantes Est", city="Nantes", surface_m2=3100, subscribed_power_kw=500),
    ]
    db.add_all(sites)
    db.flush()

    password = get_password_hash(settings.seed_user_password)
    db.add_all(
        [
            User(username="camille.admin", email="camille.martin@enervision.demo", full_name="Camille Martin", hashed_password=password, site=sites[0]),
            User(username="lucas.operator", email="lucas.bernard@enervision.demo", full_name="Lucas Bernard", hashed_password=password, site=sites[1]),
            User(username="ines.analyst", email="ines.dubois@enervision.demo", full_name="Ines Dubois", hashed_password=password, site=sites[2]),
            User(username="marc.viewer", email="marc.legrand@enervision.demo", full_name="Marc Legrand", hashed_password=password, site=sites[0]),
        ]
    )

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
                    site_id=site.id,
                    recorded_at=recorded_at,
                    consumption_kwh_raw=None if is_missing else value,
                    consumption_kwh_imputed=value if is_missing else None,
                    data_quality="partial" if is_missing else "good",
                    null_reasons=["scheduled_sensor_maintenance"] if is_missing else None,
                    source="seed",
                )
            )
    db.add_all(readings)
    db.flush()
    refresh_stored_predictions(db, now)

    db.add(
        Alert(
            site_id=sites[1].id,
            severity="warning",
            message="Consommation elevee detectee sur le site Grenoble Sud.",
            triggered_at=now - timedelta(minutes=30),
            is_active=True,
        )
    )
    db.commit()
