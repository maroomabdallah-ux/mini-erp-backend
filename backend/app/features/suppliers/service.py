from sqlalchemy.orm import Session

from app.features.audit.service import add_audit_log
from app.features.suppliers import repository
from app.features.suppliers.exceptions import (
    SupplierDeactivationError,
    SupplierNotFoundError,
)
from app.features.suppliers.models import Supplier
from app.features.suppliers.schemas import SupplierCreate, SupplierUpdate


def _supplier_or_error(db: Session, supplier_id: int) -> Supplier:
    supplier = repository.get_supplier(db, supplier_id)
    if supplier is None:
        raise SupplierNotFoundError(supplier_id)
    return supplier


def _values(supplier: Supplier) -> dict:
    return {
        "name": supplier.name,
        "email": supplier.email,
        "phone": supplier.phone,
        "credit_terms": supplier.credit_terms,
        "is_active": supplier.is_active,
    }


def list_suppliers(
    db: Session,
    *,
    page: int,
    size: int,
    search: str | None,
    is_active: bool | None,
) -> dict:
    return {
        "items": repository.list_suppliers(
            db,
            offset=(page - 1) * size,
            limit=size,
            search=search,
            is_active=is_active,
        ),
        "page": page,
        "size": size,
        "total": repository.count_suppliers(
            db, search=search, is_active=is_active
        ),
    }


def get_supplier(db: Session, supplier_id: int) -> Supplier:
    return _supplier_or_error(db, supplier_id)


def create_supplier(
    db: Session,
    data: SupplierCreate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Supplier:
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.flush()
    add_audit_log(
        db,
        user_id=actor_id,
        action="create",
        table_name="suppliers",
        record_id=supplier.id,
        ip_address=ip_address,
        new_values=_values(supplier),
    )
    db.commit()
    return _supplier_or_error(db, supplier.id)


def update_supplier(
    db: Session,
    supplier_id: int,
    data: SupplierUpdate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Supplier:
    supplier = _supplier_or_error(db, supplier_id)
    old_values = _values(supplier)
    for field in data.model_fields_set:
        setattr(supplier, field, getattr(data, field))
    add_audit_log(
        db,
        user_id=actor_id,
        action="update",
        table_name="suppliers",
        record_id=supplier.id,
        ip_address=ip_address,
        old_values=old_values,
        new_values=_values(supplier),
    )
    db.commit()
    return _supplier_or_error(db, supplier.id)


def deactivate_supplier(
    db: Session,
    supplier_id: int,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Supplier:
    supplier = _supplier_or_error(db, supplier_id)
    if not supplier.is_active:
        raise SupplierDeactivationError(
            f"Supplier with id {supplier_id} is already inactive."
        )
    supplier.is_active = False
    add_audit_log(
        db,
        user_id=actor_id,
        action="deactivate",
        table_name="suppliers",
        record_id=supplier.id,
        ip_address=ip_address,
        old_values={"is_active": True},
        new_values={"is_active": False},
    )
    db.commit()
    return _supplier_or_error(db, supplier.id)
