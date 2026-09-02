"""Retire la migration de cloisonnement mono-site devenue obsolète.

This revision was released before the API contract adopted global viewer,
operator and admin roles.  It deliberately performs no data assignment: a
later migration introduces the contract schema and roles without inventing a
security-sensitive site association for existing accounts.
"""

from collections.abc import Sequence

revision: str = "20260902_0002"
down_revision: str | Sequence[str] | None = "20260901_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
