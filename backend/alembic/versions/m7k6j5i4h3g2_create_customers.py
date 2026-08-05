"""Create customers.

Revision ID: m7k6j5i4h3g2
Revises: l6j5i4h3g2f1
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7k6j5i4h3g2"
down_revision: str | None = "l6j5i4h3g2f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("contact_person", sa.String(150), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("tax_number", sa.String(100), nullable=True),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("credit_limit >= 0", name="ck_customers_credit_limit_nonnegative"),
        sa.UniqueConstraint("code", name="uq_customers_code"),
    )
    for column in ("code", "name", "email", "phone", "city", "tax_number"):
        op.create_index(f"ix_customers_{column}", "customers", [column])


def downgrade() -> None:
    op.drop_table("customers")
