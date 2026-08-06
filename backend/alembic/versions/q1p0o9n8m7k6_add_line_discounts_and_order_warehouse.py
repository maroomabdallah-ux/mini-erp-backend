"""Add sales line discounts and selected order warehouse.

Revision ID: q1p0o9n8m7k6
Revises: p0o9n8m7k6j5
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "q1p0o9n8m7k6"
down_revision: str | None = "p0o9n8m7k6j5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "quotation_items",
        sa.Column(
            "discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"
        ),
    )
    op.create_check_constraint(
        "ck_quotation_items_discount_percent",
        "quotation_items",
        "discount_percent >= 0 AND discount_percent <= 100",
    )
    op.add_column(
        "sales_order_items",
        sa.Column(
            "discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"
        ),
    )
    op.create_check_constraint(
        "ck_sales_order_items_discount_percent",
        "sales_order_items",
        "discount_percent >= 0 AND discount_percent <= 100",
    )
    op.add_column(
        "sales_orders", sa.Column("warehouse_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_sales_orders_warehouse_id",
        "sales_orders",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_sales_orders_warehouse_id", "sales_orders", ["warehouse_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_sales_orders_warehouse_id", table_name="sales_orders")
    op.drop_constraint(
        "fk_sales_orders_warehouse_id", "sales_orders", type_="foreignkey"
    )
    op.drop_column("sales_orders", "warehouse_id")
    op.drop_constraint(
        "ck_sales_order_items_discount_percent",
        "sales_order_items",
        type_="check",
    )
    op.drop_column("sales_order_items", "discount_percent")
    op.drop_constraint(
        "ck_quotation_items_discount_percent",
        "quotation_items",
        type_="check",
    )
    op.drop_column("quotation_items", "discount_percent")
