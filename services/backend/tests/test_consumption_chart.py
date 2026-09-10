from datetime import UTC, datetime, timedelta

import pytest
from app.api.deps import get_current_user
from app.api.v1.endpoints import consumption_chart, predictions, readings
from app.config import settings
from app.core.contract import utc_iso
from app.db.models.prediction import Prediction
from app.db.models.reading import Reading
from app.db.models.site import Site
from app.db.models.user import User
from app.db.session import SessionLocal, get_db
from app.services import consumption_chart_service as service
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select
from sqlalchemy.exc import DBAPIError

START = datetime(2025, 1, 1, tzinfo=UTC)
SITE = "chart-test"


@pytest.fixture
def chart_client(database):
    """Real PostgreSQL and route, rolled back; no prediction scheduler is started."""
    with SessionLocal() as db:
        db.add(
            Site(
                site_id=SITE,
                site_type="office",
                site_name="Chart test",
                location="Paris",
                capacity_kw=1000,
                status="active",
                first_seen_at=START,
                last_seen_at=START,
            )
        )
        db.flush()
        app = FastAPI()
        app.include_router(consumption_chart.router, prefix="/api/v1")
        app.include_router(readings.router, prefix="/api/v1")
        app.include_router(predictions.model_router, prefix="/api/v1")
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: User(role="viewer", is_active=True)
        with TestClient(app) as client:
            yield client, db, app
        db.rollback()


def reading(minute, value=342.62, site=SITE):
    return {
        "site_id": site,
        "measured_at": START + timedelta(minutes=minute),
        "consumption_kwh": value,
        "consumption_kwh_raw": value,
        "is_imputed": False,
        "data_quality": "good",
        "null_reasons": [],
        "ingested_at": START,
    }


def prediction(minute, value=300.0, *, version=None, horizon=120, site=SITE, name=None):
    return {
        "site_id": site,
        "target_at": START + timedelta(minutes=minute),
        "predicted_at": START + timedelta(minutes=minute - horizon),
        "horizon_minutes": horizon,
        "model_name": name or settings.local_model_name,
        "model_version": version or settings.local_model_version,
        "predicted_kwh": value,
        "actual_kwh": None,
        "scored_at": None,
    }


def fetch(client, minutes=60, **overrides):
    params = {
        "site_id": SITE,
        "start": utc_iso(START),
        "end": utc_iso(START + timedelta(minutes=minutes)),
        **overrides,
    }
    return client.get("/api/v1/consumption-chart", params=params)


@pytest.mark.parametrize("days", [1, 7, 30])
def test_complete_window_exceeds_legacy_limits_without_truncation(chart_client, days):
    client, db, _ = chart_client
    count = days * 1440
    db.execute(insert(Reading), [reading(i, 300 + i % 17) for i in range(count + 1)])
    db.execute(insert(Prediction), [prediction(i) for i in range(count + 121)])
    before = db.scalar(select(func.count()).select_from(Prediction))
    response = fetch(client, count)
    assert response.status_code == 200
    body = response.json()
    expected_displayed = min(count, service.DISPLAY_POINTS_PER_SERIES)
    assert len(body["readings"]) == expected_displayed
    assert len(body["historical_predictions"]) == expected_displayed
    assert len(body["future_predictions"]) == 120
    assert body["readings"][0]["measured_at"] == utc_iso(START)
    assert body["readings"][-1]["measured_at"] == utc_iso(START + timedelta(minutes=count - 1))
    assert body["readings"][-1]["consumption_kwh"] == 300 + (count - 1) % 17
    assert body["future_predictions"][0]["target_at"] == body["end"]
    assert body["future_predictions"][-1]["target_at"] < body["future_end"]
    assert body["reading_coverage"]["expected_minutes"] == count
    assert body["reading_coverage"]["percent"] == 100
    assert body["downsampling"] == {
        "algorithm": "lttb",
        "target_points_per_series": service.DISPLAY_POINTS_PER_SERIES,
        "readings": {
            "input_points": count,
            "output_points": expected_displayed,
            "applied": count > expected_displayed,
        },
        "historical_predictions": {
            "input_points": count,
            "output_points": expected_displayed,
            "applied": count > expected_displayed,
        },
        "future_predictions": {
            "input_points": 120,
            "output_points": 120,
            "applied": False,
        },
    }
    assert db.scalar(select(func.count()).select_from(Prediction)) == before
    assert (
        db.scalar(
            select(func.count())
            .select_from(Prediction)
            .where(Prediction.site_id == SITE, Prediction.actual_kwh.is_not(None))
        )
        == 0
    )
    # Read-only display does not change stored scores or values.
    assert not db.dirty and not db.new and not db.deleted


def test_nulls_absences_native_values_and_exact_pair(chart_client):
    client, db, _ = chart_client
    db.execute(insert(Reading), [reading(0), reading(1, None), reading(3, 330), reading(4, None)])
    db.execute(
        insert(Prediction),
        [prediction(0), prediction(1), prediction(2), prediction(3), prediction(4), prediction(60)],
    )
    body = fetch(client).json()
    assert [p["consumption_kwh"] for p in body["readings"]] == [342.62, None, 330, None]
    assert body["reading_coverage"] == {
        "expected_minutes": 60,
        "received_minutes": 4,
        "missing_minutes": 56,
        "null_minutes": 2,
        "valid_minutes": 2,
        "percent": 3.33,
        "first_at": utc_iso(START),
        "last_at": utc_iso(START + timedelta(minutes=4)),
    }
    assert body["last_evaluated"]["target_at"] == utc_iso(START + timedelta(minutes=3))
    assert body["last_evaluated"]["actual_kwh"] == 330
    assert body["last_evaluated"]["deviation_percent"] == 10
    assert body["measurement_interval_seconds"] is None
    assert body["unit_basis"] == "source_declared"
    assert body["downsampling"]["readings"]["input_points"] == 4
    assert body["downsampling"]["readings"]["applied"] is False
    # Existing hourly sums remain sums, including their null handling.
    legacy = client.get(
        "/api/v1/readings",
        params={
            "site_id": SITE,
            "start": utc_iso(START),
            "end": utc_iso(START + timedelta(hours=1)),
            "granularity": "hour",
            "limit": 1,
        },
    ).json()
    assert legacy["points"][0]["consumption_kwh"] == 672.62


def test_only_production_h2_is_displayed_and_compared(chart_client):
    client, db, _ = chart_client
    db.execute(insert(Reading), [reading(i, 330) for i in range(6)])
    db.execute(
        insert(Prediction),
        [
            prediction(0),
            prediction(1, horizon=60),
            prediction(2, version="experimental"),
            prediction(3, site="another-site"),
            prediction(4, version="other-model", name="other"),
            prediction(5, 0),
        ],
    )
    body = fetch(client).json()
    assert len(body["historical_predictions"]) == 2
    assert body["model_version"] == settings.local_model_version
    assert body["horizon_minutes"] == 120
    assert body["last_evaluated"]["target_at"] == utc_iso(START + timedelta(minutes=5))
    assert body["last_evaluated"]["deviation_percent"] is None
    assert body["last_evaluated"]["actual_kwh"] == 330


def test_chart_follows_the_active_model_identity_per_site(chart_client):
    client, db, _ = chart_client
    db.execute(insert(Reading), [reading(i, 330) for i in range(6)])
    db.execute(
        insert(Prediction),
        [
            # ancien modele local : previsions plus anciennes
            prediction(0, name="local-moving-average", version="local-1"),
            prediction(1, name="local-moving-average", version="local-1"),
            # modele MLflow par site : la prevision la plus recente
            prediction(2, name="EnerVision_RF_Predictor_chart-test", version="7"),
            prediction(3, name="EnerVision_RF_Predictor_chart-test", version="7"),
        ],
    )
    body = fetch(client).json()

    # l'identite renvoyee est celle de la derniere prevision ecrite, pas une constante
    assert body["model_name"] == "EnerVision_RF_Predictor_chart-test"
    assert body["model_version"] == "7"
    # seules les lignes du modele actif alimentent la serie
    assert len(body["historical_predictions"]) == 2
    assert {p["model_version"] for p in body["historical_predictions"]} == {"7"}
    assert body["last_evaluated"]["model_version"] == "7"


def test_chart_falls_back_to_local_identity_without_predictions(chart_client):
    client, db, _ = chart_client
    db.execute(insert(Reading), [reading(i, 330) for i in range(6)])
    body = fetch(client).json()

    assert body["model_name"] == settings.local_model_name
    assert body["model_version"] == settings.local_model_version
    assert body["historical_predictions"] == []


def test_empty_window_and_nonmatching_timestamps(chart_client):
    client, db, _ = chart_client
    assert fetch(client).json()["last_evaluated"] is None
    db.execute(insert(Reading), [reading(0.5)])
    db.execute(insert(Prediction), [prediction(0)])
    body = fetch(client).json()
    assert body["last_evaluated"] is None
    assert body["readings"][0]["measured_at"] == utc_iso(START + timedelta(seconds=30))


@pytest.mark.parametrize(
    "params",
    [
        {"end": utc_iso(START + timedelta(days=30, microseconds=1))},
        {"end": utc_iso(START)},
        {"end": utc_iso(START - timedelta(seconds=1))},
        {"start": "2025-01-01T00:00:00"},
        {"start": "invalid"},
        {"limit": "500"},
        {"offset": "1"},
        {"horizon_minutes": "60"},
        {"model_version": "experimental"},
        {
            "start": utc_iso(datetime.now(UTC)),
            "end": utc_iso(datetime.now(UTC) + timedelta(hours=1)),
        },
    ],
)
def test_unsupported_windows_and_pagination_fail_explicitly(chart_client, params):
    client, _, _ = chart_client
    assert fetch(client, **params).status_code == 422


@pytest.mark.parametrize("series", ["readings", "predictions"])
def test_volume_overflow_is_error_not_partial_success(chart_client, monkeypatch, series):
    client, db, _ = chart_client
    if series == "readings":
        monkeypatch.setattr(service, "MAX_READINGS", 2)
        db.execute(insert(Reading), [reading(i) for i in range(3)])
    else:
        monkeypatch.setattr(service, "MAX_PREDICTIONS", 2)
        db.execute(insert(Prediction), [prediction(i) for i in range(3)])
    response = fetch(client)
    assert response.status_code == 422
    assert "volume" in response.json()["detail"]


def test_site_and_authentication_are_required(chart_client):
    client, _, app = chart_client
    assert fetch(client, site_id="nonexistent").status_code == 404
    app.dependency_overrides.pop(get_current_user)
    assert fetch(client).status_code == 401


def test_partial_minute_coverage_does_not_round_native_timestamps(chart_client):
    client, db, _ = chart_client
    db.execute(insert(Reading), [reading(0), reading(1), reading(2)])
    body = fetch(
        client,
        start=utc_iso(START + timedelta(seconds=30)),
        end=utc_iso(START + timedelta(minutes=2, seconds=30)),
    ).json()
    assert body["reading_coverage"]["expected_minutes"] == 3
    assert body["reading_coverage"]["received_minutes"] == 2
    assert body["readings"][0]["measured_at"] == utc_iso(START + timedelta(minutes=1))


def test_query_timeout_is_explicit_not_an_empty_chart(chart_client, monkeypatch):
    from psycopg.errors import QueryCanceled

    client, _, _ = chart_client

    def timeout(*args):
        raise DBAPIError("select", {}, QueryCanceled("statement timeout"))

    monkeypatch.setattr(consumption_chart, "consumption_chart", timeout)
    response = fetch(client)
    assert response.status_code == 503
    assert "timed out" in response.json()["detail"]


def test_display_does_not_rewrite_stored_evaluation_or_model_metrics(chart_client):
    client, db, _ = chart_client
    db.execute(insert(Reading), [reading(0, 330)])
    stored = prediction(0)
    stored.update(actual_kwh=200, scored_at=START)
    db.execute(insert(Prediction), [stored])
    params = {"site_id": SITE, "start": utc_iso(START), "end": utc_iso(START + timedelta(hours=1))}
    before = client.get("/api/v1/model/performance", params=params).json()
    assert before["model"]["mae"] == 100
    assert fetch(client).json()["last_evaluated"]["deviation_percent"] == 10
    assert client.get("/api/v1/model/performance", params=params).json() == before
    record = db.scalar(select(Prediction).where(Prediction.site_id == SITE))
    assert record.actual_kwh == 200
    assert record.absolute_error == 100
    assert record.scored_at == START


def test_last_evaluated_pair_uses_full_series_before_downsampling(chart_client, monkeypatch):
    client, db, _ = chart_client
    db.execute(insert(Reading), [reading(i, 330) for i in range(701)])
    db.execute(insert(Prediction), [prediction(i) for i in range(701)])

    def endpoints_only(points, **kwargs):
        selected = points if len(points) < 2 else [points[0], points[-1]]
        return [{**point, "segment_start": index == 0} for index, point in enumerate(selected)]

    monkeypatch.setattr(service, "downsample_with_gaps", endpoints_only)
    body = fetch(client, minutes=701).json()

    assert len(body["readings"]) == 2
    assert body["reading_coverage"]["received_minutes"] == 701
    assert body["last_evaluated"]["target_at"] == utc_iso(START + timedelta(minutes=700))
    assert body["last_evaluated"]["actual_kwh"] == 330


def test_main_router_authentication_and_error_contract(client, viewer_headers):
    params = {
        "site_id": "LYO-01",
        "start": utc_iso(START),
        "end": utc_iso(START + timedelta(days=30)),
    }
    url = "/api/v1/consumption-chart"
    assert client.get(url, params=params).status_code == 401
    response = client.get(url, params=params, headers=viewer_headers)
    assert response.status_code == 200
    assert response.json()["model_version"] == settings.local_model_version
    error = client.get(url, params={**params, "limit": 500}, headers=viewer_headers)
    assert error.status_code == 422
    assert error.json()["error"]["code"] == "validation_error"
