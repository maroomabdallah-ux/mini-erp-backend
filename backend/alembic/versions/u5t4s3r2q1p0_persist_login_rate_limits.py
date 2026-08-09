"""Persist login rate limits.

Revision ID: u5t4s3r2q1p0
Revises: t4s3r2q1p0o9
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "u5t4s3r2q1p0"
down_revision: str | None = "t4s3r2q1p0o9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_login_attempts_ip_address", "login_attempts", ["ip_address"])
    op.create_index("ix_login_attempts_attempted_at", "login_attempts", ["attempted_at"])


def downgrade() -> None:
    op.drop_table("login_attempts")
