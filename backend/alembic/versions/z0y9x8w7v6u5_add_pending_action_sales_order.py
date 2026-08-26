"""Add sales-order result to Agent pending actions.

Revision ID: z0y9x8w7v6u5
Revises: y9x8w7v6u5t4
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "z0y9x8w7v6u5"
down_revision: str | None = "y9x8w7v6u5t4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_pending_actions",
        sa.Column(
            "sales_order_id",
            sa.Integer(),
            sa.ForeignKey("sales_orders.id", ondelete="SET NULL"),
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_pending_actions", "sales_order_id")
