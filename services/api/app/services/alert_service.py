from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.reading import Reading
from app.models.site import Site


def get_alerts(db: Session, site_id: int, active_only: bool = True) -> list[Alert]:
    statement = select(Alert).where(Alert.site_id == site_id).order_by(Alert.triggered_at.desc())
    if active_only:
        statement = statement.where(Alert.is_active.is_(True))
    return list(db.scalars(statement))


def evaluate_reading_alert(db: Session, reading: Reading) -> Alert | None:
    site = db.get(Site, reading.site_id)
    consumption = (
        reading.consumption_kwh_raw
        if reading.consumption_kwh_raw is not None
        else reading.consumption_kwh_imputed
    )
    if site is None or consumption is None or consumption <= site.subscribed_power_kw * 0.9:
        return None

    alert = Alert(
        site_id=site.id,
        severity="critical" if consumption > site.subscribed_power_kw else "warning",
        message=f"Seuil de puissance approche sur {site.name}.",
        triggered_at=datetime.now(UTC),
        is_active=True,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert