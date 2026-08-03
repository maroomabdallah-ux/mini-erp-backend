from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.features.audit.service import add_audit_log
from app.features.warehouses import repository
from app.features.warehouses.exceptions import (
    DuplicateWarehouseCodeError,
    WarehouseDeactivationError,
    WarehouseNotFoundError,
)
from app.features.warehouses.models import Warehouse
from app.features.warehouses.schemas import WarehouseCreate, WarehouseUpdate


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        constraint = getattr(exc.orig, "diag", None)
        if getattr(constraint, "constraint_name", "") == "uq_warehouses_code":
            raise ConflictError("The warehouse code already exists.") from exc
        raise


def _warehouse_or_error(db: Session, warehouse_id: int) -> Warehouse:
    warehouse = repository.get_warehouse(db, warehouse_id)
    if warehouse is None:
        raise WarehouseNotFoundError(warehouse_id)
    return warehouse


def _values(warehouse: Warehouse) -> dict:
    return {
        "code": warehouse.code,
        "name": warehouse.name,
        "address": warehouse.address,
        "is_active": warehouse.is_active,
    }


def list_warehouses(
    db: Session,
    *,
    page: int,
    size: int,
    search: str | None,
    is_active: bool | None,
) -> dict:
    return {
        "items": repository.list_warehouses(
            db,
            offset=(page - 1) * size,
            limit=size,
            search=search,
            is_active=is_active,
        ),
        "page": page,
        "size": size,
        "total": repository.count_warehouses(
            db, search=search, is_active=is_active
        ),
    }


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse:
    return _warehouse_or_error(db, warehouse_id)


def create_warehouse(
    db: Session,
    data: WarehouseCreate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Warehouse:
    if repository.get_warehouse_by_code(db, data.code):
        raise DuplicateWarehouseCodeError(data.code)
    warehouse = Warehouse(code=data.code, name=data.name, address=data.address)
    db.add(warehouse)
    db.flush()
    add_audit_log(
        db,
        user_id=actor_id,
        action="create",
        table_name="warehouses",
        record_id=warehouse.id,
        ip_address=ip_address,
        new_values=_values(warehouse),
    )
    _commit(db)
    return _warehouse_or_error(db, warehouse.id)


def update_warehouse(
    db: Session,
    warehouse_id: int,
    data: WarehouseUpdate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Warehouse:
    warehouse = _warehouse_or_error(db, warehouse_id)
    old_values = _values(warehouse)
    if data.code is not None and data.code != warehouse.code:
        existing = repository.get_warehouse_by_code(db, data.code)
        if existing is not None and existing.id != warehouse.id:
            raise DuplicateWarehouseCodeError(data.code)
        warehouse.code = data.code
    if data.name is not None:
        warehouse.name = data.name
    if "address" in data.model_fields_set:
        warehouse.address = data.address
    add_audit_log(
        db,
        user_id=actor_id,
        action="update",
        table_name="warehouses",
        record_id=warehouse.id,
        ip_address=ip_address,
        old_values=old_values,
        new_values=_values(warehouse),
    )
    _commit(db)
    return _warehouse_or_error(db, warehouse.id)


def deactivate_warehouse(
    db: Session,
    warehouse_id: int,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Warehouse:
    warehouse = _warehouse_or_error(db, warehouse_id)
    if not warehouse.is_active:
        raise WarehouseDeactivationError(
            f"Warehouse with id {warehouse_id} is already inactive."
        )
    if repository.has_stock(db, warehouse_id):
        raise WarehouseDeactivationError(
            "A warehouse holding stock cannot be deactivated."
        )
    warehouse.is_active = False
    add_audit_log(
        db,
        user_id=actor_id,
        action="deactivate",
        table_name="warehouses",
        record_id=warehouse.id,
        ip_address=ip_address,
        old_values={"is_active": True},
        new_values={"is_active": False},
    )
    _commit(db)
    return _warehouse_or_error(db, warehouse.id)
