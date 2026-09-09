#!/usr/bin/env python3
"""Compare sites in DB with registered MLflow models and list missing ones.

Usage (preferred, uses Doppler-injected env vars inside docker):
  doppler run -p eadl_2025_niort_g1 -c dev -- \
    docker compose run --rm api python3 scripts/check_models_vs_sites.py

Or locally if env vars are set:
  DATABASE_URL=<db_url> \
    MLFLOW_TRACKING_URI=http://mlflow:5000 python3 scripts/check_models_vs_sites.py
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from sqlalchemy import create_engine, text
except Exception:
    print(
        "Missing dependency: sqlalchemy. Run inside the backend container",
        file=sys.stderr,
    )
    raise

try:
    from mlflow import MlflowClient
except Exception:
    print(
        "Missing dependency: mlflow. Run inside the backend container",
        file=sys.stderr,
    )
    raise


def get_site_ids(engine) -> list[str]:
    query = text(
        "SELECT DISTINCT site_id FROM readings WHERE consumption_kwh IS NOT NULL ORDER BY site_id"
    )
    with engine.connect() as conn:
        result = conn.execute(query)
        return [str(row[0]) for row in result]


def get_registered_model_names(client: MlflowClient) -> list[str]:
    # mlflow versions provide different listing APIs. Try multiple ways.
    try:
        models = client.list_registered_models()
        return [m.name for m in models]
    except AttributeError:
        # Fallback: collect model names from model versions
        try:
            versions = client.search_model_versions(filter_string="")
        except TypeError:
            versions = client.search_model_versions()
        names = set()
        for v in versions:
            name = getattr(v, "name", None)
            if name is None and isinstance(v, dict):
                name = v.get("name")
            if name:
                names.add(name)
        return sorted(names)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-prefix",
        default="EnerVision_RF_Predictor",
        help="Registered model name prefix",
    )
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL"), help="SQLAlchemy DB URL")
    parser.add_argument(
        "--mlflow-uri",
        default=os.getenv("MLFLOW_TRACKING_URI"),
        help="MLflow tracking URI",
    )
    args = parser.parse_args(argv)

    if not args.db_url:
        print("Error: DATABASE_URL not provided (set env or pass --db-url)", file=sys.stderr)
        return 2
    if not args.mlflow_uri:
        print(
            "Error: MLFLOW_TRACKING_URI not provided (set env or pass --mlflow-uri)",
            file=sys.stderr,
        )
        return 2

    print("Connecting to DB and MLflow...")
    try:
        engine = create_engine(args.db_url)
    except Exception as exc:
        print(f"Error creating DB engine: {exc}", file=sys.stderr)
        return 3

    try:
        sites = get_site_ids(engine)
    except Exception as exc:
        print(f"Error querying sites: {exc}", file=sys.stderr)
        return 4

    try:
        client = MlflowClient(tracking_uri=args.mlflow_uri)
        registered = get_registered_model_names(client)
    except Exception as exc:
        print(f"Error connecting to MLflow: {exc}", file=sys.stderr)
        return 5

    expected = {f"{args.model_prefix}_{site}" for site in sites}
    registered_set = set(registered)

    missing = sorted(list(expected - registered_set))

    print()
    print(f"Sites found in readings: {len(sites)}")
    print(f"Registered models (total): {len(registered)}")
    print(
        f"Registered models matching prefix '{args.model_prefix}_{{site_id}}': "
        f"{len(registered_set & expected)}"
    )
    print()

    if missing:
        print(f"Missing models for {len(missing)} sites:")
        for name in missing:
            site = name[len(args.model_prefix) + 1 :]
            print(f" - site_id={site} -> expected model name: {name}")
        print()
        print(
            "Next steps: run the training for missing sites, or inspect training logs for"
            " sites that were skipped due to insufficient data (min_train_rows)."
        )
        return 7
    else:
        print("All sites have a registered model (matching prefix).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
