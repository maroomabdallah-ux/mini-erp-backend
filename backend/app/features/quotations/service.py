from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.features.audit.service import add_audit_log
from app.features.customers import repository as customer_repository
from app.features.products import repository as product_repository
from app.features.quotations import repository
from app.features.quotations.exceptions import (
    QuotationEntityError,
    QuotationNotFoundError,
    QuotationStateError,
)
from app.features.quotations.models import Quotation, QuotationItem
from app.features.quotations.schemas import QuotationCreate, QuotationUpdate

CENT = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(UTC)


def _get(db: Session, quotation_id: int, *, lock: bool = False) -> Quotation:
    quotation = repository.get_quotation(db, quotation_id, lock=lock)
    if quotation is None:
        raise QuotationNotFoundError(quotation_id)
    return quotation


def _validate(db: Session, data: QuotationCreate | QuotationUpdate) -> None:
    customer = customer_repository.get_customer(db, data.customer_id)
    if customer is None or not customer.is_active:
        raise QuotationEntityError("Quotations require an active customer.")
    if data.valid_until < date.today():
        raise QuotationEntityError("Quotation validity cannot be in the past.")
    for item in data.items:
        product = product_repository.get_product(db, item.product_id)
        if product is None or not product.is_active:
            raise QuotationEntityError(f"Product with id {item.product_id} is unavailable.")


def _replace(quotation: Quotation, data: QuotationCreate | QuotationUpdate) -> None:
    quotation.items = [
        QuotationItem(
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=(item.unit_price * item.quantity).quantize(CENT, rounding=ROUND_HALF_UP),
        )
        for item in data.items
    ]
    quotation.subtotal = sum((item.line_total for item in quotation.items), Decimal("0.00"))
    quotation.discount_percent = data.discount_percent
    quotation.tax_percent = data.tax_percent
    quotation.discount_amount = (quotation.subtotal * data.discount_percent / 100).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    taxable = quotation.subtotal - quotation.discount_amount
    quotation.tax_amount = (taxable * data.tax_percent / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    quotation.total_amount = taxable + quotation.tax_amount


def _audit(
    db: Session,
    quotation: Quotation,
    *,
    actor_id: int,
    action: str,
    ip_address: str | None,
    old_status: str | None = None,
) -> None:
    add_audit_log(
        db,
        user_id=actor_id,
        action=action,
        table_name="quotations",
        record_id=quotation.id,
        ip_address=ip_address,
        old_values={"status": old_status} if old_status else None,
        new_values={
            "number": quotation.number,
            "status": quotation.status,
            "customer_id": quotation.customer_id,
            "total_amount": f"{quotation.total_amount:.2f}",
        },
    )


def list_quotations(
    db: Session,
    *,
    page: int,
    size: int,
    search: str | None,
    status: str | None,
    customer_id: int | None,
) -> dict:
    return {
        "items": repository.list_quotations(
            db,
            offset=(page - 1) * size,
            limit=size,
            search=search,
            status=status,
            customer_id=customer_id,
        ),
        "page": page,
        "size": size,
        "total": repository.count_quotations(
            db, search=search, status=status, customer_id=customer_id
        ),
    }


def get_quotation(db: Session, quotation_id: int) -> Quotation:
    return _get(db, quotation_id)


def create_quotation(
    db: Session, data: QuotationCreate, *, actor_id: int, ip_address: str | None
) -> Quotation:
    _validate(db, data)
    quotation = Quotation(
        number=f"QT-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        customer_id=data.customer_id,
        valid_until=data.valid_until,
        notes=data.notes,
        created_by=actor_id,
    )
    _replace(quotation, data)
    db.add(quotation)
    db.flush()
    _audit(db, quotation, actor_id=actor_id, action="create", ip_address=ip_address)
    db.commit()
    return _get(db, quotation.id)


def update_quotation(
    db: Session, quotation_id: int, data: QuotationUpdate, *, actor_id: int, ip_address: str | None
) -> Quotation:
    quotation = _get(db, quotation_id, lock=True)
    if quotation.status != "draft":
        raise QuotationStateError("Only draft quotations can be edited.")
    _validate(db, data)
    quotation.customer_id = data.customer_id
    quotation.valid_until = data.valid_until
    quotation.notes = data.notes
    _replace(quotation, data)
    _audit(db, quotation, actor_id=actor_id, action="update", ip_address=ip_address)
    db.commit()
    return _get(db, quotation.id)


def transition(
    db: Session,
    quotation_id: int,
    action: str,
    *,
    actor_id: int,
    ip_address: str | None,
    reason: str | None = None,
) -> Quotation:
    quotation = _get(db, quotation_id, lock=True)
    old = quotation.status
    allowed = {
        "send": ("draft", "sent"),
        "accept": ("sent", "accepted"),
        "reject": ("sent", "rejected"),
        "expire": ("sent", "expired"),
    }
    source, target = allowed[action]
    if quotation.status != source:
        raise QuotationStateError(f"Only {source} quotations can be marked as {target}.")
    if action in {"send", "accept"} and quotation.valid_until < date.today():
        quotation.status = "expired"
        _audit(
            db, quotation, actor_id=actor_id, action="expire", ip_address=ip_address, old_status=old
        )
        db.commit()
        raise QuotationStateError("This quotation has expired.")
    quotation.status = target
    if action == "send":
        quotation.sent_at = _now()
    if action == "accept":
        quotation.accepted_at = _now()
    if action == "reject":
        quotation.rejected_at = _now()
        quotation.rejection_reason = reason
    _audit(db, quotation, actor_id=actor_id, action=action, ip_address=ip_address, old_status=old)
    db.commit()
    return _get(db, quotation.id)
