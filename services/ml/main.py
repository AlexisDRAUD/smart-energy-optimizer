#!/usr/bin/env python3
"""Train a RandomForestRegressor and track runs with MLflow.

Le script accepte deux sources de donnees:
1. PostgreSQL via DATABASE_URL (option --use-db)
2. CSV local (option --csv)
"""

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
from pandas import Timestamp
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from sqlalchemy import create_engine


@dataclass
class Config:
    csv: str | None = None
    use_db: bool = False
    timestamp_col: str = "timestamp"
    target: str = "consumption_kw"
    experiment: str = "EnerVision_Pred_Conso"
    model_name: str = "modele_rf_energie"
    registered_model_name: str = "EnerVision_RF_Predictor"
    train_months: int = 22
    holdout_months: int = 2
    random_state: int = 42
    n_estimators: int = 100
    max_depth: int | None = 15
    n_jobs: int | None = -1


def parse_args(argv: list[str] | None = None) -> Config:
    p = argparse.ArgumentParser(description="Train with temporal split and MLflow tracking")
    p.add_argument("--csv", required=False, help="Path to prepared CSV file")
    p.add_argument(
        "--use-db", action="store_true", help="Load data from DATABASE_URL instead of CSV"
    )
    p.add_argument(
        "--timestamp-col", default="timestamp", help="Name of timestamp column (ISO format)"
    )
    p.add_argument("--target", default="consumption_kw", help="Target column name")
    p.add_argument(
        "--experiment",
        default="EnerVision_Pred_Conso",
        help="MLflow experiment name",
    )
    p.add_argument("--model-name", default="modele_rf_energie", help="Model artifact name")
    p.add_argument(
        "--registered-model-name",
        default="EnerVision_RF_Predictor",
        help="MLflow Model Registry name",
    )
    p.add_argument("--train-months", type=int, default=22, help="Number of months to train on")
    p.add_argument(
        "--holdout-months", type=int, default=2, help="Number of months to reserve as holdout"
    )
    p.add_argument("--random-state", type=int, default=42)
    p.add_argument("--n-estimators", type=int, default=100)
    p.add_argument("--max-depth", type=int, default=15)
    p.add_argument("--n-jobs", type=int, default=-1)
    args = p.parse_args(argv)
    return Config(
        csv=args.csv,
        use_db=args.use_db,
        timestamp_col=args.timestamp_col,
        target=args.target,
        experiment=args.experiment,
        model_name=args.model_name,
        registered_model_name=args.registered_model_name,
        train_months=args.train_months,
        holdout_months=args.holdout_months,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        n_jobs=args.n_jobs,
    )


def load_csv(path: str, timestamp_col: str) -> pd.DataFrame:
    """Load and sanitize training data from CSV."""
    if not Path(path).exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path)
    if timestamp_col not in df.columns:
        raise KeyError(f"Timestamp column '{timestamp_col}' not found in CSV")

    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    df = df.sort_values(timestamp_col).reset_index(drop=True)
    df = df.dropna(subset=["consumption_kw"])
    return df


def load_from_db(timestamp_col: str) -> pd.DataFrame:
    """Load and sanitize training data from PostgreSQL (DATABASE_URL)."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is required when using --use-db")

    engine = create_engine(db_url)
    query = "SELECT * FROM energy_readings ORDER BY timestamp ASC"
    df = pd.read_sql(query, engine)

    if timestamp_col not in df.columns:
        raise KeyError(f"Timestamp column '{timestamp_col}' not found in DB result")

    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    df = df.sort_values(timestamp_col).reset_index(drop=True)
    df = df.dropna(subset=["consumption_kw"])
    return df


def temporal_split(
    df: pd.DataFrame, timestamp_col: str, train_months: int, holdout_months: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    max_ts: Timestamp = df[timestamp_col].max()
    holdout_start = (max_ts - pd.DateOffset(months=holdout_months)).normalize()
    train_start = (holdout_start - pd.DateOffset(months=train_months)).normalize()

    train_df = df[(df[timestamp_col] >= train_start) & (df[timestamp_col] < holdout_start)].copy()
    holdout_df = df[df[timestamp_col] >= holdout_start].copy()

    if train_df.empty or holdout_df.empty:
        raise ValueError(
            f"Temporal split produced empty train or holdout. "
            f"train.shape={train_df.shape}, holdout.shape={holdout_df.shape}"
        )

    return train_df, holdout_df


def prepare_features(
    df: pd.DataFrame, target: str, timestamp_col: str
) -> tuple[pd.DataFrame, pd.Series]:
    if target not in df.columns:
        raise KeyError(f"Target column '{target}' missing")

    x = df.drop(columns=[target, timestamp_col], errors="ignore")
    y = df[target]

    cat_cols = x.select_dtypes(include=["object", "category"]).columns.tolist()
    if cat_cols:
        x = pd.get_dummies(x, columns=cat_cols, drop_first=True)

    x = x.fillna(0)
    return x, y


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    mae = float(np.mean(np.abs(y_true - y_pred)))
    return {"rmse": float(rmse), "mae": float(mae)}


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)

    mlflow_tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if mlflow_tracking_uri:
        mlflow.set_tracking_uri(mlflow_tracking_uri)

    if cfg.use_db:
        print("Loading data from DB (DATABASE_URL)...")
        df = load_from_db(cfg.timestamp_col)
    else:
        if not cfg.csv:
            raise ValueError("No input specified: provide --csv <path> or --use-db")
        print("Loading CSV:", cfg.csv)
        df = load_csv(cfg.csv, cfg.timestamp_col)

    min_ts = df[cfg.timestamp_col].min()
    max_ts = df[cfg.timestamp_col].max()
    print(f"Data rows: {len(df)}, time range: {min_ts} -> {max_ts}")

    train_df, holdout_df = temporal_split(
        df, cfg.timestamp_col, cfg.train_months, cfg.holdout_months
    )
    print(f"Train rows: {len(train_df)}, Holdout rows: {len(holdout_df)}")

    x_train, y_train = prepare_features(train_df, cfg.target, cfg.timestamp_col)
    x_hold, y_hold = prepare_features(holdout_df, cfg.target, cfg.timestamp_col)

    x_hold = x_hold.reindex(columns=x_train.columns, fill_value=0)

    mlflow.set_experiment(cfg.experiment)
    with mlflow.start_run():
        mlflow.log_param("train_months", cfg.train_months)
        mlflow.log_param("holdout_months", cfg.holdout_months)
        mlflow.log_param("n_estimators", cfg.n_estimators)
        mlflow.log_param("max_depth", cfg.max_depth)

        model = RandomForestRegressor(
            n_estimators=cfg.n_estimators,
            max_depth=cfg.max_depth,
            n_jobs=cfg.n_jobs,
            random_state=cfg.random_state,
        )
        print("Training model...")
        model.fit(x_train, y_train)

        print("Predicting holdout set...")
        preds = model.predict(x_hold)
        metrics = evaluate(y_hold.to_numpy(), preds)
        print("Metrics:", metrics)

        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path=cfg.model_name,
            registered_model_name=cfg.registered_model_name,
        )

        print(f"Run saved with id: {mlflow.active_run().info.run_id}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("Error:", exc, file=sys.stderr)
        raise
