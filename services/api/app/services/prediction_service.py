from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reading import Reading


def predict_next_consumption(db: Session, site_id: int) -> dict[str, float | int]:
    readings = list(
        db.scalars(
            select(Reading)
            .where(Reading.site_id == site_id)
            .order_by(Reading.recorded_at.desc())
            .limit(24)
        )
    )
    values = [
        reading.consumption_kwh_raw
        if reading.consumption_kwh_raw is not None
        else reading.consumption_kwh_imputed
        for reading in readings
    ]
    known_values = [value for value in values if value is not None]
    if not known_values:
        raise ValueError("No usable reading is available for this site")
    average = sum(known_values) / len(known_values)
    return {
        "site_id": site_id,
        "predicted_consumption_kwh": round(average * 1.05, 2),
        "based_on_readings": len(known_values),
    }