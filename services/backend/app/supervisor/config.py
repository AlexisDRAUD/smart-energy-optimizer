"""Reglages du superviseur, lus dans l environnement sous le prefixe SUPERVISOR_.

Separes de app.config.Settings : ces reglages n interessent que ce processus,
et les valeurs par defaut sont les decisions du lot (voir docs/ml-supervision.md),
pas des reglages techniques. Le superviseur prend en plus a app.config ce qu il
partage avec le reste du backend : la base, MLflow et le prefixe des modeles.

Les durees sont saisies dans l unite ou on les pense (heures, jours) et
exposees en timedelta, pretes a passer au moniteur et a l ordonnanceur. Les
valeurs par defaut sont des valeurs de depart, a calibrer sur des donnees
reelles.
"""

from datetime import timedelta

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SupervisorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SUPERVISOR_",
        env_file=(".env", "../../.env"),
        extra="ignore",
    )

    # Temps de sommeil entre deux tours. Les fenetres se comptent en jours, un
    # tour toutes les cinq minutes suffit largement.
    interval_seconds: int = Field(default=300, gt=0)
    # Fenetre de decision : la MAE qui juge la derive.
    decision_window_hours: int = Field(default=168, gt=0)
    # Fenetre d alerte : la MAE qui previent, sans decider.
    alert_window_hours: int = Field(default=24, gt=0)
    # Delai de grace : donnees exigees depuis la premiere notation avant verdict.
    grace_hours: int = Field(default=24, gt=0)
    # Verrou : jamais deux lancements pour un site a moins de cet ecart.
    lock_hours: int = Field(default=24, gt=0)
    # Filet : age au-dela duquel on reentraine meme sans derive.
    max_model_age_days: int = Field(default=7, gt=0)
    # Seuil de repli = MAE holdout x tolerance, quand le run n a pas de
    # drift_threshold_mae.
    mae_tolerance: float = Field(default=1.5, gt=0)

    @property
    def decision_window(self) -> timedelta:
        return timedelta(hours=self.decision_window_hours)

    @property
    def alert_window(self) -> timedelta:
        return timedelta(hours=self.alert_window_hours)

    @property
    def grace(self) -> timedelta:
        return timedelta(hours=self.grace_hours)

    @property
    def lock(self) -> timedelta:
        return timedelta(hours=self.lock_hours)

    @property
    def max_model_age(self) -> timedelta:
        return timedelta(days=self.max_model_age_days)
