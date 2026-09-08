#!/usr/bin/env python3
"""Databricks / notebook example: train one site and register model to MLflow.

Usage on Databricks (notebook cell):
- Ensure cluster has mlflow, sqlalchemy, psycopg[binary], scikit-learn and seo-features installed
  (pip install git+https://github.com/your-org/your-repo.git#subdirectory=packages/features)
- Set MLflow tracking URI and DATABASE_URL (cluster env or in-notebook)

This script trains a single site ('site1' by default) from the database and
registers the model under EnerVision_RF_Predictor_<SITE_ID>.
"""

from __future__ import annotations

import os

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from seo_features import build_feature_frame
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import create_engine


def load_from_db(database_url: str) -> pd.DataFrame:
    engine = create_engine(database_url)
    query = (
        "SELECT r.site_id, r.measured_at, r.consumption_kwh, r.temperature_celsius, "
        "r.humidity_percent, s.site_type "
        "FROM readings r "
        "LEFT JOIN sites s ON s.site_id = r.site_id "
        "WHERE r.consumption_kwh IS NOT NULL"
    )
    df = pd.read_sql(query, engine)
    df["measured_at"] = pd.to_datetime(df["measured_at"], utc=True)
    return df


def train_single_site(site_id: str, df: pd.DataFrame, horizon_minutes: int = 120) -> dict:
    df_site = df[df["site_id"] == site_id].sort_values("measured_at").reset_index(drop=True)
    features = build_feature_frame(df_site)
    features["target_kwh"] = features.groupby("site_id")["consumption_kwh"].shift(-horizon_minutes)
    features = features.dropna(subset=["target_kwh"]).reset_index(drop=True)

    x = features.drop(columns=["target_kwh", "measured_at", "consumption_kwh"], errors="ignore")
    y = features["target_kwh"]

    categorical = [c for c in ["site_id", "site_type"] if c in x.columns]
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ],
        remainder="passthrough",
    )
    model = Pipeline(
        [("pre", preprocessor), ("rf", RandomForestRegressor(n_estimators=100, n_jobs=-1))]
    )

    model.fit(x, y)
    preds = model.predict(x)
    rmse = float(np.sqrt(mean_squared_error(y, preds)))

    # Log to mlflow and register
    mlflow.log_metric("rmse", rmse)
    reg_name = f"EnerVision_RF_Predictor_{site_id}"
    mlflow.sklearn.log_model(sk_model=model, artifact_path="model", registered_model_name=reg_name)

    return {"site_id": site_id, "rmse": rmse, "registered_model": reg_name}


if __name__ == "__main__":
    ML_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL must be set in environment")

    mlflow.set_tracking_uri(ML_URI)
    mlflow.set_experiment("EnerVision_Pred_Conso")

    df = load_from_db(DATABASE_URL)
    result = train_single_site("site1", df, horizon_minutes=120)
    print("Done:", result)
