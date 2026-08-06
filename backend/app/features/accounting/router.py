from datetime import date

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.accounting import service
from app.features.accounting.schemas import (
    AccountingDashboardResponse,
    AccountInput,
    AccountResponse,
    JournalEntryCreate,
    JournalEntryListResponse,
    JournalEntryResponse,
    ReasonPayload,
    SalesSettings,
    StatementResponse,
    SupplierOutstandingResponse,
    SupplierPaymentCreate,
    SupplierPaymentResponse,
    TimelineEvent,
)
from app.features.users.model import User

router = APIRouter(tags=["Accounting"])


@router.get("/system-settings/sales", response_model=SalesSettings)
def get_sales_settings(
    db: DatabaseSession,
    actor: User = Depends(require_permission("sales_orders.read")),
):
    return {"credit_limit_behavior": service.credit_limit_behavior(db)}


@router.put("/system-settings/sales", response_model=SalesSettings)
def update_sales_settings(
    data: SalesSettings,
    db: DatabaseSession,
    actor: User = Depends(require_permission("accounts.manage")),
):
    return service.update_credit_limit_behavior(db, data.credit_limit_behavior, actor.id)


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(
    db: DatabaseSession,
    active_only: bool = False,
    actor: User = Depends(require_permission("accounts.read")),
):
    return service.list_accounts(db, active_only)


@router.get("/accounting/dashboard", response_model=AccountingDashboardResponse)
def dashboard(
    db: DatabaseSession,
    actor: User = Depends(require_permission("accounts.read")),
):
    return service.accounting_dashboard(db)


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    data: AccountInput,
    db: DatabaseSession,
    actor: User = Depends(require_permission("accounts.manage")),
):
    return service.create_account(db, data, actor_id=actor.id)


@router.put("/accounts/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: int,
    data: AccountInput,
    db: DatabaseSession,
    actor: User = Depends(require_permission("accounts.manage")),
):
    return service.update_account(db, account_id, data)


@router.delete("/accounts/{account_id}", response_model=AccountResponse)
def deactivate_account(
    account_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("accounts.manage")),
):
    return service.deactivate_account(db, account_id)


@router.get("/journal-entries", response_model=JournalEntryListResponse)
def list_entries(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    account_id: int | None = Query(None, gt=0),
    source_type: str | None = Query(None, max_length=50),
    actor: User = Depends(require_permission("journal_entries.read")),
):
    return service.list_entries(
        db,
        page=page,
        size=size,
        search=search,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        source_type=source_type,
    )


@router.get("/journal-entries/{entry_id}", response_model=JournalEntryResponse)
def get_entry(
    entry_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("journal_entries.read")),
):
    return service.get_entry(db, entry_id)


@router.post(
    "/journal-entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED
)
def create_entry(
    data: JournalEntryCreate,
    db: DatabaseSession,
    actor: User = Depends(require_permission("accounts.manage")),
):
    return service.create_manual_entry(db, data, actor_id=actor.id)


@router.get("/supplier-payments", response_model=list[SupplierPaymentResponse])
def list_supplier_payments(
    db: DatabaseSession,
    supplier_id: int | None = Query(None, gt=0),
    actor: User = Depends(require_permission("payments.read")),
):
    return service.repository.list_supplier_payments(db, supplier_id)


@router.get("/supplier-outstanding", response_model=list[SupplierOutstandingResponse])
def supplier_outstanding(
    db: DatabaseSession,
    supplier_id: int | None = Query(None, gt=0),
    actor: User = Depends(require_permission("payments.read")),
):
    return service.supplier_outstanding(db, supplier_id)


@router.get("/invoices/{invoice_id}/accounting-timeline", response_model=list[TimelineEvent])
def invoice_timeline(
    invoice_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("invoices.read")),
):
    return service.invoice_timeline(db, invoice_id)


@router.post(
    "/supplier-payments",
    response_model=SupplierPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_supplier_payment(
    data: SupplierPaymentCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("payments.create")),
):
    return service.record_supplier_payment(
        db,
        data,
        actor_id=actor.id,
        ip_address=request.client.host if request.client else None,
    )


@router.post("/supplier-payments/{payment_id}/reverse", response_model=SupplierPaymentResponse)
def reverse_supplier_payment(
    payment_id: int,
    data: ReasonPayload,
    db: DatabaseSession,
    actor: User = Depends(require_permission("payments.create")),
):
    return service.reverse_supplier_payment(db, payment_id, data.reason.strip(), actor_id=actor.id)


@router.get("/accounting/customer-statement/{customer_id}", response_model=StatementResponse)
def customer_statement(
    customer_id: int,
    db: DatabaseSession,
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    actor: User = Depends(require_permission("customer_statements.read")),
):
    return service.customer_statement(db, customer_id, date_from, date_to)


@router.get("/accounting/supplier-statement/{supplier_id}", response_model=StatementResponse)
def supplier_statement(
    supplier_id: int,
    db: DatabaseSession,
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    actor: User = Depends(require_permission("supplier_statements.read")),
):
    return service.supplier_statement(db, supplier_id, date_from, date_to)
