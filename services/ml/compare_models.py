#!/usr/bin/env python3
"""Comparer plusieurs stratégies de création de modèle et produire des charts.

Stratégies implémentées:
 - global_rf: modèle RandomForest entraîné sur toutes les données
 - global_lgb: modèle LightGBM entraîné sur toutes les données (si disponible)
 - per_site_rf: modèle RandomForest entraîné séparément par site (prédictions concaténées)
 - per_site_lgb: modèle LightGBM entraîné séparément par site (si disponible)

Usage:
    python compare_models.py --csv donnees.csv --horizon 120 --output-dir results

Le script sauvegarde:
 - un CSV par stratégie avec les prédictions et la vérité (si disponible)
 - un fichier `metrics_summary.csv` contenant RMSE/MAE par stratégie
 - des graphiques dans le dossier de sortie

Notes:
 - Le script ne dépend pas de `seo_features` et construit des features simples (heure, jour, lags).
 - L'horizon est interprété comme un nombre de pas (comme dans `main.py`).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error

try:
    import lightgbm as lgb

    HAS_LGB = True
except Exception:
    HAS_LGB = False

import matplotlib.pyplot as plt
import seaborn as sns

TARGET_COL = "target_kwh"
SOURCE_CONS_COL = "consumption_kwh"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare model strategies on last 2 months")
    p.add_argument("--csv", default="donnees.csv", help="Source CSV path")
    p.add_argument("--horizon", type=int, default=120, help="Horizon in rows (shift)")
    p.add_argument("--holdout-months", type=int, default=2, help="Number of months for test set")
    p.add_argument("--output-dir", default="results", help="Directory to write outputs and charts")
    p.add_argument(
        "--max-sites",
        type=int,
        default=50,
        help="Max number of sites to train per-site models on (to limit runtime). 0 = all",
    )
    return p.parse_args(argv)


def load_and_sanitize(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # If CSV already contains both 'consumption_kw' and 'consumption_kwh',
    # drop the raw 'consumption_kw' column to avoid duplicates
    if "consumption_kw" in df.columns and SOURCE_CONS_COL in df.columns:
        df = df.drop(columns=["consumption_kw"], errors=True)

    # Normalize column names
    rename_map = {"timestamp": "measured_at", "consumption_kw": SOURCE_CONS_COL}
    df = df.rename(columns=rename_map)

    required = {"site_id", "measured_at", SOURCE_CONS_COL}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"Missing required columns: {missing}")
    df = df.copy()
    df["measured_at"] = pd.to_datetime(df["measured_at"], utc=True)
    df = df.sort_values(["site_id", "measured_at"]).reset_index(drop=True)
    df = df.dropna(subset=[SOURCE_CONS_COL])
    return df


def build_supervised_features(frame: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Créer features simples et colonne target (shift -horizon) par site.

    Features:
    - site_id (categorical)
    - hour, dayofweek
    - lag_1, lag_24 (si disponibles)
    - temperature_celsius, humidity_percent si présents
    """
    df = frame.copy()
    # basic time features
    df["hour"] = df["measured_at"].dt.hour
    df["dayofweek"] = df["measured_at"].dt.dayofweek

    # group-wise lags
    df["lag_1"] = df.groupby("site_id")[SOURCE_CONS_COL].shift(1)
    df["lag_24"] = df.groupby("site_id")[SOURCE_CONS_COL].shift(24)

    # target as shift -horizon (like main.py)
    df[TARGET_COL] = df.groupby("site_id")[SOURCE_CONS_COL].shift(-horizon)

    # drop rows missing essential features or target
    df = df.dropna(subset=[SOURCE_CONS_COL, TARGET_COL])

    return df.reset_index(drop=True)


def temporal_holdout(frame: pd.DataFrame, holdout_months: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    max_ts = frame["measured_at"].max()
    holdout_start = (pd.to_datetime(max_ts) - pd.DateOffset(months=holdout_months)).normalize()
    train_df = frame[frame["measured_at"] < holdout_start].copy()
    holdout_df = frame[frame["measured_at"] >= holdout_start].copy()
    if train_df.empty or holdout_df.empty:
        raise ValueError("Temporal split produced empty train or holdout set")
    return train_df.reset_index(drop=True), holdout_df.reset_index(drop=True)


def prepare_xy(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    x = frame.drop(columns=[TARGET_COL], errors="ignore")
    # drop timestamp and original consumption to avoid target leakage except lags
    x = x.drop(columns=["measured_at", SOURCE_CONS_COL], errors="ignore")
    # One-hot encode categorical columns (site_id, site_type) if present
    categorical_cols = [c for c in ["site_id", "site_type"] if c in x.columns]
    if categorical_cols:
        x = pd.get_dummies(x, columns=categorical_cols, drop_first=True)

    # Keep numeric columns only (drop remaining object columns) and fill na
    x = x.select_dtypes(include=[np.number]).fillna(0)
    y = frame[TARGET_COL]
    return x, y


def train_predict_global(
    model_name: str, train_df: pd.DataFrame, test_df: pd.DataFrame, model_params: dict
) -> tuple[pd.Series, dict]:
    x_train, y_train = prepare_xy(train_df)
    x_test, y_test = prepare_xy(test_df)
    if model_name == "rf":
        model = RandomForestRegressor(**model_params)
    elif model_name == "lgb":
        if not HAS_LGB:
            raise RuntimeError("LightGBM not installed")
        model = lgb.LGBMRegressor(**model_params)
    else:
        raise ValueError("Unknown model")
    model.fit(x_train, y_train)
    preds = model.predict(x_test)
    metrics = compute_metrics(y_test.to_numpy(), preds)
    return pd.Series(preds, index=test_df.index), metrics


def train_predict_per_site(
    model_name: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    model_params: dict,
    max_sites: int = 0,
) -> tuple[pd.Series, dict]:
    metrics_acc = {"rmse": [], "mae": [], "n": []}
    site_ids = sorted(test_df["site_id"].unique())
    if max_sites and max_sites > 0:
        site_ids = site_ids[:max_sites]
    # initialize pred series with NaN
    preds = pd.Series(index=test_df.index, dtype=float)

    for site in site_ids:
        train_site = train_df[train_df["site_id"] == site]
        test_site = test_df[test_df["site_id"] == site]
        if train_site.empty or test_site.empty:
            continue
        x_train, y_train = prepare_xy(train_site)
        x_test, y_test = prepare_xy(test_site)
        if model_name == "rf":
            model = RandomForestRegressor(**model_params)
        elif model_name == "lgb":
            if not HAS_LGB:
                raise RuntimeError("LightGBM not installed")
            model = lgb.LGBMRegressor(**model_params)
        else:
            raise ValueError("Unknown model")
        # If too few rows, skip
        if len(x_train) < 10:
            # skip small training sets
            continue
        model.fit(x_train, y_train)
        pred_vals = model.predict(x_test)
        preds.loc[test_site.index] = pred_vals
        m = compute_metrics(y_test.to_numpy(), pred_vals)
        metrics_acc["rmse"].append(m["rmse"])
        metrics_acc["mae"].append(m["mae"])
        metrics_acc["n"].append(len(y_test))

    # aggregate per-site metrics weighted by n
    if metrics_acc["n"]:
        total_n = sum(metrics_acc["n"])
        weighted_rmse = math.sqrt(
            sum(r * n * n for r, n in zip(metrics_acc["rmse"], metrics_acc["n"], strict=True))
            / (total_n * total_n)
        )
        # simpler weighted MAE
        weighted_mae = (
            sum(m * n for m, n in zip(metrics_acc["mae"], metrics_acc["n"], strict=True)) / total_n
        )
        metrics = {"rmse": weighted_rmse, "mae": weighted_mae}
    else:
        metrics = {"rmse": float("nan"), "mae": float("nan")}
    return preds, metrics


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mask = ~np.isnan(y_pred)
    if mask.sum() == 0:
        return {"rmse": float("nan"), "mae": float("nan")}
    y_true = y_true[mask]
    y_pred = y_pred[mask]
    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(y_true - y_pred)))
    return {"rmse": rmse, "mae": mae}


def plot_predictions(out_df: pd.DataFrame, output_dir: Path, strategy: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    # Scatter true vs pred
    if "y_true" not in out_df.columns:
        return
    plt.figure(figsize=(6, 6))
    sns.scatterplot(
        x="y_true", y="prediction", data=out_df.sample(min(len(out_df), 2000), random_state=42)
    )
    plt.plot(
        [out_df["y_true"].min(), out_df["y_true"].max()],
        [out_df["y_true"].min(), out_df["y_true"].max()],
        color="red",
        linestyle="--",
    )
    plt.xlabel("y_true")
    plt.ylabel("prediction")
    plt.title(f"True vs Pred - {strategy}")
    plt.tight_layout()
    plt.savefig(output_dir / f"{strategy}_scatter.png")
    plt.close()

    # Time series plot for a few sites
    sample_sites = out_df["site_id"].drop_duplicates().tolist()[:3]
    for site in sample_sites:
        df_site = out_df[out_df["site_id"] == site].sort_values("measured_at")
        if df_site.empty:
            continue
        plt.figure(figsize=(10, 3))
        plt.plot(df_site["measured_at"], df_site["y_true"], label="y_true")
        plt.plot(df_site["measured_at"], df_site["prediction"], label="prediction")
        plt.legend()
        plt.title(f"Time series - site {site} - {strategy}")
        plt.tight_layout()
        plt.savefig(output_dir / f"{strategy}_timeseries_site_{site}.png")
        plt.close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 2

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_and_sanitize(str(csv_path))
    supervised = build_supervised_features(df, args.horizon)

    train_df, holdout_df = temporal_holdout(supervised, args.holdout_months)

    strategies = []
    strategies.append(
        (
            "global_rf",
            lambda: train_predict_global(
                "rf", train_df, holdout_df, {"n_estimators": 150, "random_state": 42, "n_jobs": -1}
            ),
        )
    )
    if HAS_LGB:
        strategies.append(
            (
                "global_lgb",
                lambda: train_predict_global("lgb", train_df, holdout_df, {"n_estimators": 200}),
            )
        )
    strategies.append(
        (
            "per_site_rf",
            lambda: train_predict_per_site(
                "rf",
                train_df,
                holdout_df,
                {"n_estimators": 100, "random_state": 42},
                max_sites=args.max_sites,
            ),
        )
    )
    if HAS_LGB:
        strategies.append(
            (
                "per_site_lgb",
                lambda: train_predict_per_site(
                    "lgb", train_df, holdout_df, {"n_estimators": 200}, max_sites=args.max_sites
                ),
            )
        )

    metrics_records = []

    for name, func in strategies:
        print(f"Running strategy: {name}")
        try:
            preds_series, metrics = func()
        except Exception as exc:
            print(f"Strategy {name} failed: {exc}")
            metrics_records.append({"strategy": name, "rmse": None, "mae": None})
            continue
        out = holdout_df[["measured_at", "site_id"]].copy()
        out["prediction"] = preds_series.values
        out["y_true"] = holdout_df[TARGET_COL].values
        # Save predictions
        out_path = out_dir / f"predictions_{name}.csv"
        out.to_csv(out_path, index=False)
        print(f"Saved predictions to {out_path} (n={len(out)})")
        # compute metrics
        m = compute_metrics(out["y_true"].to_numpy(), out["prediction"].to_numpy())
        metrics_records.append({"strategy": name, "rmse": m["rmse"], "mae": m["mae"]})
        # plot
        plot_predictions(out, out_dir, name)

    # Save metrics summary
    metrics_df = pd.DataFrame(metrics_records)
    metrics_df.to_csv(out_dir / "metrics_summary.csv", index=False)
    print("Metrics summary saved to", out_dir / "metrics_summary.csv")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("Error:", exc, file=sys.stderr)
        raise
