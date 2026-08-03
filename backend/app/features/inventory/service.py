from datetime import datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.features.audit.service import add_audit_log
from app.features.inventory import repository
from app.features.inventory.exceptions import (
    InactiveInventoryEntityError,
    InsufficientStockError,
)
from app.features.inventory.models import StockLevel, StockMovement
from app.features.inventory.schemas import StockAdjustmentCreate
from app.features.warehouses import repository as warehouse_repository


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("The inventory operation conflicted with another update.") from exc


def list_stock(
    db: Session,
    *,
    page: int,
    size: int,
    product_id: int | None,
    warehouse_id: int | None,
    search: str | None,
) -> dict:
    return {
        "items": repository.list_stock_levels(
            db,
            offset=(page - 1) * size,
            limit=size,
            product_id=product_id,
            warehouse_id=warehouse_id,
            search=search,
        ),
        "page": page,
        "size": size,
        "total": repository.count_stock_levels(
            db,
            product_id=product_id,
            warehouse_id=warehouse_id,
            search=search,
        ),
        "total_quantity": repository.total_stock_quantity(
            db,
            product_id=product_id,
            warehouse_id=warehouse_id,
            search=search,
        ),
    }


def list_movements(
    db: Session,
    *,
    page: int,
    size: int,
    product_id: int | None,
    warehouse_id: int | None,
    movement_type: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> dict:
    return {
        "items": repository.list_movements(
            db,
            offset=(page - 1) * size,
            limit=size,
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            date_from=date_from,
            date_to=date_to,
        ),
        "page": page,
        "size": size,
        "total": repository.count_movements(
            db,
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            date_from=date_from,
            date_to=date_to,
        ),
    }


def adjust_stock(
    db: Session,
    data: StockAdjustmentCreate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> StockLevel:
    product = repository.lock_product(db, data.product_id)
    if product is None:
        from app.features.products.exceptions import ProductNotFoundError

        raise ProductNotFoundError(data.product_id)
    warehouse = warehouse_repository.get_warehouse(db, data.warehouse_id)
    if warehouse is None:
        from app.features.warehouses.exceptions import WarehouseNotFoundError

        raise WarehouseNotFoundError(data.warehouse_id)
    if not product.is_active:
        raise InactiveInventoryEntityError("Stock cannot be adjusted for an inactive product.")
    if not warehouse.is_active:
        raise InactiveInventoryEntityError("Stock cannot be adjusted in an inactive warehouse.")

    stock = repository.get_stock_level_for_update(db, product.id, warehouse.id)
    if stock is None:
        stock = StockLevel(
            product_id=product.id,
            warehouse_id=warehouse.id,
            quantity=Decimal("0.00"),
        )
        db.add(stock)
        db.flush()
    old_quantity = stock.quantity
    new_quantity = old_quantity + data.quantity_change
    if new_quantity < 0:
        db.rollback()
        raise InsufficientStockError(_money(old_quantity), _money(data.quantity_change))
    stock.quantity = new_quantity
    db.add(
        StockMovement(
            product_id=product.id,
            warehouse_id=warehouse.id,
            type="adjust",
            quantity=data.quantity_change,
            reference_type="manual_adjustment",
            reason=data.reason,
            created_by=actor_id,
        )
    )
    add_audit_log(
        db,
        user_id=actor_id,
        action="adjust",
        table_name="stock_levels",
        record_id=stock.id,
        ip_address=ip_address,
        old_values={"quantity": _money(old_quantity)},
        new_values={
            "quantity": _money(new_quantity),
            "change": _money(data.quantity_change),
            "reason": data.reason,
        },
    )
    _commit(db)
    return repository.list_stock_levels(
        db,
        offset=0,
        limit=1,
        product_id=product.id,
        warehouse_id=warehouse.id,
        search=None,
    )[0]


def list_low_stock(db: Session) -> list[dict]:
    return repository.list_low_stock(db)
