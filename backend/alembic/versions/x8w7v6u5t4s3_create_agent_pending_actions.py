"""Create controlled Agent pending actions.

Revision ID: x8w7v6u5t4s3
Revises: w7v6u5t4s3r2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "x8w7v6u5t4s3"
down_revision: str | None = "w7v6u5t4s3r2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_pending_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "quotation_id",
            sa.Integer(),
            sa.ForeignKey("quotations.id", ondelete="SET NULL"),
        ),
        sa.Column("failure_category", sa.String(100)),
        sa.CheckConstraint(
            "status IN ('pending', 'executed', 'expired', 'cancelled', 'failed')",
            name="ck_agent_pending_actions_status",
        ),
    )
    op.create_index("ix_agent_pending_actions_user_id", "agent_pending_actions", ["user_id"])
    op.create_index(
        "ix_agent_pending_actions_conversation_id",
        "agent_pending_actions",
        ["conversation_id"],
    )
    op.create_index(
        "ix_agent_pending_actions_action_type", "agent_pending_actions", ["action_type"]
    )
    op.create_index("ix_agent_pending_actions_status", "agent_pending_actions", ["status"])
    op.create_index(
        "ix_agent_pending_actions_expires_at", "agent_pending_actions", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_table("agent_pending_actions")
