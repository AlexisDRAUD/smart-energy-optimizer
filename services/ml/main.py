#!/usr/bin/env python3
"""Train one forecasting model per site and register each in MLflow."""

from __future__ import annotations

import argparse
import fcntl
import os
import sys
from contextlib import nullcontext
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
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import create_engine, text

TARGET_COLUMN = "target_kwh"
NUMERIC_FEATURES = [
    "temperature_celsius",
    "humidity_percent",
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "is_working_hours",
    "lag_1",
    "lag_60",
    "lag_120",
    "rolling_mean_30",
    "rolling_mean_120",
]
FEATURE_COLUMNS = ["site_id", "site_type", *NUMERIC_FEATURES]


@dataclass
class Config:
    csv: str | None = None
    use_db: bool = True
    experiment: str = "EnerVision_Pred_Conso"
    model_name_prefix: str = "EnerVision_RF_Predictor"
    production_alias: str = "production"
    set_production_alias: bool = True
    horizon_minutes: int = 120
    train_months: int = 22
    holdout_months: int = 2
    holdout_minutes: int | None = None
    random_state: int = 42
    n_estimators: int = 150
    max_depth: int | None = 15
    n_jobs: int = -1
    min_train_rows: int = 500
    site_id: str | None = None
    estimator: str = "random_forest"
    job_run_id: str | None = None
    # When true, only perform a check comparing sites in DB and registered models
    check_models: bool = False


def parse_args(argv: list[str] | None = None) -> Config:
    parser = argparse.ArgumentParser(description="Train per-site forecasting models with MLflow")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--csv", required=False, help="Path to CSV fallback source")
    source.add_argument(
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
    parser.add_argument(
        "--holdout-minutes", type=int, help="Override holdout months for short histories"
    )
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=150)
    parser.add_argument("--max-depth", type=int, default=15)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--min-train-rows", type=int, default=500)
    parser.add_argument("--site-id")
    parser.add_argument(
        "--estimator", choices=["random_forest", "extra_trees"], default="random_forest"
    )
    parser.add_argument("--job-run-id")
    parser.add_argument(
        "--check-models",
        action="store_true",
        help="Vérifie les sites en base vs modèles enregistrés MLflow et affiche les manquants",
    )
    args = parser.parse_args(argv)
    if args.holdout_minutes is not None and args.holdout_minutes <= 0:
        parser.error("--holdout-minutes must be positive")
    for name in (
        "horizon_minutes",
        "train_months",
        "holdout_months",
        "min_train_rows",
        "n_estimators",
    ):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    return Config(
        csv=args.csv,
        use_db=not bool(args.csv),
        experiment=args.experiment,
        model_name_prefix=args.model_name_prefix,
        production_alias=args.production_alias,
        set_production_alias=not args.no_production_alias,
        horizon_minutes=args.horizon_minutes,
        train_months=args.train_months,
        holdout_months=args.holdout_months,
        holdout_minutes=args.holdout_minutes,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        n_jobs=args.n_jobs,
        min_train_rows=args.min_train_rows,
        site_id=args.site_id,
        estimator=args.estimator,
        job_run_id=args.job_run_id,
        check_models=args.check_models,
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
    try:
        with engine.connect() as connection:
            frame = pd.read_sql(query, connection)
    finally:
        engine.dispose()
    return _sanitize_source(frame)


def _sanitize_source(frame: pd.DataFrame) -> pd.DataFrame:
    source = frame.copy()
    rename_map = {
        "timestamp": "measured_at",
        "consumption_kw": "consumption_kwh",
    }
    source = source.rename(
        columns={old: new for old, new in rename_map.items() if new not in source.columns}
    )
    required = {"site_id", "measured_at", "consumption_kwh"}
    missing = required.difference(source.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise KeyError(f"Missing required columns: {missing_cols}")

    source["measured_at"] = pd.to_datetime(source["measured_at"], utc=True)
    source["consumption_kwh"] = pd.to_numeric(source["consumption_kwh"], errors="coerce")
    for column in ("temperature_celsius", "humidity_percent"):
        source[column] = pd.to_numeric(
            source.get(column, pd.Series(np.nan, index=source.index)), errors="coerce"
        ).replace([np.inf, -np.inf], np.nan)
    source["site_type"] = source.get("site_type", pd.Series("unknown", index=source.index)).fillna(
        "unknown"
    )
    source = source.dropna(subset=["site_id", "measured_at", "consumption_kwh"])
    source = source[np.isfinite(source["consumption_kwh"])]
    if source.duplicated(["site_id", "measured_at"]).any():
        raise ValueError("Duplicate readings for the same site and timestamp")
    source = source.sort_values(["site_id", "measured_at"]).reset_index(drop=True)
    source = source.dropna(subset=["consumption_kwh"])
    return source


def build_supervised_frame(source: pd.DataFrame, horizon_minutes: int) -> pd.DataFrame:
    if horizon_minutes <= 0:
        raise ValueError("horizon_minutes must be positive")
    featured = build_feature_frame(source)
    featured["target_at"] = featured["measured_at"] + pd.Timedelta(minutes=horizon_minutes)
    targets = source[["site_id", "measured_at", "consumption_kwh"]].rename(
        columns={"measured_at": "target_at", "consumption_kwh": TARGET_COLUMN}
    )
    featured = featured.merge(targets, on=["site_id", "target_at"], validate="one_to_one")
    return featured.dropna(subset=["consumption_kwh", TARGET_COLUMN]).reset_index(drop=True)


def temporal_split(
    frame: pd.DataFrame,
    train_months: int,
    holdout_months: int,
    holdout_minutes: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    max_ts: Timestamp = frame["measured_at"].max()
    holdout_start = (max_ts - pd.DateOffset(months=holdout_months)).normalize()
    if holdout_minutes is not None:
        holdout_start = max_ts - pd.Timedelta(minutes=holdout_minutes)
    train_start = (holdout_start - pd.DateOffset(months=train_months)).normalize()
    train_df = frame[
        (frame["measured_at"] >= train_start)
        & (frame["measured_at"] < holdout_start)
        & (frame["target_at"] < holdout_start)
    ].copy()
    holdout_df = frame[frame["measured_at"] >= holdout_start].copy()
    if train_df.empty or holdout_df.empty:
        raise ValueError(
            "Temporal split produced empty train or holdout. "
            f"train={train_df.shape}, holdout={holdout_df.shape}"
        )
    return train_df, holdout_df


def split_features_target(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    x = frame[FEATURE_COLUMNS]
    y = frame[TARGET_COLUMN]
    return x, y


def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(y_true - y_pred)))
    metrics = {"rmse": rmse, "mae": mae}
    if len(y_true) >= 2:
        metrics["r2"] = float(r2_score(y_true, y_pred))
    return metrics


def log_holdout(frame: pd.DataFrame, predictions: np.ndarray) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    comparison = frame[["site_id", "measured_at", "target_at", TARGET_COLUMN]].copy()
    comparison["predicted_kwh"] = predictions
    mlflow.log_text(comparison.to_csv(index=False), "holdout/predictions.csv")
    fig, ax = plt.subplots(figsize=(12, 4))
    # Keep the plot readable without discarding rows from the CSV.
    plotted = comparison.iloc[:: max(1, len(comparison) // 2000)]
    ax.plot(plotted["target_at"], plotted[TARGET_COLUMN], label="Actual")
    ax.plot(plotted["target_at"], plotted["predicted_kwh"], label="Predicted")
    ax.set_ylabel("Consumption (kWh)")
    ax.legend()
    fig.autofmt_xdate()
    try:
        mlflow.log_figure(fig, "holdout/actual_vs_predicted.png")
    finally:
        plt.close(fig)


def model_for_site(cfg: Config) -> Pipeline:
    categorical = ["site_id", "site_type"]
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore"),
                categorical,
            ),
            (
                "num",
                SimpleImputer(strategy="constant", fill_value=0, keep_empty_features=True),
                NUMERIC_FEATURES,
            ),
        ],
        remainder="drop",
    )
    estimator = {"random_forest": RandomForestRegressor, "extra_trees": ExtraTreesRegressor}
    regressor = estimator[cfg.estimator](
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
        raise ValueError(f"No registered version found for {model_name}")
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
    try:
        train_df, holdout_df = temporal_split(
            frame, cfg.train_months, cfg.holdout_months, cfg.holdout_minutes
        )
    except ValueError:
        return None
    if len(train_df) < cfg.min_train_rows:
        return None

    x_train, y_train = split_features_target(train_df)
    x_holdout, y_holdout = split_features_target(holdout_df)
    model = model_for_site(cfg)

    with mlflow.start_run(run_name=f"train-{site_id}", nested=bool(cfg.job_run_id)) as run:
        mlflow.log_params(
            {
                "site_id": site_id,
                "horizon_minutes": cfg.horizon_minutes,
                "train_months": cfg.train_months,
                "holdout_months": cfg.holdout_months,
                "holdout_minutes": cfg.holdout_minutes,
                "n_estimators": cfg.n_estimators,
                "max_depth": cfg.max_depth,
                "estimator": cfg.estimator,
                "rows_train": len(train_df),
                "rows_holdout": len(holdout_df),
            }
        )
        model.fit(x_train, y_train)
        predictions = model.predict(x_holdout)
        metrics = evaluate(y_holdout.to_numpy(), predictions)
        mlflow.log_metrics(metrics)
        log_holdout(holdout_df, predictions)

        registered_name = f"{cfg.model_name_prefix}_{site_id}"
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE,
            registered_model_name=registered_name,
            signature=mlflow.models.infer_signature(x_train, predictions),
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


def get_db_sites(database_url: str | None = None) -> list[str]:
    """Récupère la liste distincte des identifiants de sites ayant des mesures."""
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is required to query sites")
    engine = create_engine(url)
    query = text(
        "SELECT DISTINCT site_id FROM readings WHERE consumption_kwh IS NOT NULL ORDER BY site_id"
    )
    try:
        with engine.connect() as connection:
            result = connection.execute(query)
            return [str(row[0]) for row in result]
    finally:
        engine.dispose()


def get_registered_models(client: MlflowClient) -> list[str]:
    """Récupère les noms des modèles enregistrés dans MLflow."""
    try:
        models = client.search_registered_models()
        return [m.name for m in models]
    except Exception:
        try:
            versions = client.search_model_versions(filter_string="")
            names = set()
            for v in versions:
                name = getattr(v, "name", None)
                if name is None and isinstance(v, dict):
                    name = v.get("name")
                if name:
                    names.add(name)
            return sorted(names)
        except Exception:
            return []


def check_models_vs_sites(cfg: Config) -> list[str]:
    """Vérifie le nombre de sites vs modèles enregistrés et renvoie les modèles manquants."""
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient()

    sites = get_db_sites()
    registered = get_registered_models(client)
    registered_set = set(registered)

    expected = {f"{cfg.model_name_prefix}_{site}" for site in sites}
    missing = sorted(list(expected - registered_set))

    print("\n==================================================", flush=True)
    print("📊 Bilan : Sites vs Modèles MLflow", flush=True)
    print("==================================================", flush=True)
    print(f"Nombre total de sites en base : {len(sites)}", flush=True)
    print(
        f"Modèles enregistrés : {len(registered_set & expected)}/{len(sites)}",
        flush=True,
    )

    if missing:
        print(f"\n⚠️  {len(missing)} modèle(s) manquant(s) :", flush=True)
        for model_name in missing:
            site_id = model_name[len(cfg.model_name_prefix) + 1 :]
            print(f"  ❌ Site {site_id} -> Manquant : {model_name}", flush=True)
    else:
        print("\n✅ Tous les sites possèdent un modèle MLflow enregistré.", flush=True)
    print("==================================================\n", flush=True)

    return missing


def run_training(cfg: Config) -> int:
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    if cfg.use_db:
        source = load_from_db()
    else:
        if not cfg.csv:
            raise ValueError("Provide --use-db or --csv <path>")
        source = load_csv(cfg.csv)
    if cfg.site_id:
        source = source[source["site_id"].astype(str) == cfg.site_id]
        if source.empty:
            raise ValueError("Selected site has no readings")
    supervised = build_supervised_frame(source, cfg.horizon_minutes)
    experiment = mlflow.set_experiment(cfg.experiment)
    if (
        tracking_uri
        and tracking_uri.startswith(("http://", "https://"))
        and not experiment.artifact_location.startswith("mlflow-artifacts:/")
    ):
        raise ValueError(
            "This experiment does not use proxied artifacts. Use --experiment with a new name "
            "on the artifact-proxy server; existing artifact locations are not migrated."
        )
    client = MlflowClient()

    site_groups = list(supervised.groupby("site_id", sort=True))
    total_sites = len(site_groups)

    print("\n==================================================", flush=True)
    print(f"📋 Liste des modèles prévus à l'entraînement ({total_sites} sites) :", flush=True)
    for idx, (s_id, frame) in enumerate(site_groups, 1):
        print(
            f"  [{idx}/{total_sites}] Site {s_id} -> Modèle : {cfg.model_name_prefix}_{s_id} "
            f"({len(frame)} observations)",
            flush=True,
        )
    print("==================================================\n", flush=True)

    trained = 0
    skipped = 0
    for idx, (site_id, site_frame) in enumerate(site_groups, 1):
        model_name = f"{cfg.model_name_prefix}_{site_id}"
        print(
            f"⏳ [{idx}/{total_sites}] Entraînement en cours : Site {site_id} ({model_name})...",
            flush=True,
        )
        result = train_site(cfg, client, site_id, site_frame)
        if result is None:
            skipped += 1
            print(
                f"⚠️  [{idx}/{total_sites}] Site {site_id} ignoré : "
                f"données d'entraînement insuffisantes (< {cfg.min_train_rows} lignes)",
                flush=True,
            )
            continue
        trained += 1
        print(
            f"✅ [{idx}/{total_sites}] Site {site_id} terminé : "
            f"rmse={result['metrics']['rmse']:.3f}, "
            f"mae={result['metrics']['mae']:.3f}, "
            f"modèle={result['registered_model_name']}, "
            f"version={result['alias_version']}",
            flush=True,
        )

    if trained == 0:
        raise ValueError("No model trained. Check source data volume and min-train-rows.")

    print(f"\n🎉 Entraînement terminé : {trained} entraînés, {skipped} ignorés.", flush=True)
    if cfg.use_db:
        check_models_vs_sites(cfg)
    return 0


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    if cfg.check_models:
        check_models_vs_sites(cfg)
        return 0

    inherited = os.getenv("ML_TRAIN_LOCK_FD")
    with (
        os.fdopen(int(inherited), "w")
        if inherited
        else Path(os.getenv("ML_TRAIN_LOCK_PATH", "training.lock")).open("w")
    ) as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another training job is already running") from None
        context = mlflow.start_run(run_id=cfg.job_run_id) if cfg.job_run_id else nullcontext()
        with context:
            try:
                return run_training(cfg)
            except Exception as exc:
                if cfg.job_run_id:
                    mlflow.set_tag(
                        "training.error",
                        f"{type(exc).__name__}: training failed; "
                        "check container logs and data volume/holdout settings.",
                    )
                raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MlflowException, ValueError, KeyError, FileNotFoundError) as exc:
        print("Error:", exc, file=sys.stderr)
        raise
