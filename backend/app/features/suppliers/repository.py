from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.features.suppliers.models import Supplier


def get_supplier(db: Session, supplier_id: int) -> Supplier | None:
    return cast(Supplier | None, db.get(Supplier, supplier_id))


def _supplier_filters(statement, *, search: str | None, is_active: bool | None):
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Supplier.name).like(term),
                func.lower(Supplier.email).like(term),
                func.lower(Supplier.phone).like(term),
                func.lower(Supplier.credit_terms).like(term),
            )
        )
    if is_active is not None:
        statement = statement.where(Supplier.is_active.is_(is_active))
    return statement


def list_suppliers(
    db: Session,
    *,
    offset: int,
    limit: int,
    search: str | None,
    is_active: bool | None,
) -> list[Supplier]:
    statement = _supplier_filters(select(Supplier), search=search, is_active=is_active)
    return list(db.scalars(statement.order_by(Supplier.name).offset(offset).limit(limit)).all())


def count_suppliers(db: Session, *, search: str | None, is_active: bool | None) -> int:
    statement = _supplier_filters(
        select(func.count(Supplier.id)), search=search, is_active=is_active
    )
    return int(db.scalar(statement) or 0)
