#!/usr/bin/env python3
"""Train one forecasting model per site and register each in MLflow."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from pandas import Timestamp
from seo_features import build_feature_frame
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import create_engine

TARGET_COLUMN = "target_kwh"


@dataclass
class Config:
    csv: str | None = None
    use_db: bool = False
    experiment: str = "EnerVision_Pred_Conso"
    model_name_prefix: str = "EnerVision_RF_Predictor"
    production_alias: str = "production"
    set_production_alias: bool = True
    horizon_minutes: int = 120
    train_months: int = 22
    holdout_months: int = 2
    random_state: int = 42
    n_estimators: int = 150
    max_depth: int | None = 15
    n_jobs: int = -1
    min_train_rows: int = 500


def parse_args(argv: list[str] | None = None) -> Config:
    parser = argparse.ArgumentParser(description="Train per-site forecasting models with MLflow")
    parser.add_argument("--csv", required=False, help="Path to CSV fallback source")
    parser.add_argument(
        "--use-db", action="store_true", help="Load from DATABASE_URL and readings table"
    )
    parser.add_argument(
        "--experiment", default="EnerVision_Pred_Conso", help="MLflow experiment name"
    )
    parser.add_argument(
        "--model-name-prefix",
        default="EnerVision_RF_Predictor",
        help="Registered model prefix, final name is <prefix>_<site_id>",
    )
    parser.add_argument("--production-alias", default="production", help="Registry alias to update")
    parser.add_argument(
        "--no-production-alias",
        action="store_true",
        help="Do not update the registry alias after training",
    )
    parser.add_argument(
        "--horizon-minutes", type=int, default=120, help="Forecast horizon in minutes"
    )
    parser.add_argument("--train-months", type=int, default=22, help="Training window in months")
    parser.add_argument("--holdout-months", type=int, default=2, help="Holdout window in months")
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=150)
    parser.add_argument("--max-depth", type=int, default=15)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--min-train-rows", type=int, default=500)
    args = parser.parse_args(argv)
    return Config(
        csv=args.csv,
        use_db=args.use_db,
        experiment=args.experiment,
        model_name_prefix=args.model_name_prefix,
        production_alias=args.production_alias,
        set_production_alias=not args.no_production_alias,
        horizon_minutes=args.horizon_minutes,
        train_months=args.train_months,
        holdout_months=args.holdout_months,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        n_jobs=args.n_jobs,
        min_train_rows=args.min_train_rows,
    )


def load_csv(path: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(path)

    frame = pd.read_csv(csv_path)
    return _sanitize_source(frame)


def load_from_db() -> pd.DataFrame:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is required when using --use-db")

    engine = create_engine(database_url)
    query = """
        SELECT
            r.site_id,
            r.measured_at,
            r.consumption_kwh,
            r.temperature_celsius,
            r.humidity_percent,
            s.site_type
        FROM readings r
        LEFT JOIN sites s ON s.site_id = r.site_id
        WHERE r.consumption_kwh IS NOT NULL
    """
    frame = pd.read_sql(query, engine)
    return _sanitize_source(frame)


def _sanitize_source(frame: pd.DataFrame) -> pd.DataFrame:
    source = frame.copy()
    rename_map = {
        "timestamp": "measured_at",
        "consumption_kw": "consumption_kwh",
    }
    source = source.rename(columns=rename_map)
    required = {"site_id", "measured_at", "consumption_kwh"}
    missing = required.difference(source.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise KeyError(f"Missing required columns: {missing_cols}")

    source["measured_at"] = pd.to_datetime(source["measured_at"], utc=True)
    source = source.sort_values(["site_id", "measured_at"]).reset_index(drop=True)
    source = source.dropna(subset=["consumption_kwh"])
    return source


def build_supervised_frame(source: pd.DataFrame, horizon_minutes: int) -> pd.DataFrame:
    featured = build_feature_frame(source)
    featured[TARGET_COLUMN] = featured.groupby("site_id")["consumption_kwh"].shift(-horizon_minutes)
    return featured.dropna(subset=["consumption_kwh", TARGET_COLUMN]).reset_index(drop=True)


def temporal_split(
    frame: pd.DataFrame,
    train_months: int,
    holdout_months: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    max_ts: Timestamp = frame["measured_at"].max()
    holdout_start = (max_ts - pd.DateOffset(months=holdout_months)).normalize()
    train_start = (holdout_start - pd.DateOffset(months=train_months)).normalize()
    train_df = frame[
        (frame["measured_at"] >= train_start) & (frame["measured_at"] < holdout_start)
    ].copy()
    holdout_df = frame[frame["measured_at"] >= holdout_start].copy()
    if train_df.empty or holdout_df.empty:
        raise ValueError(
            "Temporal split produced empty train or holdout. "
            f"train={train_df.shape}, holdout={holdout_df.shape}"
        )
    return train_df, holdout_df


def split_features_target(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    x = frame.drop(columns=[TARGET_COLUMN], errors="ignore")
    y = frame[TARGET_COLUMN]
    return x, y


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(y_true - y_pred)))
    return {"rmse": rmse, "mae": mae}


def model_for_site(cfg: Config) -> Pipeline:
    categorical = ["site_id", "site_type"]
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore"),
                categorical,
            ),
        ],
        remainder="passthrough",
    )
    regressor = RandomForestRegressor(
        n_estimators=cfg.n_estimators,
        max_depth=cfg.max_depth,
        n_jobs=cfg.n_jobs,
        random_state=cfg.random_state,
    )
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", regressor),
        ]
    )


def register_alias(
    client: MlflowClient,
    model_name: str,
    alias: str,
    run_id: str,
) -> str | None:
    versions = client.search_model_versions(filter_string=f"name = '{model_name}'")
    matching = [version for version in versions if version.run_id == run_id]
    if not matching:
        return None
    latest_version = max(matching, key=lambda model_version: int(model_version.version))
    client.set_registered_model_alias(
        name=model_name,
        alias=alias,
        version=latest_version.version,
    )
    return latest_version.version


def train_site(
    cfg: Config,
    client: MlflowClient,
    site_id: str,
    frame: pd.DataFrame,
) -> dict[str, object] | None:
    train_df, holdout_df = temporal_split(frame, cfg.train_months, cfg.holdout_months)
    if len(train_df) < cfg.min_train_rows:
        return None

    x_train, y_train = split_features_target(train_df)
    x_holdout, y_holdout = split_features_target(holdout_df)
    model = model_for_site(cfg)

    with mlflow.start_run(run_name=f"train-{site_id}") as run:
        mlflow.log_params(
            {
                "site_id": site_id,
                "horizon_minutes": cfg.horizon_minutes,
                "train_months": cfg.train_months,
                "holdout_months": cfg.holdout_months,
                "n_estimators": cfg.n_estimators,
                "max_depth": cfg.max_depth,
            }
        )
        model.fit(x_train, y_train)
        predictions = model.predict(x_holdout)
        metrics = evaluate(y_holdout.to_numpy(), predictions)
        mlflow.log_metrics(metrics)

        registered_name = f"{cfg.model_name_prefix}_{site_id}"
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=registered_name,
        )

        alias_version: str | None = None
        if cfg.set_production_alias:
            alias_version = register_alias(
                client=client,
                model_name=registered_name,
                alias=cfg.production_alias,
                run_id=run.info.run_id,
            )

        return {
            "site_id": site_id,
            "rows_train": len(train_df),
            "rows_holdout": len(holdout_df),
            "metrics": metrics,
            "registered_model_name": registered_name,
            "alias": cfg.production_alias if alias_version else None,
            "alias_version": alias_version,
        }


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    if cfg.use_db:
        source = load_from_db()
    else:
        if not cfg.csv:
            raise ValueError("Provide --use-db or --csv <path>")
        source = load_csv(cfg.csv)
    supervised = build_supervised_frame(source, cfg.horizon_minutes)
    mlflow.set_experiment(cfg.experiment)
    client = MlflowClient()

    trained = 0
    skipped = 0
    for site_id, site_frame in supervised.groupby("site_id", sort=True):
        result = train_site(cfg, client, site_id, site_frame)
        if result is None:
            skipped += 1
            print(f"Skipped site {site_id}: insufficient train rows")
            continue
        trained += 1
        print(
            f"Trained site {site_id}: "
            f"rmse={result['metrics']['rmse']:.3f}, "
            f"mae={result['metrics']['mae']:.3f}, "
            f"model={result['registered_model_name']}, "
            f"alias_version={result['alias_version']}"
        )

    if trained == 0:
        raise ValueError("No model trained. Check source data volume and min-train-rows.")

    print(f"Training complete: trained={trained}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MlflowException, ValueError, KeyError, FileNotFoundError) as exc:
        print("Error:", exc, file=sys.stderr)
        raise
