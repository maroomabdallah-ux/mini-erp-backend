"""Add purchase-order result to Agent pending actions.

Revision ID: y9x8w7v6u5t4
Revises: x8w7v6u5t4s3
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "y9x8w7v6u5t4"
down_revision: str | None = "x8w7v6u5t4s3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_pending_actions",
        sa.Column(
            "purchase_order_id",
            sa.Integer(),
            sa.ForeignKey("purchase_orders.id", ondelete="SET NULL"),
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_pending_actions", "purchase_order_id")
