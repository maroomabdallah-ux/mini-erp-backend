from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.sales import service
from app.features.sales.schemas import (
    SalesDeliveryCreate,
    SalesOrderConfirm,
    SalesOrderCreate,
    SalesOrderListResponse,
    SalesOrderReason,
    SalesOrderResponse,
    WarehouseAvailability,
)
from app.features.users.model import User

router = APIRouter(tags=["Sales Orders"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/sales-orders", response_model=SalesOrderListResponse)
def list_orders(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    status_filter: Literal["draft", "confirmed", "delivered", "cancelled"] | None = Query(
        default=None, alias="status"
    ),
    customer_id: int | None = Query(default=None, gt=0),
    actor: User = Depends(require_permission("sales_orders.read")),
):
    return service.list_orders(
        db, page=page, size=size, search=search, status=status_filter, customer_id=customer_id
    )


@router.get("/sales-orders/{order_id}", response_model=SalesOrderResponse)
def get_order(
    order_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("sales_orders.read")),
):
    return service.get_order(db, order_id)


@router.post(
    "/sales-orders", response_model=SalesOrderResponse, status_code=status.HTTP_201_CREATED
)
def create_order(
    data: SalesOrderCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("sales_orders.create")),
):
    return service.create_order(db, data, actor_id=actor.id, ip_address=_ip(request))


@router.get("/sales-orders/{order_id}/availability", response_model=list[WarehouseAvailability])
def get_availability(
    order_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("sales_orders.read")),
):
    return service.availability(db, order_id)


@router.post(
    "/quotations/{quotation_id}/convert",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def convert_quotation(
    quotation_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("sales_orders.create")),
):
    return service.convert_quotation(db, quotation_id, actor_id=actor.id, ip_address=_ip(request))


@router.post("/sales-orders/{order_id}/confirm", response_model=SalesOrderResponse)
def confirm_order(
    order_id: int,
    data: SalesOrderConfirm,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("sales_orders.confirm")),
):
    return service.confirm_order(db, order_id, data, actor_id=actor.id, ip_address=_ip(request))


@router.post("/sales-orders/{order_id}/cancel", response_model=SalesOrderResponse)
def cancel_order(
    order_id: int,
    data: SalesOrderReason,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("sales_orders.update")),
):
    return service.cancel_order(
        db, order_id, data.reason, actor_id=actor.id, ip_address=_ip(request)
    )


@router.post(
    "/sales-orders/{order_id}/deliver",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def deliver_order(
    order_id: int,
    data: SalesDeliveryCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("sales_orders.deliver")),
):
    return service.deliver_order(db, order_id, data, actor_id=actor.id, ip_address=_ip(request))
