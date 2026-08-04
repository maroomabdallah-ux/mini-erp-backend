"""create inventory counts

Revision ID: h2f1e0d9c8b7
Revises: g1e0d9c8b7a6
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "h2f1e0d9c8b7"
down_revision: str | Sequence[str] | None = "g1e0d9c8b7a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_counts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(30), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expected_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("counted_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("variance", sa.Numeric(12, 2), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'approved')", name="ck_inventory_counts_status"),
        sa.CheckConstraint("counted_quantity >= 0", name="ck_inventory_counts_counted_nonnegative"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_inventory_counts_reference", "inventory_counts", ["reference"], unique=True)
    op.create_index("ix_inventory_counts_product_id", "inventory_counts", ["product_id"])
    op.create_index("ix_inventory_counts_warehouse_id", "inventory_counts", ["warehouse_id"])
    op.create_index("ix_inventory_counts_status", "inventory_counts", ["status"])


def downgrade() -> None:
    op.drop_table("inventory_counts")
