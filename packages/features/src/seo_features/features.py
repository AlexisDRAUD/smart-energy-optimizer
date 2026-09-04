"""Calcul des variables d'entree du modele.

Importe par services/ml (entrainement) ET par services/backend (service).
Ne jamais dupliquer une de ces formules ailleurs : l'entrainement et le service
calculeraient la meme variable de deux facons, le modele se degraderait en production
sans qu'aucun test n'echoue.

Les variables de calendrier sont recalculees ici depuis l'horodatage, elles ne sont
pas stockees en base.
"""

from __future__ import annotations

import pandas as pd


def add_calendar_features(df: pd.DataFrame, ts_col: str = "measured_at") -> pd.DataFrame:
    """Ajoute heure, jour de la semaine, mois, week-end et heures ouvrees."""
    if ts_col not in df.columns:
        raise KeyError(f"Timestamp column '{ts_col}' missing")

    out = df.copy()
    out[ts_col] = pd.to_datetime(out[ts_col], utc=True)
    out["hour"] = out[ts_col].dt.hour
    out["day_of_week"] = out[ts_col].dt.dayofweek
    out["month"] = out[ts_col].dt.month
    out["is_weekend"] = out["day_of_week"].isin([5, 6]).astype(int)
    out["is_working_hours"] = (
        (out["hour"] >= 8) & (out["hour"] <= 18) & (out["is_weekend"] == 0)
    ).astype(int)
    return out


def add_lag_features(df: pd.DataFrame, value_col: str = "consumption_kwh") -> pd.DataFrame:
    """Ajoute les valeurs recentes et les agregats glissants."""
    if value_col not in df.columns:
        raise KeyError(f"Value column '{value_col}' missing")

    out = df.copy()
    group_cols = ["site_id"] if "site_id" in out.columns else None

    if group_cols is None:
        shifted_1 = out[value_col].shift(1)
        shifted_60 = out[value_col].shift(60)
        shifted_120 = out[value_col].shift(120)
        rolling_30 = out[value_col].shift(1).rolling(window=30, min_periods=1).mean()
        rolling_120 = out[value_col].shift(1).rolling(window=120, min_periods=1).mean()
    else:
        shifted_1 = out.groupby(group_cols)[value_col].shift(1)
        shifted_60 = out.groupby(group_cols)[value_col].shift(60)
        shifted_120 = out.groupby(group_cols)[value_col].shift(120)
        rolling_30 = (
            out.groupby(group_cols)[value_col]
            .shift(1)
            .rolling(window=30, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )
        rolling_120 = (
            out.groupby(group_cols)[value_col]
            .shift(1)
            .rolling(window=120, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )

    out["lag_1"] = shifted_1
    out["lag_60"] = shifted_60
    out["lag_120"] = shifted_120
    out["rolling_mean_30"] = rolling_30
    out["rolling_mean_120"] = rolling_120

    fill_value = out[value_col]
    out["lag_1"] = out["lag_1"].fillna(fill_value)
    out["lag_60"] = out["lag_60"].fillna(out["lag_1"])
    out["lag_120"] = out["lag_120"].fillna(out["lag_60"])
    out["rolling_mean_30"] = out["rolling_mean_30"].fillna(out["lag_1"])
    out["rolling_mean_120"] = out["rolling_mean_120"].fillna(out["lag_60"])
    return out


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Point d'entree unique : rend le tableau de variables pret pour le modele."""
    required = {"measured_at", "consumption_kwh"}
    missing = required.difference(df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise KeyError(f"Missing required columns: {missing_cols}")

    sort_cols = ["measured_at"]
    if "site_id" in df.columns:
        sort_cols = ["site_id", "measured_at"]

    out = df.sort_values(sort_cols).reset_index(drop=True)
    out = add_calendar_features(out, ts_col="measured_at")
    out = add_lag_features(out, value_col="consumption_kwh")
    return out
