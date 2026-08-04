"""make inventory quantities integer

Revision ID: j4h3g2f1e0d9
Revises: i3g2f1e0d9c8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "j4h3g2f1e0d9"
down_revision: str | None = "i3g2f1e0d9c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing fractional quantities are rounded to the nearest whole unit once.
    op.alter_column(
        "products",
        "min_stock_level",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Integer(),
        postgresql_using="ROUND(min_stock_level)::integer",
        existing_nullable=False,
    )
    op.alter_column(
        "stock_levels",
        "quantity",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Integer(),
        postgresql_using="ROUND(quantity)::integer",
        existing_nullable=False,
    )
    op.alter_column(
        "stock_movements",
        "quantity",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Integer(),
        postgresql_using=(
            "CASE WHEN ROUND(quantity) = 0 "
            "THEN CASE WHEN quantity > 0 THEN 1 ELSE -1 END "
            "ELSE ROUND(quantity)::integer END"
        ),
        existing_nullable=False,
    )
    for column in ("expected_quantity", "counted_quantity", "variance"):
        op.alter_column(
            "inventory_counts",
            column,
            existing_type=sa.Numeric(12, 2),
            type_=sa.Integer(),
            postgresql_using=f"ROUND({column})::integer",
            existing_nullable=False,
        )
    op.execute(
        "UPDATE inventory_counts "
        "SET variance = counted_quantity - expected_quantity"
    )


def downgrade() -> None:
    for column in ("expected_quantity", "counted_quantity", "variance"):
        op.alter_column(
            "inventory_counts",
            column,
            existing_type=sa.Integer(),
            type_=sa.Numeric(12, 2),
            postgresql_using=f"{column}::numeric(12,2)",
            existing_nullable=False,
        )
    op.alter_column("stock_movements", "quantity", existing_type=sa.Integer(), type_=sa.Numeric(12, 2), postgresql_using="quantity::numeric(12,2)", existing_nullable=False)
    op.alter_column("stock_levels", "quantity", existing_type=sa.Integer(), type_=sa.Numeric(12, 2), postgresql_using="quantity::numeric(12,2)", existing_nullable=False)
    op.alter_column("products", "min_stock_level", existing_type=sa.Integer(), type_=sa.Numeric(12, 2), postgresql_using="min_stock_level::numeric(12,2)", existing_nullable=False)
