"""Create sales quotations.

Revision ID: n8m7k6j5i4h3
Revises: m7k6j5i4h3g2
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "n8m7k6j5i4h3"
down_revision: str | None = "m7k6j5i4h3g2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('draft','sent','accepted','rejected','expired')",
            name="ck_quotations_status",
        ),
        sa.CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_quotations_discount_percent",
        ),
        sa.CheckConstraint(
            "tax_percent >= 0 AND tax_percent <= 100", name="ck_quotations_tax_percent"
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_quotations_total_nonnegative"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("number", name="uq_quotations_number"),
    )
    for column in ("number", "customer_id", "status", "valid_until"):
        op.create_index(f"ix_quotations_{column}", "quotations", [column])
    op.create_table(
        "quotation_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_quotation_items_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_quotation_items_price_nonnegative"),
        sa.CheckConstraint("line_total >= 0", name="ck_quotation_items_total_nonnegative"),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("quotation_id", "product_id", name="uq_quotation_product"),
    )
    op.create_index("ix_quotation_items_quotation_id", "quotation_items", ["quotation_id"])
    op.create_index("ix_quotation_items_product_id", "quotation_items", ["product_id"])


def downgrade() -> None:
    op.drop_table("quotation_items")
    op.drop_table("quotations")
