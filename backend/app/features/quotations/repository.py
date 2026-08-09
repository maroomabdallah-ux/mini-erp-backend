from datetime import date
from typing import cast

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.features.customers.models import Customer
from app.features.quotations.models import Quotation, QuotationItem


def _options(statement):
    return statement.options(
        selectinload(Quotation.customer),
        selectinload(Quotation.items).selectinload(QuotationItem.product),
    )


def get_quotation(db: Session, quotation_id: int, *, lock: bool = False) -> Quotation | None:
    statement = _options(select(Quotation)).where(Quotation.id == quotation_id)
    if lock:
        statement = statement.with_for_update()
    return cast(Quotation | None, db.scalar(statement))


def _filters(statement, *, search: str | None, status: str | None, customer_id: int | None):
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.join(Quotation.customer).where(
            or_(
                func.lower(Quotation.number).like(term),
                func.lower(Customer.name).like(term),
                func.lower(Customer.code).like(term),
            )
        )
    if status:
        statement = statement.where(Quotation.status == status)
    if customer_id:
        statement = statement.where(Quotation.customer_id == customer_id)
    return statement


def list_quotations(
    db: Session,
    *,
    offset: int,
    limit: int,
    search: str | None,
    status: str | None,
    customer_id: int | None,
) -> list[Quotation]:
    statement = _filters(
        _options(select(Quotation)), search=search, status=status, customer_id=customer_id
    )
    return list(
        db.scalars(
            statement.order_by(Quotation.created_at.desc(), Quotation.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def count_quotations(
    db: Session, *, search: str | None, status: str | None, customer_id: int | None
) -> int:
    return int(
        db.scalar(
            _filters(
                select(func.count(Quotation.id)),
                search=search,
                status=status,
                customer_id=customer_id,
            )
        )
        or 0
    )


def expire_past_due(db: Session) -> int:
    result = db.execute(
        update(Quotation)
        .where(Quotation.status == "sent", Quotation.valid_until < date.today())
        .values(status="expired")
    )
    return result.rowcount or 0
