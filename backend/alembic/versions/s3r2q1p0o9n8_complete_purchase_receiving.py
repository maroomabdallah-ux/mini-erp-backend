"""Complete purchase order receiving lifecycle.

Revision ID: s3r2q1p0o9n8
Revises: r2q1p0o9n8m7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "s3r2q1p0o9n8"
down_revision: str | None = "r2q1p0o9n8m7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("warehouse_id", sa.Integer(), nullable=True))
    op.add_column("purchase_orders", sa.Column("expected_date", sa.Date(), nullable=True))
    op.add_column("purchase_orders", sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.create_foreign_key(
        "fk_purchase_orders_warehouse_id",
        "purchase_orders",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_purchase_orders_warehouse_id", "purchase_orders", ["warehouse_id"])
    op.create_index("ix_purchase_orders_expected_date", "purchase_orders", ["expected_date"])
    op.add_column(
        "purchase_order_items",
        sa.Column("received_quantity", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_purchase_order_items_received",
        "purchase_order_items",
        "received_quantity >= 0 AND received_quantity <= quantity",
    )
    op.drop_constraint("uq_goods_receipts_purchase_order_id", "goods_receipts", type_="unique")
    op.add_column("goods_receipt_items", sa.Column("purchase_order_item_id", sa.Integer()))
    op.execute(
        "UPDATE goods_receipt_items gri SET purchase_order_item_id = poi.id "
        "FROM goods_receipts gr JOIN purchase_order_items poi "
        "ON poi.purchase_order_id = gr.purchase_order_id "
        "WHERE gri.goods_receipt_id = gr.id AND gri.product_id = poi.product_id"
    )
    op.alter_column("goods_receipt_items", "purchase_order_item_id", nullable=False)
    op.create_foreign_key(
        "fk_goods_receipt_items_po_item",
        "goods_receipt_items",
        "purchase_order_items",
        ["purchase_order_item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_goods_receipt_items_purchase_order_item_id",
        "goods_receipt_items",
        ["purchase_order_item_id"],
    )
    op.execute(
        "UPDATE purchase_order_items poi SET received_quantity = COALESCE(("
        "SELECT SUM(gri.quantity) FROM goods_receipt_items gri "
        "WHERE gri.purchase_order_item_id = poi.id), 0)"
    )
    op.drop_constraint("ck_purchase_orders_status", "purchase_orders", type_="check")
    op.create_check_constraint(
        "ck_purchase_orders_status",
        "purchase_orders",
        "status IN ('draft','pending_approval','approved','sent','rejected',"
        "'cancelled','partially_received','received')",
    )
    op.execute(
        "UPDATE purchase_orders po SET warehouse_id = gr.warehouse_id, "
        "expected_date = COALESCE(gr.received_at::date, CURRENT_DATE) "
        "FROM goods_receipts gr WHERE gr.purchase_order_id = po.id"
    )
    op.execute(
        "UPDATE purchase_orders SET warehouse_id = (SELECT id FROM warehouses "
        "WHERE is_active = true ORDER BY id LIMIT 1), expected_date = CURRENT_DATE "
        "WHERE warehouse_id IS NULL"
    )
    op.alter_column("purchase_orders", "warehouse_id", nullable=False)
    op.alter_column("purchase_orders", "expected_date", nullable=False)


def downgrade() -> None:
    op.drop_constraint("ck_purchase_orders_status", "purchase_orders", type_="check")
    op.create_check_constraint(
        "ck_purchase_orders_status",
        "purchase_orders",
        "status IN ('draft','pending_approval','approved','rejected','cancelled','received')",
    )
    op.drop_index("ix_goods_receipt_items_purchase_order_item_id", table_name="goods_receipt_items")
    op.drop_constraint("fk_goods_receipt_items_po_item", "goods_receipt_items", type_="foreignkey")
    op.drop_column("goods_receipt_items", "purchase_order_item_id")
    op.create_unique_constraint(
        "uq_goods_receipts_purchase_order_id", "goods_receipts", ["purchase_order_id"]
    )
    op.drop_constraint("ck_purchase_order_items_received", "purchase_order_items", type_="check")
    op.drop_column("purchase_order_items", "received_quantity")
    op.drop_index("ix_purchase_orders_expected_date", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_warehouse_id", table_name="purchase_orders")
    op.drop_constraint("fk_purchase_orders_warehouse_id", "purchase_orders", type_="foreignkey")
    op.drop_column("purchase_orders", "sent_at")
    op.drop_column("purchase_orders", "expected_date")
    op.drop_column("purchase_orders", "warehouse_id")
