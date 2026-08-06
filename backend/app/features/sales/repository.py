from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.features.customers.models import Customer
from app.features.sales.models import SalesDelivery, SalesDeliveryItem, SalesOrder, SalesOrderItem


def _options(statement):
    return statement.options(
        selectinload(SalesOrder.customer),
        selectinload(SalesOrder.warehouse),
        selectinload(SalesOrder.items).selectinload(SalesOrderItem.product),
        selectinload(SalesOrder.delivery).selectinload(SalesDelivery.warehouse),
        selectinload(SalesOrder.delivery)
        .selectinload(SalesDelivery.items)
        .selectinload(SalesDeliveryItem.product),
    )


def get_order(db: Session, order_id: int, *, lock: bool = False) -> SalesOrder | None:
    statement = _options(select(SalesOrder)).where(SalesOrder.id == order_id)
    if lock:
        statement = statement.with_for_update()
    return cast(SalesOrder | None, db.scalar(statement))


def get_by_quotation(db: Session, quotation_id: int) -> SalesOrder | None:
    return cast(
        SalesOrder | None,
        db.scalar(_options(select(SalesOrder)).where(SalesOrder.quotation_id == quotation_id)),
    )


def _filters(statement, *, search: str | None, status: str | None, customer_id: int | None):
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.join(SalesOrder.customer).where(
            or_(
                func.lower(SalesOrder.number).like(term),
                func.lower(Customer.name).like(term),
                func.lower(Customer.code).like(term),
            )
        )
    if status:
        statement = statement.where(SalesOrder.status == status)
    if customer_id:
        statement = statement.where(SalesOrder.customer_id == customer_id)
    return statement


def list_orders(
    db: Session,
    *,
    offset: int,
    limit: int,
    search: str | None,
    status: str | None,
    customer_id: int | None,
) -> list[SalesOrder]:
    statement = _filters(
        _options(select(SalesOrder)), search=search, status=status, customer_id=customer_id
    )
    return list(
        db.scalars(
            statement.order_by(SalesOrder.created_at.desc(), SalesOrder.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def count_orders(
    db: Session, *, search: str | None, status: str | None, customer_id: int | None
) -> int:
    return int(
        db.scalar(
            _filters(
                select(func.count(SalesOrder.id)),
                search=search,
                status=status,
                customer_id=customer_id,
            )
        )
        or 0
    )
