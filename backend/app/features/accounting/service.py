from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.accounting import repository
from app.features.accounting.exceptions import (
    AccountingConflictError,
    AccountingRuleError,
    AccountNotFoundError,
)
from app.features.accounting.models import (
    Account,
    JournalEntry,
    JournalEntryLine,
    SupplierPayment,
    SystemSetting,
)
from app.features.accounting.schemas import (
    AccountInput,
    JournalEntryCreate,
    SupplierPaymentCreate,
)
from app.features.audit.service import add_audit_log
from app.features.billing.models import Invoice, Payment
from app.features.customers.models import Customer
from app.features.purchases.models import GoodsReceipt, PurchaseOrder
from app.features.suppliers.models import Supplier

SYSTEM_ACCOUNTS = {
    "1000": ("Cash", "asset"),
    "1100": ("Bank", "asset"),
    "1200": ("Accounts Receivable", "asset"),
    "1300": ("Inventory", "asset"),
    "2000": ("Accounts Payable", "liability"),
    "3000": ("Owner Equity", "equity"),
    "4000": ("Sales Revenue", "revenue"),
    "5000": ("Cost of Goods Sold", "expense"),
}


def ensure_system_accounts(db: Session) -> None:
    for code, (name, account_type) in SYSTEM_ACCOUNTS.items():
        if repository.get_account_by_code(db, code) is None:
            db.add(Account(code=code, name=name, type=account_type, is_system=True))
    db.flush()


def credit_limit_behavior(db: Session) -> str:
    setting = db.get(SystemSetting, "credit_limit_behavior")
    return setting.value if setting else "block"


def update_credit_limit_behavior(db: Session, value: str, actor_id: int) -> dict:
    setting = db.get(SystemSetting, "credit_limit_behavior")
    if setting is None:
        setting = SystemSetting(key="credit_limit_behavior", value=value, updated_by=actor_id)
        db.add(setting)
    else:
        setting.value = value
        setting.updated_by = actor_id
    db.commit()
    return {"credit_limit_behavior": value}


def list_accounts(db: Session, active_only: bool = False) -> list[Account]:
    ensure_system_accounts(db)
    db.commit()
    return repository.list_accounts(db, active_only=active_only)


def create_account(db: Session, data: AccountInput, *, actor_id: int) -> Account:
    if repository.get_account_by_code(db, data.code):
        raise AccountingConflictError(f"Account code {data.code} already exists.")
    if data.parent_id:
        parent = repository.get_account(db, data.parent_id)
        if parent is None:
            raise AccountNotFoundError("Parent account was not found.")
        if parent.type != data.type:
            raise AccountingRuleError("Parent and child accounts must have the same type.")
    account = Account(**data.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_account(db: Session, account_id: int, data: AccountInput) -> Account:
    account = repository.get_account(db, account_id)
    if account is None:
        raise AccountNotFoundError("Account was not found.")
    if account.is_system and (
        data.code != account.code
        or data.type != account.type
        or data.parent_id != account.parent_id
    ):
        raise AccountingRuleError("System account code, type, and hierarchy cannot be changed.")
    duplicate = repository.get_account_by_code(db, data.code)
    if duplicate and duplicate.id != account.id:
        raise AccountingConflictError(f"Account code {data.code} already exists.")
    for key, value in data.model_dump().items():
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return account


def deactivate_account(db: Session, account_id: int) -> Account:
    account = repository.get_account(db, account_id)
    if account is None:
        raise AccountNotFoundError("Account was not found.")
    if account.is_system:
        raise AccountingRuleError("System accounts cannot be deactivated.")
    account.is_active = False
    db.commit()
    db.refresh(account)
    return account


def post_entry(
    db: Session,
    *,
    entry_date: date,
    description: str,
    source_type: str,
    source_id: int,
    lines: list[tuple[str, Decimal, Decimal, str | None]],
    actor_id: int,
) -> JournalEntry:
    existing = repository.get_entry_by_source(db, source_type, source_id)
    if existing:
        return existing
    ensure_system_accounts(db)
    debit = sum((line[1] for line in lines), Decimal("0"))
    credit = sum((line[2] for line in lines), Decimal("0"))
    if debit <= 0 or debit != credit:
        raise AccountingRuleError("Journal entry debits and credits must be equal and positive.")
    entry = JournalEntry(
        number=f"JE-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        entry_date=entry_date,
        description=description,
        source_type=source_type,
        source_id=source_id,
        created_by=actor_id,
        lines=[
            JournalEntryLine(
                account_id=repository.get_account_by_code(db, code).id,
                debit=debit_amount,
                credit=credit_amount,
                memo=memo,
            )
            for code, debit_amount, credit_amount, memo in lines
        ],
    )
    db.add(entry)
    db.flush()
    return entry


def create_manual_entry(db: Session, data: JournalEntryCreate, *, actor_id: int) -> JournalEntry:
    for line in data.lines:
        account = repository.get_account(db, line.account_id)
        if account is None or not account.is_active:
            raise AccountingRuleError(f"Account {line.account_id} is unavailable.")
    entry = JournalEntry(
        number=f"JE-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        entry_date=data.entry_date,
        description=data.description.strip(),
        created_by=actor_id,
        lines=[JournalEntryLine(**line.model_dump()) for line in data.lines],
    )
    db.add(entry)
    db.commit()
    saved = repository.list_entries(db, offset=0, limit=1, search=entry.number)[0]
    return _entry_response(db, saved)


def _source_details(db: Session, entry: JournalEntry) -> tuple[str, str | None, int | None]:
    if not entry.source_type or not entry.source_id:
        return "Manual journal entry", None, None
    if entry.source_type in {"sales_invoice", "credit_note"}:
        invoice = db.get(Invoice, entry.source_id)
        return (invoice.number if invoice else "Invoice", "billing", entry.source_id)
    if entry.source_type in {"customer_payment", "customer_payment_reversal"}:
        payment = db.get(Payment, entry.source_id)
        return (
            payment.number if payment else "Customer payment",
            "billing",
            payment.invoice_id if payment else None,
        )
    if entry.source_type == "goods_receipt":
        receipt = db.get(GoodsReceipt, entry.source_id)
        return (
            receipt.number if receipt else "Goods receipt",
            "purchases",
            receipt.purchase_order_id if receipt else None,
        )
    if entry.source_type in {"supplier_payment", "supplier_payment_reversal"}:
        payment = db.get(SupplierPayment, entry.source_id)
        return (payment.number if payment else "Supplier payment", "accounting", entry.source_id)
    return (entry.source_type.replace("_", " ").title(), None, entry.source_id)


def _entry_response(db: Session, entry: JournalEntry) -> dict:
    reference, route, document_id = _source_details(db, entry)
    return {
        "id": entry.id,
        "number": entry.number,
        "entry_date": entry.entry_date,
        "description": entry.description,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "source_reference": reference,
        "source_route": route,
        "source_document_id": document_id,
        "total_amount": sum((line.debit for line in entry.lines), Decimal("0")),
        "created_by": entry.created_by,
        "created_at": entry.created_at,
        "lines": entry.lines,
    }


def get_entry(db: Session, entry_id: int) -> dict:
    entry = repository.get_entry(db, entry_id)
    if entry is None:
        raise AccountingRuleError("Journal entry was not found.")
    return _entry_response(db, entry)


def list_entries(
    db: Session,
    *,
    page: int,
    size: int,
    search: str | None,
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: int | None = None,
    source_type: str | None = None,
) -> dict:
    entries = repository.list_entries(
        db,
        offset=(page - 1) * size,
        limit=size,
        search=search,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        source_type=source_type,
    )
    return {
        "items": [_entry_response(db, entry) for entry in entries],
        "page": page,
        "size": size,
        "total": repository.count_entries(
            db,
            search=search,
            date_from=date_from,
            date_to=date_to,
            account_id=account_id,
            source_type=source_type,
        ),
    }


def accounting_dashboard(db: Session) -> dict:
    ensure_system_accounts(db)

    def balance(code: str, *, date_from: date | None = None) -> Decimal:
        statement = (
            select(
                func.coalesce(func.sum(JournalEntryLine.debit), 0),
                func.coalesce(func.sum(JournalEntryLine.credit), 0),
            )
            .join(JournalEntry)
            .join(Account)
            .where(Account.code == code)
        )
        if date_from:
            statement = statement.where(JournalEntry.entry_date >= date_from)
        debit, credit = db.execute(statement).one()
        account = repository.get_account_by_code(db, code)
        return (
            Decimal(credit) - Decimal(debit)
            if account.type in {"liability", "equity", "revenue"}
            else Decimal(debit) - Decimal(credit)
        )

    month_start = date.today().replace(day=1)
    revenue = balance("4000", date_from=month_start)
    expenses = balance("5000", date_from=month_start)
    return {
        "cash": balance("1000"),
        "bank": balance("1100"),
        "accounts_receivable": balance("1200"),
        "accounts_payable": balance("2000"),
        "inventory_value": balance("1300"),
        "profit_this_month": revenue - expenses,
    }


def supplier_outstanding(db: Session, supplier_id: int | None = None) -> list[dict]:
    statement = select(PurchaseOrder).where(PurchaseOrder.status == "received")
    if supplier_id:
        statement = statement.where(PurchaseOrder.supplier_id == supplier_id)
    orders = db.scalars(statement.order_by(PurchaseOrder.created_at.desc())).all()
    result = []
    for order in orders:
        paid = db.scalar(
            select(func.coalesce(func.sum(SupplierPayment.amount), 0)).where(
                SupplierPayment.purchase_order_id == order.id,
                SupplierPayment.status == "posted",
            )
        ) or Decimal("0")
        result.append(
            {
                "purchase_order_id": order.id,
                "purchase_order_number": order.number,
                "supplier_id": order.supplier_id,
                "supplier_name": order.supplier.name,
                "total_amount": order.total_amount,
                "paid_amount": paid,
                "remaining_amount": order.total_amount - paid,
            }
        )
    return result


def invoice_timeline(db: Session, invoice_id: int) -> list[dict]:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise AccountingRuleError("Invoice was not found.")
    events = [
        {
            "key": "invoice_created",
            "label": "Invoice created",
            "occurred_at": invoice.created_at,
            "reference": invoice.number,
            "route": "billing",
            "document_id": invoice.id,
        }
    ]
    issue_entry = repository.get_entry_by_source(db, "sales_invoice", invoice.id)
    if issue_entry:
        events.append(
            {
                "key": "invoice_journal",
                "label": "Invoice journal posted",
                "occurred_at": issue_entry.created_at,
                "reference": issue_entry.number,
                "route": "accounting",
                "document_id": issue_entry.id,
            }
        )
    for payment in invoice.payments:
        events.append(
            {
                "key": f"payment_{payment.id}",
                "label": "Customer paid" if payment.status == "posted" else "Payment reversed",
                "occurred_at": payment.created_at,
                "reference": payment.number,
                "route": "billing",
                "document_id": invoice.id,
            }
        )
        payment_entry = repository.get_entry_by_source(db, "customer_payment", payment.id)
        if payment_entry:
            events.append(
                {
                    "key": f"payment_journal_{payment.id}",
                    "label": "Payment journal posted",
                    "occurred_at": payment_entry.created_at,
                    "reference": payment_entry.number,
                    "route": "accounting",
                    "document_id": payment_entry.id,
                }
            )
    return sorted(events, key=lambda event: event["occurred_at"])


def record_supplier_payment(
    db: Session, data: SupplierPaymentCreate, *, actor_id: int, ip_address: str | None
) -> SupplierPayment:
    supplier = db.get(Supplier, data.supplier_id)
    if supplier is None or not supplier.is_active:
        raise AccountingRuleError("Supplier is unavailable.")
    if data.purchase_order_id:
        order = db.get(PurchaseOrder, data.purchase_order_id)
        if order is None or order.supplier_id != supplier.id or order.status != "received":
            raise AccountingRuleError(
                "Payment requires a received purchase order for this supplier."
            )
        paid = sum(
            db.scalars(
                select(SupplierPayment.amount).where(
                    SupplierPayment.purchase_order_id == order.id,
                    SupplierPayment.status == "posted",
                )
            ).all(),
            Decimal("0"),
        )
        if paid + data.amount > order.total_amount:
            raise AccountingRuleError("Supplier payment exceeds the purchase order balance.")
    payment = SupplierPayment(
        number=f"SPAY-{uuid4().hex[:12].upper()}",
        created_by=actor_id,
        **data.model_dump(),
    )
    db.add(payment)
    db.flush()
    cash_code = "1000" if data.method == "cash" else "1100"
    post_entry(
        db,
        entry_date=data.payment_date,
        description=f"Supplier payment {payment.number}",
        source_type="supplier_payment",
        source_id=payment.id,
        actor_id=actor_id,
        lines=[
            ("2000", data.amount, Decimal("0"), supplier.name),
            (cash_code, Decimal("0"), data.amount, supplier.name),
        ],
    )
    add_audit_log(
        db,
        user_id=actor_id,
        action="supplier_payment_post",
        table_name="supplier_payments",
        record_id=payment.id,
        ip_address=ip_address,
        new_values={"number": payment.number, "amount": f"{payment.amount:.2f}"},
    )
    db.commit()
    db.refresh(payment)
    return payment


def reverse_supplier_payment(
    db: Session, payment_id: int, reason: str, *, actor_id: int
) -> SupplierPayment:
    payment = db.get(SupplierPayment, payment_id)
    if payment is None:
        raise AccountingRuleError("Supplier payment was not found.")
    if payment.status != "posted":
        raise AccountingRuleError("Only posted supplier payments can be reversed.")
    payment.status = "reversed"
    payment.reversed_by = actor_id
    payment.reversed_at = datetime.now(UTC)
    payment.reversal_reason = reason
    cash_code = "1000" if payment.method == "cash" else "1100"
    post_entry(
        db,
        entry_date=date.today(),
        description=f"Reverse supplier payment {payment.number}",
        source_type="supplier_payment_reversal",
        source_id=payment.id,
        actor_id=actor_id,
        lines=[
            (cash_code, payment.amount, Decimal("0"), payment.supplier.name),
            ("2000", Decimal("0"), payment.amount, payment.supplier.name),
        ],
    )
    db.commit()
    db.refresh(payment)
    return payment


def _statement(records, *, entity_id: int, entity_name: str, date_from: date, date_to: date):
    opening = sum(
        (debit - credit for event_date, _, _, debit, credit in records if event_date < date_from),
        Decimal("0"),
    )
    balance = opening
    lines = []
    for event_date, reference, description, debit, credit in sorted(
        records, key=lambda row: row[0]
    ):
        if not date_from <= event_date <= date_to:
            continue
        balance += debit - credit
        lines.append(
            {
                "date": event_date,
                "reference": reference,
                "description": description,
                "debit": debit,
                "credit": credit,
                "balance": balance,
            }
        )
    return {
        "entity_id": entity_id,
        "entity_name": entity_name,
        "date_from": date_from,
        "date_to": date_to,
        "opening_balance": opening,
        "closing_balance": balance,
        "lines": lines,
    }


def customer_statement(db: Session, customer_id: int, date_from: date, date_to: date):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise AccountingRuleError("Customer was not found.")
    records = []
    invoices = db.scalars(
        select(Invoice).where(
            Invoice.customer_id == customer_id,
            Invoice.issue_date.is_not(None),
            Invoice.issue_date <= date_to,
        )
    ).all()
    for invoice in invoices:
        if invoice.document_type == "credit_note":
            records.append(
                (
                    invoice.issue_date,
                    invoice.number,
                    "Credit note",
                    Decimal("0"),
                    invoice.total_amount,
                )
            )
        else:
            records.append(
                (
                    invoice.issue_date,
                    invoice.number,
                    "Sales invoice",
                    invoice.total_amount,
                    Decimal("0"),
                )
            )
        for payment in invoice.payments:
            if payment.status == "posted" and payment.payment_date <= date_to:
                records.append(
                    (
                        payment.payment_date,
                        payment.number,
                        "Customer payment",
                        Decimal("0"),
                        payment.amount,
                    )
                )
    return _statement(
        records,
        entity_id=customer.id,
        entity_name=customer.name,
        date_from=date_from,
        date_to=date_to,
    )


def supplier_statement(db: Session, supplier_id: int, date_from: date, date_to: date):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise AccountingRuleError("Supplier was not found.")
    records = []
    receipts = db.scalars(
        select(GoodsReceipt)
        .join(PurchaseOrder)
        .where(
            PurchaseOrder.supplier_id == supplier_id,
            GoodsReceipt.received_at <= datetime.combine(date_to, datetime.max.time(), tzinfo=UTC),
        )
    ).all()
    for receipt in receipts:
        records.append(
            (
                receipt.received_at.date(),
                receipt.number,
                "Goods receipt",
                receipt.purchase_order.total_amount,
                Decimal("0"),
            )
        )
    for payment in repository.list_supplier_payments(db, supplier_id):
        if payment.status == "posted" and payment.payment_date <= date_to:
            records.append(
                (
                    payment.payment_date,
                    payment.number,
                    "Supplier payment",
                    Decimal("0"),
                    payment.amount,
                )
            )
    return _statement(
        records,
        entity_id=supplier.id,
        entity_name=supplier.name,
        date_from=date_from,
        date_to=date_to,
    )
