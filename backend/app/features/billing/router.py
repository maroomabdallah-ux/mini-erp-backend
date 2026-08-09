from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.billing import service
from app.features.billing.schemas import (
    CustomerPaymentCreate,
    InvoiceCreate,
    InvoiceListResponse,
    InvoiceResponse,
    PaymentCreate,
    PaymentResponse,
    ReasonPayload,
    SalesOrderSummary,
)
from app.features.users.model import User

router = APIRouter(tags=["Invoices and Payments"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/invoices", response_model=InvoiceListResponse)
def list_invoices(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    status_filter: Literal["draft", "issued", "partially_paid", "paid", "cancelled"] | None = Query(
        None, alias="status"
    ),
    customer_id: int | None = Query(None, gt=0),
    overdue: bool = False,
    actor: User = Depends(require_permission("invoices.read")),
):
    return service.list_invoices(
        db,
        page=page,
        size=size,
        search=search,
        status=status_filter,
        customer_id=customer_id,
        overdue=overdue,
    )


@router.get("/invoices/eligible-orders", response_model=list[SalesOrderSummary])
def eligible_orders(
    db: DatabaseSession, actor: User = Depends(require_permission("invoices.create"))
):
    return service.eligible_orders(db)


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int, db: DatabaseSession, actor: User = Depends(require_permission("invoices.read"))
):
    return service.get_invoice(db, invoice_id)


@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    data: InvoiceCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("invoices.create")),
):
    return service.create_invoice(db, data, actor_id=actor.id, ip_address=_ip(request))


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceResponse)
def issue_invoice(
    invoice_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("invoices.create")),
):
    return service.issue_invoice(db, invoice_id, actor_id=actor.id, ip_address=_ip(request))


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceResponse)
def cancel_invoice(
    invoice_id: int,
    data: ReasonPayload,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("invoices.cancel")),
):
    return service.cancel_invoice(
        db, invoice_id, data.reason, actor_id=actor.id, ip_address=_ip(request)
    )


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_payment(
    invoice_id: int,
    data: PaymentCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("payments.create")),
):
    return service.record_payment(db, invoice_id, data, actor_id=actor.id, ip_address=_ip(request))


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def record_customer_payment(
    data: CustomerPaymentCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("payments.create")),
):
    return service.record_customer_payment(db, data, actor_id=actor.id, ip_address=_ip(request))


@router.post("/payments/{payment_id}/reverse", response_model=InvoiceResponse)
def reverse_payment(
    payment_id: int,
    data: ReasonPayload,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("payments.create")),
):
    return service.reverse_payment(
        db, payment_id, data.reason, actor_id=actor.id, ip_address=_ip(request)
    )


@router.post("/customer-payments/{payment_id}/reverse", response_model=PaymentResponse)
def reverse_customer_payment(
    payment_id: int,
    data: ReasonPayload,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("payments.create")),
):
    return service.reverse_customer_payment(
        db, payment_id, data.reason, actor_id=actor.id, ip_address=_ip(request)
    )
