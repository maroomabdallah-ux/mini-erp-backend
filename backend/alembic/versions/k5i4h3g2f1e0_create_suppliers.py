"""create suppliers

Revision ID: k5i4h3g2f1e0
Revises: j4h3g2f1e0d9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "k5i4h3g2f1e0"
down_revision: str | None = "j4h3g2f1e0d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("credit_terms", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_suppliers_name"), "suppliers", ["name"], unique=False)
    op.create_index(op.f("ix_suppliers_email"), "suppliers", ["email"], unique=False)
    op.create_index(op.f("ix_suppliers_phone"), "suppliers", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_suppliers_phone"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_email"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_name"), table_name="suppliers")
    op.drop_table("suppliers")
