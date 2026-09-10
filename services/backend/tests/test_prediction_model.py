"""Le worker ne sert que les modeles versionnes de MLflow, sans repli local.

Ces tests ne parlent pas a un vrai serveur MLflow : ils instancient le forecaster
avec un modele factice ou forcent l'absence de modele, et verifient ce que
``model.refresh.refresh_predictions`` ecrit alors dans ``predictions``.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.config import settings
from app.db.models.alert import Alert
from app.db.models.prediction import Prediction
from app.db.models.reading import Reading
from app.db.models.site import Site
from app.db.session import SessionLocal
from model.forecast import SiteForecast, SiteForecaster, _LoadedModel, build_forecaster
from model.refresh import refresh_predictions
from sqlalchemy import delete, func, select


def _latest_reading(db: SessionLocal, site_id: str) -> Reading:
    return db.scalar(
        select(Reading)
        .where(Reading.site_id == site_id)
        .order_by(Reading.measured_at.desc())
        .limit(1)
    )


class _StubForecaster:
    """Forecaster minimal : rend ce qu'on lui donne, sans MLflow."""

    def __init__(self, result: SiteForecast | None) -> None:
        self._result = result
        self.calls: list[str] = []

    def forecast(self, db, site, latest) -> SiteForecast | None:
        self.calls.append(site.site_id)
        return self._result


def test_build_forecaster_is_none_without_tracking_uri(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mlflow_tracking_uri", None)
    assert build_forecaster() is None

    monkeypatch.setattr(settings, "mlflow_tracking_uri", "http://mlflow:5000")
    assert isinstance(build_forecaster(), SiteForecaster)


def test_refresh_stores_forecast_with_its_model_identity(database: None) -> None:
    marker = "test-mlflow"

    class Forecaster:
        def forecast(self, db, site, latest) -> SiteForecast:
            return SiteForecast(
                predicted_kwh=100.0 + len(site.site_id),
                model_name=f"EnerVision_RF_Predictor_{site.site_id}",
                model_version=marker,
            )

    try:
        with SessionLocal() as db:
            created = refresh_predictions(db, Forecaster(), datetime.now(UTC))
            assert created >= 1
            rows = list(db.scalars(select(Prediction).where(Prediction.model_version == marker)))

        assert rows
        for row in rows:
            assert row.model_name == f"EnerVision_RF_Predictor_{row.site_id}"
            assert row.predicted_kwh == 100.0 + len(row.site_id)
            assert row.horizon_minutes == settings.prediction_horizon_minutes
    finally:
        with SessionLocal() as db:
            db.execute(delete(Prediction).where(Prediction.model_version == marker))
            db.commit()


def test_refresh_opens_alert_for_fast_mlflow_forecast(database: None) -> None:
    site_id = "LYO-01"
    marker = "test-mlflow-alert"
    predicted_at = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)

    class Forecaster:
        def forecast(self, db, site, latest) -> SiteForecast | None:
            if site.site_id != site_id:
                return None
            assert latest.consumption_kwh is not None
            return SiteForecast(
                predicted_kwh=latest.consumption_kwh * 4,
                model_name=f"EnerVision_RF_Predictor_{site_id}",
                model_version=marker,
            )

    try:
        with SessionLocal() as db:
            assert refresh_predictions(db, Forecaster(), predicted_at) == 1
            alert = db.scalar(
                select(Alert).where(
                    Alert.site_id == site_id,
                    Alert.type == "forecast",
                    Alert.detected_at == predicted_at,
                )
            )
            prediction = db.scalar(select(Prediction).where(Prediction.model_version == marker))

        assert alert is not None
        assert prediction is not None
        assert alert.value == prediction.predicted_kwh
        assert alert.origin == "internal"
        assert alert.status == "open"
        assert alert.severity == "critical"
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(Alert).where(
                    Alert.site_id == site_id,
                    Alert.type == "forecast",
                    Alert.detected_at == predicted_at,
                )
            )
            db.execute(delete(Prediction).where(Prediction.model_version == marker))
            db.commit()


def test_refresh_without_model_writes_nothing(database: None) -> None:
    stub = _StubForecaster(None)
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(Prediction))
        created = refresh_predictions(db, stub, datetime.now(UTC))
        after = db.scalar(select(func.count()).select_from(Prediction))

    assert created == 0
    assert before == after
    assert stub.calls  # le forecaster est bien interroge pour chaque site actif


def test_refresh_without_forecaster_writes_nothing(database: None) -> None:
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(Prediction))
        created = refresh_predictions(db, None, datetime.now(UTC))
        after = db.scalar(select(func.count()).select_from(Prediction))

    assert created == 0
    assert before == after


def test_refresh_scores_due_predictions_without_touching_models(database: None) -> None:
    with SessionLocal() as db:
        due = db.scalar(
            select(Prediction)
            .where(Prediction.site_id == "LYO-01", Prediction.actual_kwh.is_(None))
            .order_by(Prediction.target_at)
        )
        assert due is not None
        due_id, site_id, target_at = due.id, due.site_id, due.target_at

    try:
        with SessionLocal() as db:
            db.add(
                Reading(
                    site_id=site_id,
                    measured_at=target_at,
                    consumption_kwh=210.0,
                    consumption_kwh_raw=210.0,
                    is_imputed=False,
                    imputation_method=None,
                    temperature_celsius=None,
                    humidity_percent=None,
                    data_quality="good",
                    null_reasons=[],
                    ingested_at=target_at,
                )
            )
            db.commit()

            refresh_predictions(db, None, target_at + timedelta(minutes=1))
            db.expire_all()
            scored = db.get(Prediction, due_id)
            assert scored.actual_kwh == 210.0
            assert scored.scored_at is not None
            # absolute_error est une colonne generee par PostgreSQL des que
            # actual_kwh est renseigne : |predicted_kwh - actual_kwh|.
            assert scored.absolute_error == pytest.approx(abs(scored.predicted_kwh - 210.0))
    finally:
        # Retirer le releve futur injecte : il decalerait le "dernier releve" de
        # LYO-01 et ferait echouer les tests de refresh_stored_predictions.
        with SessionLocal() as db:
            db.execute(
                delete(Reading).where(Reading.site_id == site_id, Reading.measured_at == target_at)
            )
            row = db.get(Prediction, due_id)
            row.actual_kwh = None
            row.scored_at = None
            db.commit()


def test_refresh_anchors_target_at_on_last_non_null_reading(database: None) -> None:
    site_id = "P2-ANCHOR"
    marker = "p2-anchor"
    base = datetime(2025, 6, 1, tzinfo=UTC)
    seen: dict[str, object] = {}

    class Forecaster:
        def forecast(self, db, site, latest) -> SiteForecast | None:
            if site.site_id != site_id:
                return None
            seen["anchor"] = latest.measured_at
            return SiteForecast(123.0, f"EnerVision_RF_Predictor_{site_id}", marker)

    try:
        with SessionLocal() as db:
            db.add(
                Site(
                    site_id=site_id,
                    site_type="office",
                    site_name="p2",
                    location="x",
                    capacity_kw=10,
                    status="active",
                    first_seen_at=base,
                    last_seen_at=base,
                )
            )
            db.add_all(
                [
                    Reading(
                        site_id=site_id,
                        measured_at=base + timedelta(minutes=m),
                        # les 4 derniers releves sont nuls (panne capteur en cours)
                        consumption_kwh=None if m >= 6 else 100.0 + m,
                        consumption_kwh_raw=None,
                        is_imputed=False,
                        imputation_method=None,
                        temperature_celsius=None,
                        humidity_percent=None,
                        data_quality="good",
                        null_reasons=[],
                        ingested_at=base,
                    )
                    for m in range(10)
                ]
            )
            db.commit()

            refresh_predictions(db, Forecaster(), base + timedelta(hours=3))
            row = db.scalar(select(Prediction).where(Prediction.model_version == marker))

        # dernier releve reel = minute 5 ; target_at part de la, pas de la minute 9
        assert seen["anchor"] == base + timedelta(minutes=5)
        assert row is not None
        assert row.target_at == base + timedelta(minutes=5, hours=2)
    finally:
        with SessionLocal() as db:
            db.execute(delete(Prediction).where(Prediction.model_version == marker))
            db.execute(delete(Reading).where(Reading.site_id == site_id))
            db.execute(delete(Site).where(Site.site_id == site_id))
            db.commit()


def test_site_forecaster_predicts_from_seeded_history(database: None, monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeModel:
        def predict(self, frame):
            seen["columns"] = set(frame.columns)
            seen["rows"] = len(frame)
            return [123.456]

    forecaster = SiteForecaster("http://mlflow:5000")
    monkeypatch.setattr(
        forecaster, "_load", lambda site_id: _LoadedModel(version="3", model=FakeModel())
    )

    with SessionLocal() as db:
        site = db.get(Site, "LYO-01")
        result = forecaster.forecast(db, site, _latest_reading(db, "LYO-01"))

    assert result is not None
    assert result.predicted_kwh == 123.456
    assert result.model_name == "EnerVision_RF_Predictor_LYO-01"
    assert result.model_version == "3"
    # Contrat de service : une seule ligne, les variables de seo_features presentes.
    assert seen["rows"] == 1
    assert {"site_id", "site_type", "hour", "lag_1", "rolling_mean_120"} <= seen["columns"]


def test_site_forecaster_returns_none_when_model_is_unavailable(
    database: None, monkeypatch
) -> None:
    forecaster = SiteForecaster("http://mlflow:5000")
    monkeypatch.setattr(forecaster, "_load", lambda site_id: None)

    with SessionLocal() as db:
        site = db.get(Site, "LYO-01")
        assert forecaster.forecast(db, site, _latest_reading(db, "LYO-01")) is None
