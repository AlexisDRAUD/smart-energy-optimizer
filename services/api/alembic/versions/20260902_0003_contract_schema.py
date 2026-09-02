"""Adopt the API data-contract schema.

The preceding revisions define the unreleased legacy schema.  Its tables are
replaced only when they are empty: data-bearing databases require an explicit
business migration so no site or user relationship is guessed or discarded.
"""

from collections.abc import Sequence

import app.models  # noqa: F401
import sqlalchemy as sa
from alembic import op
from app.db.base import Base

revision: str = "20260902_0003"
down_revision: str | Sequence[str] | None = "20260902_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_TABLES = ("user_roles", "alerts", "readings", "users", "roles", "sites")


def upgrade() -> None:
    connection = op.get_bind()
    table_names = set(sa.inspect(connection).get_table_names())
    populated_tables = [
        table_name
        for table_name in LEGACY_TABLES
        if table_name in table_names
        and connection.execute(
            sa.select(sa.literal(1)).select_from(sa.table(table_name)).limit(1)
        ).first()
        is not None
    ]
    if populated_tables:
        raise RuntimeError(
            "Cannot replace a populated legacy schema. Create an explicit data migration for: "
            + ", ".join(populated_tables)
        )

    for table_name in LEGACY_TABLES:
        if table_name in table_names:
            op.drop_table(table_name)

    Base.metadata.create_all(connection)


def downgrade() -> None:
    raise RuntimeError("The contract-schema migration cannot be downgraded automatically.")
