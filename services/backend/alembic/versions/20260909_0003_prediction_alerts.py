"""allow forecast alerts raised by the prediction worker

Revision ID: 20260909_0003
Revises: 20260908_0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260909_0003"
down_revision: str | Sequence[str] | None = "20260908_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_alerts_type", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alerts_type",
        "alerts",
        "type IN ('spike', 'threshold', 'anomaly', 'outage', 'sensor', 'forecast')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM alerts WHERE type = 'forecast'")
    op.drop_constraint("ck_alerts_type", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alerts_type",
        "alerts",
        "type IN ('spike', 'threshold', 'anomaly', 'outage', 'sensor')",
    )
