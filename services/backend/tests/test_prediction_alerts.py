from datetime import UTC, datetime, timedelta

from app.config import settings
from app.db.models.alert import Alert
from app.db.models.prediction import Prediction
from app.db.models.reading import Reading
from app.db.session import SessionLocal
from app.services.prediction_alerts import (
    ALERT_TYPE,
    rise_percent_per_hour,
    severity_for,
)
from app.services.prediction_service import refresh_stored_predictions
from fastapi.testclient import TestClient
from sqlalchemy import select


def test_slope_is_normalised_per_hour_whatever_the_horizon() -> None:
    # +20 % sur deux heures, c est 10 % par heure.
    assert rise_percent_per_hour(100.0, 120.0, 120) == 10.0
    # La meme hausse sur trente minutes monte quatre fois plus vite.
    assert rise_percent_per_hour(100.0, 120.0, 30) == 40.0


def test_slope_is_ignored_when_the_baseline_is_too_small_to_compare() -> None:
    baseline = settings.prediction_alert_min_baseline_kwh / 2
    assert rise_percent_per_hour(baseline, baseline * 10, 60) is None


def test_severity_grows_with_the_slope() -> None:
    threshold = settings.prediction_alert_rise_percent_per_hour
    assert severity_for(threshold * 0.9) is None
    assert severity_for(threshold) == "medium"
    assert severity_for(threshold * 2) == "high"
    assert severity_for(threshold * 3) == "critical"


def test_refresh_opens_a_forecast_alert_when_the_prediction_climbs_too_fast(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.get("/api/v1/sites", headers=auth_headers)
    horizon = settings.prediction_horizon_minutes
    with SessionLocal() as db:
        site_id = "LYO-01"
        latest = db.scalar(
            select(Reading)
            .where(Reading.site_id == site_id)
            .order_by(Reading.measured_at.desc())
            .limit(1)
        )
        assert latest is not None
        # Un dernier releve tres au-dessus des precedents : la moyenne mobile
        # reste basse, donc on force l inverse - une reference basse et des
        # mesures hautes - en ajoutant une mesure faible apres coup.
        measured_at = latest.measured_at + timedelta(minutes=1)
        db.add(
            Reading(
                site_id=site_id,
                measured_at=measured_at,
                consumption_kwh=1.0,
                consumption_kwh_raw=1.0,
                is_imputed=False,
                imputation_method=None,
                temperature_celsius=None,
                humidity_percent=None,
                data_quality="good",
                null_reasons=[],
                ingested_at=measured_at,
            )
        )
        db.commit()

        now = datetime.now(UTC).replace(second=0, microsecond=0)
        created = refresh_stored_predictions(db, now)
        assert created >= 1

        prediction = db.scalar(
            select(Prediction).where(
                Prediction.site_id == site_id,
                Prediction.target_at == measured_at + timedelta(minutes=horizon),
            )
        )
        assert prediction is not None
        assert prediction.predicted_kwh > 1.0

        alert = db.scalar(
            select(Alert).where(
                Alert.site_id == site_id,
                Alert.type == ALERT_TYPE,
                Alert.detected_at == now,
            )
        )
        assert alert is not None
        assert alert.status == "open"
        assert alert.origin == "internal"
        assert alert.value == prediction.predicted_kwh
        assert alert.severity in {"medium", "high", "critical"}

        # Le meme passage rejoue au meme instant ne duplique pas l alerte.
        refresh_stored_predictions(db, now)
        duplicates = list(
            db.scalars(
                select(Alert.id).where(
                    Alert.site_id == site_id,
                    Alert.type == ALERT_TYPE,
                    Alert.detected_at == now,
                )
            )
        )
        assert len(duplicates) == 1


def test_forecast_alerts_are_exposed_by_the_alerts_endpoint(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/alerts", params={"type": "forecast"}, headers=auth_headers)
    assert response.status_code == 200
    assert all(item["type"] == "forecast" for item in response.json()["items"])
