"""collect and expose source alerts

Revision ID: 20260908_0002
Revises: 20260907_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0002"
down_revision: str | Sequence[str] | None = "20260907_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_raw_snapshots_source", "raw_snapshots", type_="check")
    op.create_check_constraint(
        "ck_raw_snapshots_source",
        "raw_snapshots",
        "source IN ('api_sites', 'api_sensors', 'api_alerts')",
    )
    op.add_column(
        "alerts",
        sa.Column("origin", sa.String(), nullable=False, server_default="internal"),
    )
    op.create_check_constraint("ck_alerts_origin", "alerts", "origin IN ('internal', 'source')")


def downgrade() -> None:
    op.drop_constraint("ck_alerts_origin", "alerts", type_="check")
    op.drop_column("alerts", "origin")
    op.drop_constraint("ck_raw_snapshots_source", "raw_snapshots", type_="check")
    op.create_check_constraint(
        "ck_raw_snapshots_source",
        "raw_snapshots",
        "source IN ('api_sites', 'api_sensors')",
    )
