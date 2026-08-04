"""normalize inventory count reference uniqueness

Revision ID: i3g2f1e0d9c8
Revises: h2f1e0d9c8b7
"""

from collections.abc import Sequence

from alembic import op

revision: str = "i3g2f1e0d9c8"
down_revision: str | Sequence[str] | None = "h2f1e0d9c8b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "inventory_counts_reference_key", "inventory_counts", type_="unique"
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "inventory_counts_reference_key", "inventory_counts", ["reference"]
    )
