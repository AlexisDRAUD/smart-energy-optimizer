"""schema initial du contrat de donnees

Revision ID: 20260907_0001
Revises:
Create Date: 2026-09-07

Migration unique : le projet n a jamais ete deploye, il n y a donc pas
d historique a rejouer. Elle cree le schema des trois etages du contrat de
donnees en un seul passage, dans l ordre du flux.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260907_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cree le schema complet."""
    _create_stage_1_raw()
    _create_stage_2_transformed()
    _create_stage_3_application()


def _create_stage_1_raw() -> None:
    """Le brut, tel que la source l a envoye. Aucune interpretation ici."""
    op.create_table(
        "raw_readings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        # Calculees par PostgreSQL depuis le payload, jamais par le code.
        # measured_at reste du texte : aucune interpretation a l etage 1,
        # c est l ETL qui convertit.
        sa.Column(
            "site_id",
            sa.Text(),
            sa.Computed("(payload->>'site_id')", persisted=True),
        ),
        sa.Column(
            "measured_at",
            sa.Text(),
            sa.Computed("(payload->>'timestamp')", persisted=True),
        ),
        sa.CheckConstraint(
            "source IN ('api_current', 'api_backfill', 'csv_import')",
            name="ck_raw_readings_source",
        ),
    )
    # Une mesure par site et par instant. C est cette cle qui rend le collecteur
    # et la reprise d historique rejouables sans creer de doublon.
    #
    # La table n est pas partitionnee : PostgreSQL exige qu une cle unique
    # contienne la colonne de partitionnement. Partitionner sur received_at
    # obligerait a l ajouter a la cle, et deux appels du collecteur a deux
    # secondes d ecart creeraient deux lignes pour la meme mesure. Partitionner
    # sur measured_at est refuse, c est une colonne calculee.
    op.create_index(
        "ux_raw_readings_site_measured",
        "raw_readings",
        ["site_id", "measured_at"],
        unique=True,
    )
    # L ETL avance par fenetre de reception : il relit les lignes arrivees depuis
    # la borne de son dernier passage reussi. Rien n est ecrit sur le brut pour
    # suivre ce qui a ete traite, la table reste en insertion seule.
    op.create_index("ix_raw_readings_received_at", "raw_readings", ["received_at"])

    op.create_table(
        "raw_snapshots",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "source IN ('api_sites', 'api_sensors')",
            name="ck_raw_snapshots_source",
        ),
    )
    # L ETL relit le dernier referentiel de sites, et tous les instantanes de
    # capteurs de sa fenetre, a chaque passage. Sans cet index, la table entiere
    # serait parcourue a chaque fois.
    op.create_index(
        "ix_raw_snapshots_source_received_at",
        "raw_snapshots",
        ["source", "received_at"],
    )


def _create_stage_2_transformed() -> None:
    """Le transforme, ecrit par l ETL depuis le brut."""
    op.create_table(
        "sites",
        sa.Column("site_id", sa.String(), nullable=False),
        sa.Column("site_type", sa.String(), nullable=False),
        sa.Column("site_name", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("capacity_kw", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        # Profil d imputation, decide par la comparaison des methodes et
        # recalcule periodiquement par l ETL. Il choisit la methode de
        # reparation : interpolation pour un site variable, report pour un site
        # stable, aucune reparation tant qu il vaut unknown ou NULL. C est ce
        # qui protege un site dont les donnees se degradent, sans coder aucun
        # identifiant en dur.
        sa.Column("imputation_profile", sa.String(), nullable=True),
        sa.Column("imputation_profile_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_sites_status"),
        sa.CheckConstraint(
            "imputation_profile IS NULL OR imputation_profile IN ('variable', 'stable', 'unknown')",
            name="ck_sites_imputation_profile",
        ),
        sa.PrimaryKeyConstraint("site_id"),
    )

    op.create_table(
        "readings",
        sa.Column("site_id", sa.String(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumption_kwh", sa.Float(), nullable=True),
        sa.Column("consumption_kwh_raw", sa.Float(), nullable=True),
        sa.Column("is_imputed", sa.Boolean(), nullable=False),
        sa.Column("imputation_method", sa.String(), nullable=True),
        sa.Column("temperature_celsius", sa.Float(), nullable=True),
        sa.Column("humidity_percent", sa.Float(), nullable=True),
        sa.Column("data_quality", sa.String(), nullable=False),
        sa.Column("null_reasons", sa.ARRAY(sa.String()), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "data_quality IN ('good', 'partial', 'degraded', 'critical')",
            name="ck_readings_data_quality",
        ),
        sa.PrimaryKeyConstraint("site_id", "measured_at"),
        sa.UniqueConstraint("site_id", "measured_at", name="uq_readings_site_measured"),
    )
    op.create_index(op.f("ix_readings_measured_at"), "readings", ["measured_at"], unique=False)
    op.create_index(op.f("ix_readings_site_id"), "readings", ["site_id"], unique=False)

    op.create_table(
        "sensor_status",
        sa.Column("site_id", sa.String(), nullable=False),
        sa.Column("sensor", sa.String(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("failing_until", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "sensor IN ('consumption', 'electrical', 'temperature', 'humidity', 'network')",
            name="ck_sensor_status_sensor",
        ),
        sa.CheckConstraint("status IN ('ok', 'failing')", name="ck_sensor_status_status"),
        sa.PrimaryKeyConstraint("site_id", "sensor", "observed_at"),
        sa.UniqueConstraint(
            "site_id", "sensor", "observed_at", name="uq_sensor_status_site_sensor_observed"
        ),
    )

    op.create_table(
        "data_quality_daily",
        sa.Column("site_id", sa.String(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("expected_points", sa.Integer(), nullable=False),
        sa.Column("received_points", sa.Integer(), nullable=False),
        sa.Column("missing_points", sa.Integer(), nullable=False),
        sa.Column("null_points", sa.Integer(), nullable=False),
        sa.Column("imputed_points", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("site_id", "day"),
        sa.UniqueConstraint("site_id", "day", name="uq_data_quality_daily_site_day"),
    )

    op.create_table(
        "etl_runs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rows_read", sa.Integer(), nullable=False),
        sa.Column("rows_written", sa.Integer(), nullable=False),
        sa.Column("rows_imputed", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'ok', 'partial', 'failed')", name="ck_etl_runs_status"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_stage_3_application() -> None:
    """Les tables ecrites par l API : comptes, predictions, alertes."""
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('viewer', 'operator', 'admin')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("site_id", sa.String(), nullable=False),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("predicted_kwh", sa.Float(), nullable=False),
        sa.Column("actual_kwh", sa.Float(), nullable=True),
        sa.Column(
            "absolute_error",
            sa.Float(),
            sa.Computed(
                "CASE WHEN actual_kwh IS NULL THEN NULL ELSE abs(predicted_kwh - actual_kwh) END",
            ),
            nullable=True,
        ),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "site_id",
            "target_at",
            "model_version",
            "horizon_minutes",
            name="uq_predictions_site_target_model_horizon",
        ),
    )
    op.create_index(op.f("ix_predictions_site_id"), "predictions", ["site_id"], unique=False)
    op.create_index(op.f("ix_predictions_target_at"), "predictions", ["target_at"], unique=False)

    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("site_id", sa.String(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("threshold_value", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')", name="ck_alerts_severity"
        ),
        sa.CheckConstraint("status IN ('open', 'acknowledged', 'closed')", name="ck_alerts_status"),
        sa.CheckConstraint(
            "type IN ('spike', 'threshold', 'anomaly', 'outage', 'sensor')", name="ck_alerts_type"
        ),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "type", "detected_at", name="uq_alerts_site_type_detected"),
    )
    op.create_index(op.f("ix_alerts_detected_at"), "alerts", ["detected_at"], unique=False)
    op.create_index(op.f("ix_alerts_site_id"), "alerts", ["site_id"], unique=False)


def downgrade() -> None:
    """Supprime le schema complet, dans l ordre inverse des dependances."""
    op.drop_table("alerts")
    op.drop_table("predictions")
    op.drop_table("users")
    op.drop_table("etl_runs")
    op.drop_table("data_quality_daily")
    op.drop_table("sensor_status")
    op.drop_table("readings")
    op.drop_table("sites")
    op.drop_table("raw_snapshots")
    op.drop_table("raw_readings")
