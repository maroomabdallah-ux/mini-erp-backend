from datetime import datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.features.inventory.models import InventoryCount, StockLevel, StockMovement
from app.features.products.models import Product


def get_stock_level_for_update(
    db: Session, product_id: int, warehouse_id: int
) -> StockLevel | None:
    return cast(
        StockLevel | None,
        db.scalar(
            select(StockLevel)
            .where(
                StockLevel.product_id == product_id,
                StockLevel.warehouse_id == warehouse_id,
            )
            .with_for_update()
        ),
    )


def lock_product(db: Session, product_id: int) -> Product | None:
    return cast(
        Product | None,
        db.scalar(select(Product).where(Product.id == product_id).with_for_update()),
    )


def _stock_filters(statement, *, product_id, warehouse_id, search):
    if product_id is not None:
        statement = statement.where(StockLevel.product_id == product_id)
    if warehouse_id is not None:
        statement = statement.where(StockLevel.warehouse_id == warehouse_id)
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.join(StockLevel.product).where(
            or_(
                func.lower(Product.name).like(term),
                func.lower(Product.sku).like(term),
            )
        )
    return statement


def list_stock_levels(
    db: Session,
    *,
    offset: int,
    limit: int,
    product_id: int | None,
    warehouse_id: int | None,
    search: str | None,
) -> list[StockLevel]:
    statement = _stock_filters(
        select(StockLevel).options(
            selectinload(StockLevel.product), selectinload(StockLevel.warehouse)
        ),
        product_id=product_id,
        warehouse_id=warehouse_id,
        search=search,
    )
    return list(
        db.scalars(
            statement.order_by(StockLevel.product_id, StockLevel.warehouse_id)
            .offset(offset)
            .limit(limit)
        ).all()
    )


def count_stock_levels(
    db: Session,
    *,
    product_id: int | None,
    warehouse_id: int | None,
    search: str | None,
) -> int:
    statement = _stock_filters(
        select(func.count(StockLevel.id)),
        product_id=product_id,
        warehouse_id=warehouse_id,
        search=search,
    )
    return int(db.scalar(statement) or 0)


def total_stock_quantity(
    db: Session,
    *,
    product_id: int | None,
    warehouse_id: int | None,
    search: str | None,
) -> Decimal:
    statement = _stock_filters(
        select(func.coalesce(func.sum(StockLevel.quantity), 0)),
        product_id=product_id,
        warehouse_id=warehouse_id,
        search=search,
    )
    return Decimal(db.scalar(statement) or 0)


def _movement_filters(
    statement,
    *,
    product_id,
    warehouse_id,
    movement_type,
    date_from,
    date_to,
):
    if product_id is not None:
        statement = statement.where(StockMovement.product_id == product_id)
    if warehouse_id is not None:
        statement = statement.where(StockMovement.warehouse_id == warehouse_id)
    if movement_type is not None:
        statement = statement.where(StockMovement.type == movement_type)
    if date_from is not None:
        statement = statement.where(StockMovement.created_at >= date_from)
    if date_to is not None:
        statement = statement.where(StockMovement.created_at <= date_to)
    return statement


def list_movements(
    db: Session,
    *,
    offset: int,
    limit: int,
    product_id: int | None,
    warehouse_id: int | None,
    movement_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[StockMovement]:
    statement = _movement_filters(
        select(StockMovement).options(
            selectinload(StockMovement.product),
            selectinload(StockMovement.warehouse),
        ),
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        date_from=date_from,
        date_to=date_to,
    )
    return list(
        db.scalars(
            statement.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def count_movements(
    db: Session,
    *,
    product_id: int | None,
    warehouse_id: int | None,
    movement_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> int:
    statement = _movement_filters(
        select(func.count(StockMovement.id)),
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        date_from=date_from,
        date_to=date_to,
    )
    return int(db.scalar(statement) or 0)


def list_low_stock(db: Session) -> list[dict]:
    total = func.coalesce(func.sum(StockLevel.quantity), 0)
    rows = db.execute(
        select(
            Product.id,
            Product.sku,
            Product.name,
            Product.min_stock_level,
            total.label("total_quantity"),
        )
        .outerjoin(StockLevel, StockLevel.product_id == Product.id)
        .where(Product.is_active.is_(True), Product.min_stock_level > 0)
        .group_by(Product.id)
        .having(total < Product.min_stock_level)
        .order_by((Product.min_stock_level - total).desc(), Product.name)
    ).all()
    return [
        {
            "product_id": row.id,
            "sku": row.sku,
            "name": row.name,
            "total_quantity": Decimal(row.total_quantity),
            "min_stock_level": row.min_stock_level,
            "shortage": row.min_stock_level - Decimal(row.total_quantity),
        }
        for row in rows
    ]


def warehouse_stock_quantity(db: Session, warehouse_id: int) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(StockLevel.quantity), 0)).where(
            StockLevel.warehouse_id == warehouse_id
        )
    )
    return Decimal(value or 0)


def list_inventory_counts(
    db: Session, *, offset: int, limit: int, status: str | None
) -> list[InventoryCount]:
    statement = select(InventoryCount).options(
        selectinload(InventoryCount.product), selectinload(InventoryCount.warehouse)
    )
    if status is not None:
        statement = statement.where(InventoryCount.status == status)
    return list(
        db.scalars(
            statement.order_by(InventoryCount.created_at.desc(), InventoryCount.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def count_inventory_counts(db: Session, *, status: str | None) -> int:
    statement = select(func.count(InventoryCount.id))
    if status is not None:
        statement = statement.where(InventoryCount.status == status)
    return int(db.scalar(statement) or 0)


def get_inventory_count_for_update(db: Session, count_id: int) -> InventoryCount | None:
    return cast(
        InventoryCount | None,
        db.scalar(
            select(InventoryCount)
            .options(
                selectinload(InventoryCount.product),
                selectinload(InventoryCount.warehouse),
            )
            .where(InventoryCount.id == count_id)
            .with_for_update()
        ),
    )


def pending_inventory_count_exists(db: Session, product_id: int, warehouse_id: int) -> bool:
    return (
        db.scalar(
            select(InventoryCount.id)
            .where(
                InventoryCount.product_id == product_id,
                InventoryCount.warehouse_id == warehouse_id,
                InventoryCount.status == "pending",
            )
            .limit(1)
        )
        is not None
    )
