from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.reading import Reading
from app.services.prediction_service import (
    PREDICTION_HORIZON_MINUTES,
    PREDICTION_SOURCE,
    get_stored_next_prediction,
    refresh_stored_predictions,
)


def test_refresh_replaces_predictions_with_future_minute_data(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    client.get("/api/v1/sites", headers=auth_headers)
    refresh_time = datetime.now(UTC).replace(second=0, microsecond=0)

    with SessionLocal() as db:
        created_predictions = refresh_stored_predictions(db, refresh_time)
        predictions = list(
            db.scalars(
                select(Reading)
                .where(Reading.site_id == 1, Reading.source == PREDICTION_SOURCE)
                .order_by(Reading.recorded_at)
            )
        )

    assert created_predictions == PREDICTION_HORIZON_MINUTES * 3
    assert len(predictions) == PREDICTION_HORIZON_MINUTES
    expected_start = refresh_time.replace(tzinfo=None)
    assert predictions[0].recorded_at == expected_start + timedelta(minutes=1)
    assert predictions[-1].recorded_at == expected_start + timedelta(minutes=PREDICTION_HORIZON_MINUTES)


def test_next_prediction_rejects_expired_points(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.get("/api/v1/sites", headers=auth_headers)

    with SessionLocal() as db:
        db.execute(delete(Reading).where(Reading.source == PREDICTION_SOURCE))
        db.add(
            Reading(
                site_id=1,
                recorded_at=datetime.now(UTC) - timedelta(minutes=1),
                consumption_kwh_raw=300.0,
                consumption_kwh_imputed=None,
                data_quality="predicted",
                null_reasons=None,
                source=PREDICTION_SOURCE,
            )
        )
        db.commit()
        with pytest.raises(ValueError, match="No future prediction"):
            get_stored_next_prediction(db, 1)
        refresh_stored_predictions(db)
