from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.features.accounting.service import post_entry
from app.features.audit.service import add_audit_log
from app.features.billing import repository
from app.features.billing.exceptions import (
    InvoiceConflictError,
    InvoiceNotFoundError,
    InvoiceStateError,
    PaymentNotFoundError,
)
from app.features.billing.models import Invoice, InvoiceItem, Payment, PaymentAllocation
from app.features.billing.schemas import CustomerPaymentCreate, InvoiceCreate, PaymentCreate
from app.features.customers.models import Customer
from app.features.sales import repository as sales_repository


def _now() -> datetime:
    return datetime.now(UTC)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("The billing operation conflicted with another update.") from exc


def _get(db: Session, invoice_id: int, *, lock: bool = False) -> Invoice:
    invoice = repository.get_invoice(db, invoice_id, lock=lock)
    if invoice is None:
        raise InvoiceNotFoundError(invoice_id)
    return invoice


def _status_for(invoice: Invoice) -> str:
    if invoice.paid_amount <= 0:
        return "issued"
    if invoice.paid_amount >= invoice.total_amount:
        return "paid"
    return "partially_paid"


def list_invoices(
    db: Session,
    *,
    page: int,
    size: int,
    search: str | None,
    status: str | None,
    customer_id: int | None,
    overdue: bool,
) -> dict:
    return {
        "items": repository.list_invoices(
            db,
            offset=(page - 1) * size,
            limit=size,
            search=search,
            status=status,
            customer_id=customer_id,
            overdue=overdue,
        ),
        "page": page,
        "size": size,
        "total": repository.count_invoices(
            db, search=search, status=status, customer_id=customer_id, overdue=overdue
        ),
    }


def get_invoice(db: Session, invoice_id: int) -> Invoice:
    return _get(db, invoice_id)


def eligible_orders(db: Session):
    return repository.eligible_orders(db)


def create_invoice(
    db: Session, data: InvoiceCreate, *, actor_id: int, ip_address: str | None
) -> Invoice:
    order = sales_repository.get_order(db, data.sales_order_id, lock=True)
    if order is None:
        from app.features.sales.exceptions import SalesOrderNotFoundError

        raise SalesOrderNotFoundError(data.sales_order_id)
    if order.status != "delivered":
        raise InvoiceStateError("Only delivered sales orders can be invoiced.")
    existing = repository.get_by_order(db, order.id)
    if existing is not None:
        raise InvoiceConflictError(f"Sales order already invoiced as {existing.number}.")
    delivered_date = order.delivery.delivered_at.date() if order.delivery else date.today()
    due_date = data.due_date or delivered_date + timedelta(days=30)
    if due_date < delivered_date:
        raise InvoiceStateError("Invoice due date cannot be before the delivery date.")
    invoice = Invoice(
        number=f"INV-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        sales_order_id=order.id,
        customer_id=order.customer_id,
        status="draft",
        due_date=due_date,
        notes=data.notes or order.notes,
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        tax_amount=order.tax_amount,
        total_amount=order.total_amount,
        paid_amount=Decimal("0.00"),
        created_by=actor_id,
        items=[
            InvoiceItem(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
            )
            for item in order.items
        ],
    )
    db.add(invoice)
    db.flush()
    add_audit_log(
        db,
        user_id=actor_id,
        action="create",
        table_name="invoices",
        record_id=invoice.id,
        ip_address=ip_address,
        new_values={
            "number": invoice.number,
            "sales_order_id": order.id,
            "total_amount": f"{invoice.total_amount:.2f}",
            "status": "draft",
        },
    )
    _commit(db)
    return _get(db, invoice.id)


def issue_invoice(
    db: Session, invoice_id: int, *, actor_id: int, ip_address: str | None
) -> Invoice:
    invoice = _get(db, invoice_id, lock=True)
    if invoice.status != "draft":
        raise InvoiceStateError("Only draft invoices can be issued.")
    invoice.status = "issued"
    invoice.issue_date = date.today()
    invoice.issued_by = actor_id
    invoice.issued_at = _now()
    cogs = sum(
        (item.product.cost_price * item.quantity for item in invoice.items),
        Decimal("0"),
    )
    journal_lines = [
        ("1200", invoice.total_amount, Decimal("0"), invoice.customer.name),
        ("4000", Decimal("0"), invoice.total_amount, invoice.customer.name),
    ]
    if cogs > 0:
        journal_lines.extend(
            [
                ("5000", cogs, Decimal("0"), invoice.number),
                ("1300", Decimal("0"), cogs, invoice.number),
            ]
        )
    post_entry(
        db,
        entry_date=invoice.issue_date,
        description=f"Sales invoice {invoice.number}",
        source_type="sales_invoice",
        source_id=invoice.id,
        actor_id=actor_id,
        lines=journal_lines,
    )
    add_audit_log(
        db,
        user_id=actor_id,
        action="issue",
        table_name="invoices",
        record_id=invoice.id,
        ip_address=ip_address,
        old_values={"status": "draft"},
        new_values={"status": "issued", "due_date": str(invoice.due_date)},
    )
    _commit(db)
    return _get(db, invoice.id)


def cancel_invoice(
    db: Session, invoice_id: int, reason: str, *, actor_id: int, ip_address: str | None
) -> Invoice:
    invoice = _get(db, invoice_id, lock=True)
    if invoice.document_type != "invoice":
        raise InvoiceStateError("Credit notes cannot be cancelled.")
    if invoice.status not in {"draft", "issued"}:
        raise InvoiceStateError("Only draft or unpaid issued invoices can be cancelled.")
    if invoice.paid_amount != 0:
        raise InvoiceStateError("Reverse all posted payments before cancelling this invoice.")
    if invoice.status == "draft":
        old = invoice.status
        invoice.status = "cancelled"
        invoice.cancelled_by = actor_id
        invoice.cancelled_at = _now()
        invoice.cancellation_reason = reason
        add_audit_log(
            db,
            user_id=actor_id,
            action="cancel",
            table_name="invoices",
            record_id=invoice.id,
            ip_address=ip_address,
            old_values={"status": old},
            new_values={"status": "cancelled", "reason": reason},
        )
        _commit(db)
        return _get(db, invoice.id)
    old = invoice.status
    credit_note = Invoice(
        number=f"CRN-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        document_type="credit_note",
        sales_order_id=None,
        reversed_invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        status="issued",
        issue_date=date.today(),
        due_date=date.today(),
        notes=reason,
        subtotal=invoice.subtotal,
        discount_amount=invoice.discount_amount,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        paid_amount=Decimal("0.00"),
        created_by=actor_id,
        issued_by=actor_id,
        issued_at=_now(),
        items=[
            InvoiceItem(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
            )
            for item in invoice.items
        ],
    )
    db.add(credit_note)
    db.flush()
    post_entry(
        db,
        entry_date=date.today(),
        description=f"Reversal {credit_note.number} for {invoice.number}",
        source_type="credit_note",
        source_id=credit_note.id,
        actor_id=actor_id,
        lines=[
            ("4000", invoice.total_amount, Decimal("0"), invoice.customer.name),
            ("1200", Decimal("0"), invoice.total_amount, invoice.customer.name),
        ],
    )
    invoice.status = "cancelled"
    invoice.cancelled_by = actor_id
    invoice.cancelled_at = _now()
    invoice.cancellation_reason = reason
    add_audit_log(
        db,
        user_id=actor_id,
        action="cancel",
        table_name="invoices",
        record_id=invoice.id,
        ip_address=ip_address,
        old_values={"status": old},
        new_values={
            "status": "cancelled",
            "reason": reason,
            "credit_note_id": credit_note.id,
            "credit_note_number": credit_note.number,
        },
    )
    _commit(db)
    return _get(db, invoice.id)


def record_payment(
    db: Session, invoice_id: int, data: PaymentCreate, *, actor_id: int, ip_address: str | None
) -> Invoice:
    invoice = _get(db, invoice_id, lock=True)
    if invoice.document_type != "invoice":
        raise InvoiceStateError("Payments cannot be posted to credit notes.")
    if invoice.status not in {"issued", "partially_paid"}:
        raise InvoiceStateError("Payments can only be posted to issued or partially paid invoices.")
    balance = invoice.total_amount - invoice.paid_amount
    if data.amount > balance:
        raise InvoiceStateError(f"Payment exceeds the remaining balance of {balance:.2f} JOD.")
    payment = Payment(
        number=f"PAY-{uuid4().hex[:12].upper()}",
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        amount=data.amount,
        payment_date=data.payment_date,
        method=data.method,
        reference=data.reference,
        notes=data.notes,
        status="posted",
        created_by=actor_id,
    )
    db.add(payment)
    db.flush()
    cash_code = "1000" if data.method == "cash" else "1100"
    post_entry(
        db,
        entry_date=data.payment_date,
        description=f"Customer payment {payment.number}",
        source_type="customer_payment",
        source_id=payment.id,
        actor_id=actor_id,
        lines=[
            (cash_code, data.amount, Decimal("0"), invoice.customer.name),
            ("1200", Decimal("0"), data.amount, invoice.customer.name),
        ],
    )
    invoice.paid_amount += data.amount
    invoice.status = _status_for(invoice)
    add_audit_log(
        db,
        user_id=actor_id,
        action="payment_post",
        table_name="payments",
        record_id=payment.id,
        ip_address=ip_address,
        new_values={
            "number": payment.number,
            "invoice_id": invoice.id,
            "amount": f"{payment.amount:.2f}",
            "method": payment.method,
        },
    )
    _commit(db)
    return _get(db, invoice.id)


def record_customer_payment(
    db: Session, data: CustomerPaymentCreate, *, actor_id: int, ip_address: str | None
) -> Payment:
    customer = db.get(Customer, data.customer_id)
    if customer is None or not customer.is_active:
        raise InvoiceStateError("Customer is unavailable.")
    if sum((row.amount for row in data.allocations), Decimal("0")) > data.amount:
        raise InvoiceStateError("Allocated amount cannot exceed the payment amount.")
    invoice_ids = [row.invoice_id for row in data.allocations]
    if len(invoice_ids) != len(set(invoice_ids)):
        raise InvoiceStateError("Each invoice may only be allocated once per payment.")
    invoices = {}
    for allocation in sorted(data.allocations, key=lambda row: row.invoice_id):
        invoice = _get(db, allocation.invoice_id, lock=True)
        if invoice.customer_id != customer.id or invoice.status not in {"issued", "partially_paid"}:
            raise InvoiceStateError(
                "Allocations require an open invoice for the selected customer."
            )
        balance = invoice.total_amount - invoice.paid_amount
        if allocation.amount > balance:
            raise InvoiceStateError(
                f"Allocation exceeds {invoice.number}'s balance of {balance:.2f} JOD."
            )
        invoices[invoice.id] = invoice
    payment = Payment(
        number=f"PAY-{uuid4().hex[:12].upper()}",
        invoice_id=None,
        customer_id=customer.id,
        amount=data.amount,
        payment_date=data.payment_date,
        method=data.method,
        reference=data.reference,
        notes=data.notes,
        status="posted",
        created_by=actor_id,
        allocations=[
            PaymentAllocation(invoice_id=row.invoice_id, allocated_amount=row.amount)
            for row in data.allocations
        ],
    )
    db.add(payment)
    db.flush()
    for allocation in data.allocations:
        invoice = invoices[allocation.invoice_id]
        invoice.paid_amount += allocation.amount
        invoice.status = _status_for(invoice)
    cash_code = "1000" if data.method == "cash" else "1100"
    post_entry(
        db,
        entry_date=data.payment_date,
        description=f"Customer payment {payment.number}",
        source_type="customer_payment",
        source_id=payment.id,
        actor_id=actor_id,
        lines=[
            (cash_code, data.amount, Decimal("0"), customer.name),
            ("1200", Decimal("0"), data.amount, customer.name),
        ],
    )
    add_audit_log(
        db,
        user_id=actor_id,
        action="payment_post",
        table_name="payments",
        record_id=payment.id,
        ip_address=ip_address,
        new_values={
            "customer_id": customer.id,
            "amount": f"{payment.amount:.2f}",
            "allocations": [
                {"invoice_id": row.invoice_id, "amount": f"{row.amount:.2f}"}
                for row in data.allocations
            ],
        },
    )
    _commit(db)
    saved = repository.get_payment(db, payment.id)
    if saved is None:
        raise PaymentNotFoundError(payment.id)
    return saved


def reverse_payment(
    db: Session, payment_id: int, reason: str, *, actor_id: int, ip_address: str | None
) -> Invoice:
    payment = repository.get_payment(db, payment_id, lock=True)
    if payment is None:
        raise PaymentNotFoundError(payment_id)
    if payment.status != "posted":
        raise InvoiceStateError("Only posted payments can be reversed.")
    if payment.invoice_id is None:
        raise InvoiceStateError("Use the allocated-payment reversal workflow for this receipt.")
    invoice = _get(db, payment.invoice_id, lock=True)
    if invoice.status == "cancelled":
        raise InvoiceStateError("Payments on cancelled invoices cannot be changed.")
    payment.status = "reversed"
    payment.reversed_by = actor_id
    payment.reversed_at = _now()
    payment.reversal_reason = reason
    invoice.paid_amount -= payment.amount
    invoice.status = _status_for(invoice)
    cash_code = "1000" if payment.method == "cash" else "1100"
    post_entry(
        db,
        entry_date=date.today(),
        description=f"Reverse customer payment {payment.number}",
        source_type="customer_payment_reversal",
        source_id=payment.id,
        actor_id=actor_id,
        lines=[
            ("1200", payment.amount, Decimal("0"), invoice.customer.name),
            (cash_code, Decimal("0"), payment.amount, invoice.customer.name),
        ],
    )
    add_audit_log(
        db,
        user_id=actor_id,
        action="payment_reverse",
        table_name="payments",
        record_id=payment.id,
        ip_address=ip_address,
        old_values={"status": "posted"},
        new_values={"status": "reversed", "reason": reason, "invoice_id": invoice.id},
    )
    _commit(db)
    return _get(db, invoice.id)


def reverse_customer_payment(
    db: Session, payment_id: int, reason: str, *, actor_id: int, ip_address: str | None
) -> Payment:
    payment = repository.get_payment(db, payment_id, lock=True)
    if payment is None:
        raise PaymentNotFoundError(payment_id)
    if payment.status != "posted":
        raise InvoiceStateError("Only posted payments can be reversed.")
    if payment.invoice_id is not None:
        raise InvoiceStateError("Use the invoice payment reversal action for this payment.")

    customer = db.get(Customer, payment.customer_id)
    if customer is None:
        raise InvoiceStateError("Payment customer is unavailable.")
    for allocation in sorted(payment.allocations, key=lambda row: row.invoice_id):
        invoice = _get(db, allocation.invoice_id, lock=True)
        if invoice.status == "cancelled":
            raise InvoiceStateError("Payments on cancelled invoices cannot be changed.")
        if invoice.paid_amount < allocation.allocated_amount:
            raise InvoiceStateError("Invoice payment history is inconsistent.")
        invoice.paid_amount -= allocation.allocated_amount
        invoice.status = _status_for(invoice)

    payment.status = "reversed"
    payment.reversed_by = actor_id
    payment.reversed_at = _now()
    payment.reversal_reason = reason
    cash_code = "1000" if payment.method == "cash" else "1100"
    post_entry(
        db,
        entry_date=date.today(),
        description=f"Reverse customer payment {payment.number}",
        source_type="customer_payment_reversal",
        source_id=payment.id,
        actor_id=actor_id,
        lines=[
            ("1200", payment.amount, Decimal("0"), customer.name),
            (cash_code, Decimal("0"), payment.amount, customer.name),
        ],
    )
    add_audit_log(
        db,
        user_id=actor_id,
        action="payment_reverse",
        table_name="payments",
        record_id=payment.id,
        ip_address=ip_address,
        old_values={"status": "posted"},
        new_values={"status": "reversed", "reason": reason},
    )
    _commit(db)
    saved = repository.get_payment(db, payment.id)
    if saved is None:
        raise PaymentNotFoundError(payment.id)
    return saved
