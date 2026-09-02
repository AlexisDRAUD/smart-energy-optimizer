"""Associate each user with one site and remove role-based access."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260902_0002"
down_revision: Union[str, Sequence[str], None] = "20260901_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    user_site_codes = {
        "camille.admin": "LYO-01",
        "lucas.operator": "GRE-01",
        "ines.analyst": "NAN-01",
        "marc.viewer": "LYO-01",
    }
    usernames = set(connection.execute(sa.text("SELECT username FROM users")).scalars())
    unmapped_usernames = sorted(usernames.difference(user_site_codes))
    if unmapped_usernames:
        raise RuntimeError(
            "Cannot determine site assignments for users: " + ", ".join(unmapped_usernames)
        )

    required_site_codes = {user_site_codes[username] for username in usernames}
    site_ids = dict(
        connection.execute(
            sa.text("SELECT code, id FROM sites WHERE code IN :site_codes").bindparams(
                sa.bindparam("site_codes", expanding=True)
            ),
            {"site_codes": list(required_site_codes)},
        ).all()
    )
    missing_site_codes = sorted(required_site_codes.difference(site_ids))
    if missing_site_codes:
        raise RuntimeError(
            "Cannot determine site assignments because sites are missing: " + ", ".join(missing_site_codes)
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("site_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_site_id_sites",
            "sites",
            ["site_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    for username, site_code in user_site_codes.items():
        if username in usernames:
            connection.execute(
                sa.text("UPDATE users SET site_id = :site_id WHERE username = :username"),
                {"site_id": site_ids[site_code], "username": username},
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
