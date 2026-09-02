from datetime import UTC, datetime, timedelta

from app.db.session import SessionLocal
from app.models.prediction import Prediction
from app.models.reading import Reading
from app.services.prediction_service import PREDICTION_HORIZON_MINUTES, refresh_stored_predictions
from fastapi.testclient import TestClient
from sqlalchemy import func, select


def test_refresh_writes_one_idempotent_horizon_prediction_per_site(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.get("/api/v1/sites", headers=auth_headers)
    with SessionLocal() as db:
        before = db.scalar(select(func.count(Prediction.id))) or 0
        created = refresh_stored_predictions(db, datetime.now(UTC))
        after = db.scalar(select(func.count(Prediction.id))) or 0
        prediction = db.scalar(select(Prediction).where(Prediction.site_id == "LYO-01"))

    assert created == 0
    assert before == after
    assert prediction is not None
    assert prediction.horizon_minutes == PREDICTION_HORIZON_MINUTES


def test_refresh_scores_prediction_when_its_actual_measurement_arrives(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.get("/api/v1/sites", headers=auth_headers)
    with SessionLocal() as db:
        prediction = db.scalar(
            select(Prediction)
            .where(Prediction.site_id == "LYO-01", Prediction.actual_kwh.is_(None))
            .order_by(Prediction.target_at)
        )
        assert prediction is not None
        db.add(
            Reading(
                site_id=prediction.site_id,
                measured_at=prediction.target_at,
                consumption_kwh=321.0,
                consumption_kwh_raw=321.0,
                is_imputed=False,
                imputation_method=None,
                temperature_celsius=None,
                humidity_percent=None,
                data_quality="good",
                null_reasons=[],
                ingested_at=prediction.target_at,
            )
        )
        db.commit()
        refresh_stored_predictions(db, prediction.target_at + timedelta(minutes=1))
        db.refresh(prediction)

        assert prediction.actual_kwh == 321.0
        assert prediction.scored_at is not None
