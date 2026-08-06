from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.quotations import service
from app.features.quotations.schemas import (
    QuotationCreate,
    QuotationListResponse,
    QuotationReason,
    QuotationResponse,
    QuotationUpdate,
)
from app.features.users.model import User

router = APIRouter(prefix="/quotations", tags=["Sales Quotations"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=QuotationListResponse)
def list_quotations(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    status_filter: Literal["draft", "sent", "accepted", "rejected", "expired", "converted"]
    | None = Query(default=None, alias="status"),
    customer_id: int | None = Query(default=None, gt=0),
    actor: User = Depends(require_permission("quotations.read")),
):
    return service.list_quotations(
        db, page=page, size=size, search=search, status=status_filter, customer_id=customer_id
    )


@router.get("/{quotation_id}", response_model=QuotationResponse)
def get_quotation(
    quotation_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("quotations.read")),
):
    return service.get_quotation(db, quotation_id)


@router.post("", response_model=QuotationResponse, status_code=status.HTTP_201_CREATED)
def create_quotation(
    data: QuotationCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("quotations.manage")),
):
    return service.create_quotation(db, data, actor_id=actor.id, ip_address=_ip(request))


@router.put("/{quotation_id}", response_model=QuotationResponse)
def update_quotation(
    quotation_id: int,
    data: QuotationUpdate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("quotations.manage")),
):
    return service.update_quotation(
        db, quotation_id, data, actor_id=actor.id, ip_address=_ip(request)
    )


def _transition(
    quotation_id: int,
    action: str,
    request: Request,
    db: DatabaseSession,
    actor: User,
    reason: str | None = None,
):
    return service.transition(
        db, quotation_id, action, actor_id=actor.id, ip_address=_ip(request), reason=reason
    )


@router.post("/{quotation_id}/send", response_model=QuotationResponse)
def send_quotation(
    quotation_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("quotations.manage")),
):
    return _transition(quotation_id, "send", request, db, actor)


@router.post("/{quotation_id}/accept", response_model=QuotationResponse)
def accept_quotation(
    quotation_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("quotations.manage")),
):
    return _transition(quotation_id, "accept", request, db, actor)


@router.post("/{quotation_id}/reject", response_model=QuotationResponse)
def reject_quotation(
    quotation_id: int,
    data: QuotationReason,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("quotations.manage")),
):
    return _transition(quotation_id, "reject", request, db, actor, data.reason)


@router.post("/{quotation_id}/expire", response_model=QuotationResponse)
def expire_quotation(
    quotation_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("quotations.manage")),
):
    return _transition(quotation_id, "expire", request, db, actor)
