"""Calcul des variables d'entree du modele.

Importe par services/ml (entrainement) ET par services/api (service).
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
    raise NotImplementedError


def add_lag_features(df: pd.DataFrame, value_col: str = "consumption_kwh") -> pd.DataFrame:
    """Ajoute les valeurs recentes et les agregats glissants."""
    raise NotImplementedError


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Point d'entree unique : rend le tableau de variables pret pour le modele."""
    raise NotImplementedError
