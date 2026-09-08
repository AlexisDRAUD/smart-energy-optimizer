#!/usr/bin/env python3
"""Tester un modèle sur les 2 derniers mois du CSV et sauvegarder les prédictions.

Usage exemple:
    python test_last_2_months.py --csv donnees.csv \
        --model-dir mlruns/1/models/m-cb4e44f2e3fe494fa77db70cc136a1c3/artifacts \
        --output predictions_last_2_months.csv

Le script réutilise des fonctions de `main.py` pour la sanitation et la création du frame.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mlflow
import pandas as pd

# Importer des utilitaires existants dans main.py
from main import (
    TARGET_COLUMN,
    build_supervised_frame,
    load_csv,
    split_features_target,
)
from sklearn.metrics import mean_squared_error


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test model on last 2 months of CSV")
    parser.add_argument("--csv", default="donnees.csv", help="Path to source CSV")
    parser.add_argument(
        "--model-dir",
        default=("mlruns/1/models/m-cb4e44f2e3fe494fa77db70cc136a1c3/artifacts"),
        help="Path to trained model directory (folder that contains MLmodel and model.skops)",
    )
    parser.add_argument(
        "--horizon-minutes",
        type=int,
        default=120,
        help="Horizon used when building supervised frame",
    )
    parser.add_argument(
        "--output", default="predictions_last_2_months.csv", help="Output CSV for predictions"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 2

    # Charger et préparer les données
    source = load_csv(str(csv_path))
    supervised = build_supervised_frame(source, args.horizon_minutes)

    if supervised.empty:
        print("Aucune ligne supervisée générée (frame vide)")
        return 3

    # Filtrer sur les 2 derniers mois
    max_ts = supervised["measured_at"].max()
    start_2m = (pd.to_datetime(max_ts) - pd.DateOffset(months=2)).normalize()
    last_2m = supervised[supervised["measured_at"] >= start_2m].copy()

    if last_2m.empty:
        print("Aucune donnée pour les 2 derniers mois.")
        return 4

    # Séparer features / target
    x, y = split_features_target(last_2m)

    # Charger le modèle
    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        print(f"Model directory not found: {model_dir}", file=sys.stderr)
        return 5

    try:
        # mlflow accepts local path; if that fails, prefix with "file://"
        model = mlflow.sklearn.load_model(str(model_dir))
    except Exception:
        model = mlflow.sklearn.load_model(f"file://{model_dir}")

    # Faire les prédictions
    preds = model.predict(x)

    # Préparer le DataFrame de sortie
    out = last_2m[["measured_at", "site_id"]].reset_index(drop=True)
    out["prediction"] = preds

    if TARGET_COLUMN in last_2m.columns:
        out["y_true"] = last_2m[TARGET_COLUMN].values

    out.to_csv(args.output, index=False)
    print(f"Predictions saved to {args.output} (n={len(out)})")

    # Si y_true présent, afficher métriques rapides
    if "y_true" in out.columns:
        mse = mean_squared_error(out["y_true"], out["prediction"])
        rmse = float(mse**0.5)
        mae = float((out["y_true"] - out["prediction"]).abs().mean())
        print(f"RMSE: {rmse:.3f}, MAE: {mae:.3f}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("Error:", exc, file=sys.stderr)
        raise
