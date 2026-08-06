from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.features.warehouses.models import Warehouse


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse | None:
    return cast(Warehouse | None, db.get(Warehouse, warehouse_id))


def get_warehouse_by_code(db: Session, code: str) -> Warehouse | None:
    return cast(
        Warehouse | None,
        db.scalar(select(Warehouse).where(func.lower(Warehouse.code) == code.lower())),
    )


def _warehouse_filters(statement, *, search: str | None, is_active: bool | None):
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Warehouse.code).like(term),
                func.lower(Warehouse.name).like(term),
                func.lower(Warehouse.address).like(term),
            )
        )
    if is_active is not None:
        statement = statement.where(Warehouse.is_active.is_(is_active))
    return statement


def list_warehouses(
    db: Session,
    *,
    offset: int,
    limit: int,
    search: str | None,
    is_active: bool | None,
) -> list[Warehouse]:
    statement = _warehouse_filters(select(Warehouse), search=search, is_active=is_active)
    return list(db.scalars(statement.order_by(Warehouse.name).offset(offset).limit(limit)).all())


def count_warehouses(db: Session, *, search: str | None, is_active: bool | None) -> int:
    statement = _warehouse_filters(
        select(func.count(Warehouse.id)), search=search, is_active=is_active
    )
    return int(db.scalar(statement) or 0)


def has_stock(db: Session, warehouse_id: int) -> bool:
    from app.features.inventory.repository import warehouse_stock_quantity

    return warehouse_stock_quantity(db, warehouse_id) > 0
