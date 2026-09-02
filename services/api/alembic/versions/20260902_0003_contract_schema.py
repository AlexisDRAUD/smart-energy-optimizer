"""Adopt the API data-contract schema.

The preceding revisions define the unreleased legacy schema.  Its tables are
replaced only when they are empty: data-bearing databases require an explicit
business migration so no site or user relationship is guessed or discarded.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.db.base import Base
import app.models  # noqa: F401


revision: str = "20260902_0003"
down_revision: Union[str, Sequence[str], None] = "20260902_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_TABLES = ("user_roles", "alerts", "readings", "users", "roles", "sites")


def upgrade() -> None:
    connection = op.get_bind()
    table_names = set(sa.inspect(connection).get_table_names())
    populated_tables = [
        table_name
        for table_name in LEGACY_TABLES
        if table_name in table_names
        and connection.execute(sa.text(f"SELECT 1 FROM {table_name} LIMIT 1")).first() is not None
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
