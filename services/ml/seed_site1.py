#!/usr/bin/env python3
"""One-shot seed training: train a model for SITE001 and register it to MLflow.

This script is intended to be executed inside the mlflow container after the
mlflow server and MinIO are reachable. It uses services/ml/main.py helpers so
behaviour matches the main training pipeline.
"""

from __future__ import annotations

import os
import sys
import time

import mlflow
from mlflow import MlflowClient

try:
    # import helpers from services/ml/main.py (module name: main)
    from main import Config, build_supervised_frame, load_csv, load_from_db, train_site
except Exception as exc:  # pragma: no cover - defensive
    print("Failed to import training helpers from main.py:", exc, file=sys.stderr)
    raise


def wait_for_mlflow(uri: str, timeout: int = 30) -> bool:
    mlflow.set_tracking_uri(uri)
    client = MlflowClient()
    start = time.time()
    while True:
        try:
            # a light operation to check connectivity
            _ = client.search_experiments(max_results=1)
            return True
        except Exception as exc:
            if time.time() - start > timeout:
                print("MLflow did not become available within timeout:", exc, file=sys.stderr)
                return False
            time.sleep(2)


def main() -> int:
    mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    site_id = os.environ.get("SEED_SITE_ID", "SITE001")

    print(f"Seed training: MLflow={mlflow_uri}, site_id={site_id}")

    if not wait_for_mlflow(mlflow_uri, timeout=60):
        return 2

    # Build config with low min_train_rows to force seeding on small datasets
    cfg = Config()
    cfg.csv = os.environ.get("SEED_CSV_PATH", "services/ml/donnees.csv")
    cfg.use_db = False
    cfg.min_train_rows = 1
    cfg.train_months = int(os.environ.get("SEED_TRAIN_MONTHS", cfg.train_months))
    cfg.holdout_months = int(os.environ.get("SEED_HOLDOUT_MONTHS", cfg.holdout_months))

    # Load source (CSV preferred for local seed)
    try:
        source = load_csv(cfg.csv)
    except FileNotFoundError:
        # fallback to DB if CSV not available
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            print("Neither CSV found nor DATABASE_URL set; cannot seed.", file=sys.stderr)
            return 3
        source = load_from_db()

    supervised = build_supervised_frame(source, cfg.horizon_minutes)
    site_frame = supervised[supervised["site_id"] == site_id]
    if site_frame.empty:
        print(f"No data for site '{site_id}' in supervised frame; nothing to train.")
        return 0

    client = MlflowClient()
    result = train_site(cfg, client, site_id, site_frame)

    if result is None:
        print("train_site returned None (insufficient rows or other filter).")
        return 0

    print("Seed training completed:", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
