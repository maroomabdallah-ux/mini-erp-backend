"""create inventory levels and movements

Revision ID: g1e0d9c8b7a6
Revises: f0d9c8b7a6e5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g1e0d9c8b7a6"
down_revision: str | Sequence[str] | None = "f0d9c8b7a6e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_levels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_stock_levels_quantity_nonnegative"),
        sa.UniqueConstraint("product_id", "warehouse_id", name="uq_stock_levels_product_warehouse"),
    )
    op.create_index("ix_stock_levels_product_id", "stock_levels", ["product_id"])
    op.create_index("ix_stock_levels_warehouse_id", "stock_levels", ["warehouse_id"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("type IN ('in', 'out', 'adjust')", name="ck_stock_movements_type"),
        sa.CheckConstraint("quantity != 0", name="ck_stock_movements_quantity_nonzero"),
    )
    op.create_index("ix_stock_movements_product_id", "stock_movements", ["product_id"])
    op.create_index("ix_stock_movements_warehouse_id", "stock_movements", ["warehouse_id"])
    op.create_index("ix_stock_movements_type", "stock_movements", ["type"])
    op.create_index("ix_stock_movements_reference_type", "stock_movements", ["reference_type"])
    op.create_index("ix_stock_movements_created_by", "stock_movements", ["created_by"])
    op.create_index("ix_stock_movements_created_at", "stock_movements", ["created_at"])


def downgrade() -> None:
    op.drop_table("stock_movements")
    op.drop_table("stock_levels")
