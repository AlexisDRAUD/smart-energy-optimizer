"""colonnes derivees et unicite sur raw_readings

Revision ID: 4649d1d8fc01
Revises: 4cf9c5955926
Create Date: 2026-09-04 12:00:38.046661

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4649d1d8fc01"
down_revision: str | Sequence[str] | None = "4cf9c5955926"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Colonnes derivees du payload (brut intact) + unicite (site, instant).

    Validees par le formateur le 04/09 : le JSON reste intact, les colonnes
    sont calculees par PostgreSQL a partir du payload, jamais par le code.
    measured_at est copie tel quel (texte) : aucune conversion a l'etage 1,
    c'est l'ETL qui interprete.
    """
    op.add_column(
        "raw_readings",
        sa.Column(
            "site_id",
            sa.Text(),
            sa.Computed("(payload->>'site_id')", persisted=True),
        ),
    )
    op.add_column(
        "raw_readings",
        sa.Column(
            "measured_at",
            sa.Text(),
            sa.Computed("(payload->>'timestamp')", persisted=True),
        ),
    )
    op.create_index(
        "ux_raw_readings_site_measured",
        "raw_readings",
        ["site_id", "measured_at"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_raw_readings_site_measured", table_name="raw_readings")
    op.drop_column("raw_readings", "measured_at")
    op.drop_column("raw_readings", "site_id")
