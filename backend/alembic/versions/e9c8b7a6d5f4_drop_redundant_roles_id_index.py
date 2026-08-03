"""drop redundant roles primary-key index

Revision ID: e9c8b7a6d5f4
Revises: d8b7e6a5f4c3
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e9c8b7a6d5f4"
down_revision: str | Sequence[str] | None = "d8b7e6a5f4c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_roles_id", table_name="roles")


def downgrade() -> None:
    op.create_index("ix_roles_id", "roles", ["id"])
