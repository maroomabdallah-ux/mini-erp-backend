"""Create sales orders and deliveries.

Revision ID: o9n8m7k6j5i4
Revises: n8m7k6j5i4h3
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "o9n8m7k6j5i4"
down_revision: str | None = "n8m7k6j5i4h3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_quotations_status", "quotations", type_="check")
    op.create_check_constraint(
        "ck_quotations_status",
        "quotations",
        "status IN ('draft','sent','accepted','rejected','expired','converted')",
    )
    op.add_column(
        "quotations", sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "sales_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Integer(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('draft','confirmed','delivered','cancelled')", name="ck_sales_orders_status"
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_sales_orders_total_nonnegative"),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("number", name="uq_sales_orders_number"),
        sa.UniqueConstraint("quotation_id", name="uq_sales_orders_quotation_id"),
    )
    for column in ("number", "quotation_id", "customer_id", "status"):
        op.create_index(f"ix_sales_orders_{column}", "sales_orders", [column])
    op.create_table(
        "sales_order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sales_order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_sales_order_items_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_sales_order_items_price_nonnegative"),
        sa.CheckConstraint("line_total >= 0", name="ck_sales_order_items_total_nonnegative"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("sales_order_id", "product_id", name="uq_sales_order_product"),
    )
    op.create_index("ix_sales_order_items_sales_order_id", "sales_order_items", ["sales_order_id"])
    op.create_index("ix_sales_order_items_product_id", "sales_order_items", ["product_id"])
    op.create_table(
        "sales_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("sales_order_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("delivered_by", sa.Integer(), nullable=False),
        sa.Column(
            "delivered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["delivered_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("number", name="uq_sales_deliveries_number"),
        sa.UniqueConstraint("sales_order_id", name="uq_sales_deliveries_order_id"),
    )
    for column in ("number", "sales_order_id", "warehouse_id", "delivered_at"):
        op.create_index(f"ix_sales_deliveries_{column}", "sales_deliveries", [column])
    op.create_table(
        "sales_delivery_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sales_delivery_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_sales_delivery_items_quantity_positive"),
        sa.ForeignKeyConstraint(["sales_delivery_id"], ["sales_deliveries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("sales_delivery_id", "product_id", name="uq_sales_delivery_product"),
    )
    op.create_index(
        "ix_sales_delivery_items_sales_delivery_id", "sales_delivery_items", ["sales_delivery_id"]
    )
    op.create_index("ix_sales_delivery_items_product_id", "sales_delivery_items", ["product_id"])


def downgrade() -> None:
    op.drop_table("sales_delivery_items")
    op.drop_table("sales_deliveries")
    op.drop_table("sales_order_items")
    op.drop_table("sales_orders")
    op.drop_column("quotations", "converted_at")
    op.drop_constraint("ck_quotations_status", "quotations", type_="check")
    op.create_check_constraint(
        "ck_quotations_status",
        "quotations",
        "status IN ('draft','sent','accepted','rejected','expired')",
    )
