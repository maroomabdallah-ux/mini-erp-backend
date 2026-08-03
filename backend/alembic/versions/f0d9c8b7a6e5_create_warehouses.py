"""create warehouses

Revision ID: f0d9c8b7a6e5
Revises: e9c8b7a6d5f4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f0d9c8b7a6e5"
down_revision: str | Sequence[str] | None = "e9c8b7a6d5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("code", name="uq_warehouses_code"),
    )
    op.create_index("ix_warehouses_code", "warehouses", ["code"])
    op.create_index("ix_warehouses_name", "warehouses", ["name"])


def downgrade() -> None:
    op.drop_table("warehouses")
