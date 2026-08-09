"""Add customer payment allocations.

Revision ID: t4s3r2q1p0o9
Revises: s3r2q1p0o9n8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "t4s3r2q1p0o9"
down_revision: str | None = "s3r2q1p0o9n8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("customer_id", sa.Integer()))
    op.execute(
        "UPDATE payments p SET customer_id = i.customer_id FROM invoices i "
        "WHERE i.id = p.invoice_id"
    )
    op.alter_column("payments", "customer_id", nullable=False)
    op.alter_column("payments", "invoice_id", nullable=True)
    op.create_foreign_key(
        "fk_payments_customer_id", "payments", "customers", ["customer_id"], ["id"],
        ondelete="RESTRICT"
    )
    op.create_index("ix_payments_customer_id", "payments", ["customer_id"])
    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("allocated_amount > 0", name="ck_payment_allocations_positive"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("payment_id", "invoice_id", name="uq_payment_allocation_invoice"),
    )
    op.create_index("ix_payment_allocations_payment_id", "payment_allocations", ["payment_id"])
    op.create_index("ix_payment_allocations_invoice_id", "payment_allocations", ["invoice_id"])
    op.execute(
        "INSERT INTO payment_allocations (payment_id, invoice_id, allocated_amount) "
        "SELECT id, invoice_id, amount FROM payments WHERE invoice_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM payments WHERE invoice_id IS NULL"
    )
    op.drop_table("payment_allocations")
    op.drop_index("ix_payments_customer_id", table_name="payments")
    op.drop_constraint("fk_payments_customer_id", "payments", type_="foreignkey")
    op.alter_column("payments", "invoice_id", nullable=False)
    op.drop_column("payments", "customer_id")
