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
from app.models.user import Role, User


def initialize_database(db: Session) -> None:
    """Create the schema and populate the local demonstration dataset once."""
    Base.metadata.create_all(bind=engine)
    if db.scalar(select(User.id).limit(1)) is not None:
        return

    roles = {name: Role(name=name) for name in ("admin", "operator", "data_analyst", "user")}
    db.add_all(roles.values())
    password = get_password_hash(settings.seed_user_password)
    db.add_all(
        [
            User(
                username="camille.admin",
                email="camille.martin@enervision.demo",
                full_name="Camille Martin",
                hashed_password=password,
                roles=[roles["admin"], roles["operator"]],
            ),
            User(
                username="lucas.operator",
                email="lucas.bernard@enervision.demo",
                full_name="Lucas Bernard",
                hashed_password=password,
                roles=[roles["operator"]],
            ),
            User(
                username="ines.analyst",
                email="ines.dubois@enervision.demo",
                full_name="Ines Dubois",
                hashed_password=password,
                roles=[roles["data_analyst"], roles["user"]],
            ),
            User(
                username="marc.viewer",
                email="marc.legrand@enervision.demo",
                full_name="Marc Legrand",
                hashed_password=password,
                roles=[roles["user"]],
            ),
        ]
    )
    sites = [
        Site(code="LYO-01", name="Atelier Lyon Gerland", city="Lyon", surface_m2=4200, subscribed_power_kw=850),
        Site(code="GRE-01", name="Usine Grenoble Sud", city="Grenoble", surface_m2=6800, subscribed_power_kw=1200),
        Site(code="NAN-01", name="Entrepot Nantes Est", city="Nantes", surface_m2=3100, subscribed_power_kw=500),
    ]
    db.add_all(sites)
    db.flush()

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    base_consumption = (278.0, 436.0, 164.0)
    readings: list[Reading] = []
    for hour_offset in range(47, -1, -1):
        recorded_at = now - timedelta(hours=hour_offset)
        workday_factor = 1.23 if 7 <= recorded_at.hour <= 18 else 0.72
        for index, site in enumerate(sites):
            value = round(base_consumption[index] * workday_factor * (1 + ((hour_offset + index) % 5) * 0.018), 2)
            has_missing_value = (hour_offset, index) in {(31, 0), (17, 1), (8, 2)}
            readings.append(
                Reading(
                    site_id=site.id,
                    recorded_at=recorded_at,
                    consumption_kwh_raw=None if has_missing_value else value,
                    consumption_kwh_imputed=value if has_missing_value else None,
                    data_quality="partial" if has_missing_value else "good",
                    null_reasons=["scheduled_sensor_maintenance"] if has_missing_value else None,
                    source="seed",
                )
            )
    db.add_all(readings)
    db.add(
        Alert(
            site_id=sites[1].id,
            severity="warning",
            message="Consommation elevee detectee sur le site Grenoble Sud.",
            triggered_at=now - timedelta(hours=2),
            is_active=True,
        )
    )
    db.commit()