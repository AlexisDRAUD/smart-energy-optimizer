from datetime import UTC, datetime, timedelta
from logging import getLogger

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.reading import Reading
from app.models.site import Site

logger = getLogger(__name__)
PREDICTION_HORIZON_MINUTES = 120
PREDICTION_SOURCE = "prediction"


def refresh_stored_predictions(db: Session, now: datetime | None = None) -> int:
    """Replace all forecasts with a two-hour, minute-level forecast for every site."""
    forecast_start = (now or datetime.now(UTC)).replace(second=0, microsecond=0)
    sites = list(db.scalars(select(Site).order_by(Site.id)))
    db.execute(delete(Reading).where(Reading.source == PREDICTION_SOURCE))

    created_predictions = 0
    for site in sites:
        readings = list(
            db.scalars(
                select(Reading)
                .where(Reading.site_id == site.id, Reading.source != PREDICTION_SOURCE)
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
            logger.warning("No usable readings available to generate predictions for site %s", site.id)
            continue

        baseline = sum(known_values) / len(known_values) * 1.05
        for minute_offset in range(1, PREDICTION_HORIZON_MINUTES + 1):
            variation = 1 + (minute_offset - PREDICTION_HORIZON_MINUTES / 2) * 0.0005
            db.add(
                Reading(
                    site_id=site.id,
                    recorded_at=forecast_start + timedelta(minutes=minute_offset),
                    consumption_kwh_raw=round(baseline * variation, 2),
                    consumption_kwh_imputed=None,
                    data_quality="predicted",
                    null_reasons=None,
                    source=PREDICTION_SOURCE,
                )
            )
            created_predictions += 1

    db.commit()
    return created_predictions


def get_stored_next_prediction(db: Session, site_id: int) -> Reading:
    prediction = db.scalar(
        select(Reading)
        .where(
            Reading.site_id == site_id,
            Reading.source == PREDICTION_SOURCE,
            Reading.recorded_at > datetime.now(UTC),
        )
        .order_by(Reading.recorded_at)
        .limit(1)
    )
    if prediction is None:
        raise ValueError("No future prediction is available for this site")
    return prediction
