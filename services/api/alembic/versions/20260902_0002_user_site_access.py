"""Associate each user with one site and remove role-based access."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260902_0002"
down_revision: Union[str, Sequence[str], None] = "20260901_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("site_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_site_id_sites",
            "sites",
            ["site_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.execute(
        """
        UPDATE users
        SET site_id = (SELECT id FROM sites ORDER BY id LIMIT 1)
        WHERE site_id IS NULL
        """
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("site_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_index("ix_users_site_id", ["site_id"])

    op.drop_table("user_roles")
    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_table("roles")


def downgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=False)
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_site_id")
        batch_op.drop_constraint("fk_users_site_id_sites", type_="foreignkey")
        batch_op.drop_column("site_id")
