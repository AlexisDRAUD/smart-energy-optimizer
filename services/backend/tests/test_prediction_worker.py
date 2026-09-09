import model.predict as worker
from app.config import settings
from app.db.models.prediction import Prediction
from app.db.session import SessionLocal
from sqlalchemy import func, select


def test_run_once_writes_predictions_then_is_idempotent(database: None) -> None:
    first = worker.run_once()
    with SessionLocal() as db:
        after_first = db.scalar(select(func.count(Prediction.id))) or 0

    second = worker.run_once()
    with SessionLocal() as db:
        after_second = db.scalar(select(func.count(Prediction.id))) or 0

    assert first >= 0
    assert second == 0
    assert after_second == after_first

    with SessionLocal() as db:
        sample = db.scalar(select(Prediction))
    assert sample is not None
    assert sample.horizon_minutes == settings.prediction_horizon_minutes


def test_loop_returns_immediately_when_stop_is_already_set(database: None) -> None:
    worker._stop.set()
    try:
        assert worker.loop(interval_seconds=3600) == 0
    finally:
        worker._stop.clear()


def test_build_parser_defaults_to_the_configured_interval() -> None:
    args = worker.build_parser().parse_args([])

    assert args.interval_seconds == settings.prediction_worker_interval_seconds
    assert args.once is False
