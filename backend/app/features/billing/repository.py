from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.features.billing.models import Invoice, InvoiceItem, Payment
from app.features.customers.models import Customer
from app.features.sales.models import SalesOrder


def _options(statement):
    return statement.options(
        selectinload(Invoice.customer),
        selectinload(Invoice.sales_order).selectinload(SalesOrder.customer),
        selectinload(Invoice.items).selectinload(InvoiceItem.product),
        selectinload(Invoice.payments),
    )


def get_invoice(db: Session, invoice_id: int, *, lock: bool = False) -> Invoice | None:
    statement = _options(select(Invoice)).where(Invoice.id == invoice_id)
    if lock:
        statement = statement.with_for_update()
    return cast(Invoice | None, db.scalar(statement))


def get_by_order(db: Session, sales_order_id: int) -> Invoice | None:
    return cast(
        Invoice | None,
        db.scalar(_options(select(Invoice)).where(Invoice.sales_order_id == sales_order_id)),
    )


def get_payment(db: Session, payment_id: int, *, lock: bool = False) -> Payment | None:
    statement = select(Payment).where(Payment.id == payment_id)
    if lock:
        statement = statement.with_for_update()
    return cast(Payment | None, db.scalar(statement))


def _filters(
    statement, *, search: str | None, status: str | None, customer_id: int | None, overdue: bool
):
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.join(Invoice.customer).where(
            or_(
                func.lower(Invoice.number).like(term),
                func.lower(Customer.name).like(term),
                func.lower(Customer.code).like(term),
            )
        )
    if status:
        statement = statement.where(Invoice.status == status)
    if customer_id:
        statement = statement.where(Invoice.customer_id == customer_id)
    if overdue:
        statement = statement.where(
            Invoice.due_date < func.current_date(), Invoice.status.in_(["issued", "partially_paid"])
        )
    return statement


def list_invoices(
    db: Session,
    *,
    offset: int,
    limit: int,
    search: str | None,
    status: str | None,
    customer_id: int | None,
    overdue: bool,
) -> list[Invoice]:
    statement = _filters(
        _options(select(Invoice)),
        search=search,
        status=status,
        customer_id=customer_id,
        overdue=overdue,
    )
    return list(
        db.scalars(
            statement.order_by(Invoice.created_at.desc(), Invoice.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def count_invoices(
    db: Session, *, search: str | None, status: str | None, customer_id: int | None, overdue: bool
) -> int:
    return int(
        db.scalar(
            _filters(
                select(func.count(Invoice.id)),
                search=search,
                status=status,
                customer_id=customer_id,
                overdue=overdue,
            )
        )
        or 0
    )


def eligible_orders(db: Session) -> list[SalesOrder]:
    return list(
        db.scalars(
            select(SalesOrder)
            .options(selectinload(SalesOrder.customer))
            .outerjoin(Invoice, Invoice.sales_order_id == SalesOrder.id)
            .where(SalesOrder.status == "delivered", Invoice.id.is_(None))
            .order_by(SalesOrder.created_at.desc())
        ).all()
    )
