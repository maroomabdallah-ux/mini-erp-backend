"""Create purchase orders and goods receipts.

Revision ID: l6j5i4h3g2f1
Revises: k5i4h3g2f1e0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "l6j5i4h3g2f1"
down_revision: str | None = "k5i4h3g2f1e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(length=30), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by", sa.Integer(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("cancelled_by", sa.Integer(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', 'rejected', 'cancelled', 'received')",
            name="ck_purchase_orders_status",
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_purchase_orders_total_nonnegative"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("number", name="uq_purchase_orders_number"),
    )
    op.create_index("ix_purchase_orders_number", "purchase_orders", ["number"])
    op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"])
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"])

    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_order_items_quantity_positive"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_purchase_order_items_cost_nonnegative"),
        sa.CheckConstraint("line_total >= 0", name="ck_purchase_order_items_total_nonnegative"),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"], ["purchase_orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "purchase_order_id", "product_id", name="uq_purchase_order_product"
        ),
    )
    op.create_index(
        "ix_purchase_order_items_purchase_order_id",
        "purchase_order_items",
        ["purchase_order_id"],
    )
    op.create_index("ix_purchase_order_items_product_id", "purchase_order_items", ["product_id"])

    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(length=30), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("received_by", sa.Integer(), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"], ["purchase_orders.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("number", name="uq_goods_receipts_number"),
        sa.UniqueConstraint("purchase_order_id", name="uq_goods_receipts_purchase_order_id"),
    )
    op.create_index("ix_goods_receipts_number", "goods_receipts", ["number"])
    op.create_index("ix_goods_receipts_purchase_order_id", "goods_receipts", ["purchase_order_id"])
    op.create_index("ix_goods_receipts_warehouse_id", "goods_receipts", ["warehouse_id"])
    op.create_index("ix_goods_receipts_received_at", "goods_receipts", ["received_at"])

    op.create_table(
        "goods_receipt_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goods_receipt_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_goods_receipt_items_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["goods_receipt_id"], ["goods_receipts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("goods_receipt_id", "product_id", name="uq_goods_receipt_product"),
    )
    op.create_index(
        "ix_goods_receipt_items_goods_receipt_id",
        "goods_receipt_items",
        ["goods_receipt_id"],
    )
    op.create_index("ix_goods_receipt_items_product_id", "goods_receipt_items", ["product_id"])


def downgrade() -> None:
    op.drop_table("goods_receipt_items")
    op.drop_table("goods_receipts")
    op.drop_table("purchase_order_items")
    op.drop_table("purchase_orders")
