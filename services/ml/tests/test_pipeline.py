import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from seo_features import build_feature_frame

spec = importlib.util.spec_from_file_location("training", Path(__file__).parents[1] / "main.py")
training = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = training
spec.loader.exec_module(training)


def readings(periods=500):
    return training._sanitize_source(
        pd.DataFrame(
            {
                "site_id": ["one"] * periods,
                "measured_at": pd.date_range("2026-01-01", periods=periods, freq="5min", tz="UTC"),
                "consumption_kwh": np.arange(periods, dtype=float),
                "consumption_kw": ["unused"] * periods,
                "raw_leak": np.arange(periods),
            }
        )
    )


def test_db_default_and_exclusive_sources():
    assert training.parse_args([]).use_db
    assert not training.parse_args(["--csv", "readings.csv"]).use_db
    with pytest.raises(SystemExit):
        training.parse_args(["--csv", "readings.csv", "--use-db"])


def test_exact_horizon_and_missing_timestamps():
    source = readings().drop(index=24)
    frame = training.build_supervised_frame(source, 120)
    assert source["consumption_kwh"].ndim == 1
    assert not (frame["consumption_kwh"] == 0).any()
    assert (frame[training.TARGET_COLUMN] - frame["consumption_kwh"] == 24).all()


def test_purge_and_serving_contract():
    source = readings()
    frame = training.build_supervised_frame(source, 120)
    train, holdout = training.temporal_split(frame, 22, 2, 120)
    assert train["target_at"].max() < holdout["measured_at"].min()
    x, y = training.split_features_target(train)
    model = training.model_for_site(training.Config(n_estimators=2, n_jobs=1))
    model.fit(x, y)
    serving = build_feature_frame(
        source.tail(240).assign(temperature_celsius=None, humidity_percent=None)
    ).tail(1)
    assert np.isfinite(model.predict(serving)).all()
    assert not {
        "target_kwh",
        "target_at",
        "measured_at",
        "raw_leak",
        "consumption_kwh",
        "consumption_kw",
    } & set(x.columns)
    assert model.named_steps["preprocessor"].transform(serving).shape[1] < 30


def test_rolling_features_do_not_cross_sites():
    source = readings(5)
    other = source.assign(site_id="two", consumption_kwh=1000.0)
    features = build_feature_frame(pd.concat([source, other]))
    second = features[features.site_id == "two"]
    assert (second.rolling_mean_30 == 1000).all()
    assert (second.rolling_mean_120 == 1000).all()


def test_regression_metrics_and_holdout_artifacts(monkeypatch):
    metrics = training.evaluate(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    assert metrics == {"mae": 0.0, "rmse": 0.0, "r2": 1.0}
    assert "r2" not in training.evaluate(np.array([1.0]), np.array([1.0]))
    artifacts = {}
    monkeypatch.setattr(
        training.mlflow, "log_text", lambda content, path: artifacts.update({path: content})
    )
    monkeypatch.setattr(
        training.mlflow, "log_figure", lambda figure, path: artifacts.update({path: figure})
    )
    frame = training.build_supervised_frame(readings(), 120).tail(5)
    training.log_holdout(frame, frame[training.TARGET_COLUMN].to_numpy())
    assert "predicted_kwh" in artifacts["holdout/predictions.csv"]
    assert len(artifacts["holdout/predictions.csv"].splitlines()) == 6
    assert "holdout/actual_vs_predicted.png" in artifacts


def test_site_and_estimator_arguments():
    cfg = training.parse_args(["--site-id", "one", "--estimator", "extra_trees"])
    assert cfg.site_id == "one"
    assert isinstance(
        training.model_for_site(cfg).named_steps["regressor"], training.ExtraTreesRegressor
    )
