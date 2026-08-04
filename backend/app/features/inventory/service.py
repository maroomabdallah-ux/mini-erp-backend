from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.features.audit.service import add_audit_log
from app.features.inventory import repository
from app.features.inventory.exceptions import (
    InactiveInventoryEntityError,
    InsufficientStockError,
    InsufficientTransferStockError,
    InvalidStockTransferError,
    InventoryCountConflictError,
    InventoryCountNotFoundError,
)
from app.features.inventory.models import InventoryCount, StockLevel, StockMovement
from app.features.inventory.schemas import (
    InventoryCountCreate,
    StockAdjustmentCreate,
    StockTransferCreate,
)
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


def transfer_stock(
    db: Session,
    data: StockTransferCreate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> dict:
    if data.source_warehouse_id == data.destination_warehouse_id:
        raise InvalidStockTransferError("Source and destination warehouses must be different.")

    product = repository.lock_product(db, data.product_id)
    if product is None:
        from app.features.products.exceptions import ProductNotFoundError

        raise ProductNotFoundError(data.product_id)
    source_warehouse = warehouse_repository.get_warehouse(db, data.source_warehouse_id)
    destination_warehouse = warehouse_repository.get_warehouse(db, data.destination_warehouse_id)
    if source_warehouse is None:
        from app.features.warehouses.exceptions import WarehouseNotFoundError

        raise WarehouseNotFoundError(data.source_warehouse_id)
    if destination_warehouse is None:
        from app.features.warehouses.exceptions import WarehouseNotFoundError

        raise WarehouseNotFoundError(data.destination_warehouse_id)
    if not product.is_active:
        raise InactiveInventoryEntityError("Stock cannot be transferred for an inactive product.")
    if not source_warehouse.is_active or not destination_warehouse.is_active:
        raise InactiveInventoryEntityError(
            "Stock can only be transferred between active warehouses."
        )

    locked_levels = {
        warehouse_id: repository.get_stock_level_for_update(db, product.id, warehouse_id)
        for warehouse_id in sorted([data.source_warehouse_id, data.destination_warehouse_id])
    }
    source = locked_levels[data.source_warehouse_id]
    destination = locked_levels[data.destination_warehouse_id]
    available = source.quantity if source is not None else Decimal("0.00")
    if source is None or available < data.quantity:
        raise InsufficientTransferStockError(_money(available), _money(data.quantity))
    if destination is None:
        destination = StockLevel(
            product_id=product.id,
            warehouse_id=data.destination_warehouse_id,
            quantity=Decimal("0.00"),
        )
        db.add(destination)
        db.flush()

    source_before = source.quantity
    destination_before = destination.quantity
    source.quantity -= data.quantity
    destination.quantity += data.quantity
    transfer_reference = f"TRF-{uuid4().hex[:12].upper()}"
    movement_reason = data.reason
    db.add_all(
        [
            StockMovement(
                product_id=product.id,
                warehouse_id=source_warehouse.id,
                type="out",
                quantity=-data.quantity,
                reference_type="warehouse_transfer",
                reference_id=transfer_reference,
                reason=movement_reason,
                created_by=actor_id,
            ),
            StockMovement(
                product_id=product.id,
                warehouse_id=destination_warehouse.id,
                type="in",
                quantity=data.quantity,
                reference_type="warehouse_transfer",
                reference_id=transfer_reference,
                reason=movement_reason,
                created_by=actor_id,
            ),
        ]
    )
    add_audit_log(
        db,
        user_id=actor_id,
        action="transfer",
        table_name="stock_levels",
        record_id=source.id,
        ip_address=ip_address,
        old_values={
            "source_quantity": _money(source_before),
            "destination_quantity": _money(destination_before),
        },
        new_values={
            "transfer_reference": transfer_reference,
            "product_id": product.id,
            "source_warehouse_id": source_warehouse.id,
            "destination_warehouse_id": destination_warehouse.id,
            "quantity": _money(data.quantity),
            "source_quantity": _money(source.quantity),
            "destination_quantity": _money(destination.quantity),
            "reason": data.reason,
        },
    )
    _commit(db)
    return {
        "transfer_reference": transfer_reference,
        "product_id": product.id,
        "source_warehouse_id": source_warehouse.id,
        "destination_warehouse_id": destination_warehouse.id,
        "quantity": data.quantity,
        "source_quantity": source.quantity,
        "destination_quantity": destination.quantity,
    }


def list_low_stock(db: Session) -> list[dict]:
    return repository.list_low_stock(db)


def list_counts(db: Session, *, page: int, size: int, status: str | None) -> dict:
    return {
        "items": repository.list_inventory_counts(
            db, offset=(page - 1) * size, limit=size, status=status
        ),
        "page": page,
        "size": size,
        "total": repository.count_inventory_counts(db, status=status),
    }


def create_count(
    db: Session,
    data: InventoryCountCreate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> InventoryCount:
    product = repository.lock_product(db, data.product_id)
    warehouse = warehouse_repository.get_warehouse(db, data.warehouse_id)
    if product is None:
        from app.features.products.exceptions import ProductNotFoundError

        raise ProductNotFoundError(data.product_id)
    if warehouse is None:
        from app.features.warehouses.exceptions import WarehouseNotFoundError

        raise WarehouseNotFoundError(data.warehouse_id)
    if not product.is_active or not warehouse.is_active:
        raise InactiveInventoryEntityError(
            "Physical counts require an active product and warehouse."
        )
    if repository.pending_inventory_count_exists(db, product.id, warehouse.id):
        raise InventoryCountConflictError(
            "A pending count already exists for this product and warehouse."
        )
    stock = repository.get_stock_level_for_update(db, product.id, warehouse.id)
    expected = stock.quantity if stock is not None else Decimal("0.00")
    count = InventoryCount(
        reference=f"CNT-{uuid4().hex[:12].upper()}",
        product_id=product.id,
        warehouse_id=warehouse.id,
        expected_quantity=expected,
        counted_quantity=data.counted_quantity,
        variance=data.counted_quantity - expected,
        notes=data.notes,
        status="pending",
        created_by=actor_id,
    )
    db.add(count)
    db.flush()
    add_audit_log(
        db,
        user_id=actor_id,
        action="create_count",
        table_name="inventory_counts",
        record_id=count.id,
        ip_address=ip_address,
        new_values={
            "reference": count.reference,
            "product_id": product.id,
            "warehouse_id": warehouse.id,
            "expected_quantity": _money(expected),
            "counted_quantity": _money(data.counted_quantity),
            "variance": _money(count.variance),
        },
    )
    _commit(db)
    return repository.get_inventory_count_for_update(db, count.id) or count


def approve_count(
    db: Session, count_id: int, *, actor_id: int, ip_address: str | None
) -> InventoryCount:
    count = repository.get_inventory_count_for_update(db, count_id)
    if count is None:
        raise InventoryCountNotFoundError(count_id)
    if count.status != "pending":
        raise InventoryCountConflictError("Only pending counts can be approved.")
    stock = repository.get_stock_level_for_update(db, count.product_id, count.warehouse_id)
    current = stock.quantity if stock is not None else Decimal("0.00")
    if current != count.expected_quantity:
        raise InventoryCountConflictError(
            "Stock changed after this count was recorded. Create a new physical count."
        )
    if count.created_by == actor_id:
        raise InventoryCountConflictError(
            "The user who recorded a physical count cannot approve the same count."
        )
    if stock is None:
        stock = StockLevel(
            product_id=count.product_id,
            warehouse_id=count.warehouse_id,
            quantity=Decimal("0.00"),
        )
        db.add(stock)
        db.flush()
    if count.variance != 0:
        stock.quantity = count.counted_quantity
        db.add(
            StockMovement(
                product_id=count.product_id,
                warehouse_id=count.warehouse_id,
                type="adjust",
                quantity=count.variance,
                reference_type="physical_count",
                reference_id=count.reference,
                reason=count.notes or "Approved physical stock count",
                created_by=actor_id,
            )
        )
    count.status = "approved"
    count.approved_by = actor_id
    count.approved_at = datetime.now(UTC)
    add_audit_log(
        db,
        user_id=actor_id,
        action="approve_count",
        table_name="inventory_counts",
        record_id=count.id,
        ip_address=ip_address,
        old_values={"status": "pending", "stock_quantity": _money(current)},
        new_values={
            "status": "approved",
            "stock_quantity": _money(count.counted_quantity),
            "variance": _money(count.variance),
        },
    )
    _commit(db)
    return repository.get_inventory_count_for_update(db, count.id) or count
