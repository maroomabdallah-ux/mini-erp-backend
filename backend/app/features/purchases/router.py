from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.purchases import service
from app.features.purchases.schemas import (
    GoodsReceiptCreate,
    GoodsReceiptListResponse,
    GoodsReceiptResponse,
    PurchaseOrderCreate,
    PurchaseOrderListResponse,
    PurchaseOrderReason,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)
from app.features.users.model import User

router = APIRouter(tags=["Purchasing"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/purchase-orders", response_model=PurchaseOrderListResponse)
def list_purchase_orders(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    status_filter: Literal[
        "draft", "pending_approval", "approved", "rejected", "cancelled", "received"
    ]
    | None = Query(default=None, alias="status"),
    supplier_id: int | None = Query(default=None, gt=0),
    created_by: int | None = Query(default=None, gt=0),
    actor: User = Depends(require_permission("purchase_orders.read")),
):
    return service.list_purchase_orders(
        db,
        page=page,
        size=size,
        search=search,
        status=status_filter,
        supplier_id=supplier_id,
        created_by=created_by,
    )


@router.get("/purchase-orders/{purchase_order_id}", response_model=PurchaseOrderResponse)
def get_purchase_order(
    purchase_order_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("purchase_orders.read")),
):
    return service.get_purchase_order(db, purchase_order_id)


@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_order(
    data: PurchaseOrderCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("purchase_orders.create")),
):
    return service.create_purchase_order(
        db, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.put("/purchase-orders/{purchase_order_id}", response_model=PurchaseOrderResponse)
def update_purchase_order(
    purchase_order_id: int,
    data: PurchaseOrderUpdate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("purchase_orders.update")),
):
    return service.update_purchase_order(
        db, purchase_order_id, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.post(
    "/purchase-orders/{purchase_order_id}/submit", response_model=PurchaseOrderResponse
)
def submit_purchase_order(
    purchase_order_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("purchase_orders.update")),
):
    return service.submit_purchase_order(
        db, purchase_order_id, actor_id=actor.id, ip_address=_ip(request)
    )


@router.post(
    "/purchase-orders/{purchase_order_id}/approve", response_model=PurchaseOrderResponse
)
def approve_purchase_order(
    purchase_order_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("purchase_orders.approve")),
):
    return service.approve_purchase_order(
        db,
        purchase_order_id,
        actor_id=actor.id,
        actor_is_admin=any(role.is_active and role.name == "admin" for role in actor.roles),
        ip_address=_ip(request),
    )


@router.post(
    "/purchase-orders/{purchase_order_id}/reject", response_model=PurchaseOrderResponse
)
def reject_purchase_order(
    purchase_order_id: int,
    data: PurchaseOrderReason,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("purchase_orders.approve")),
):
    return service.reject_purchase_order(
        db,
        purchase_order_id,
        data.reason,
        actor_id=actor.id,
        actor_is_admin=any(role.is_active and role.name == "admin" for role in actor.roles),
        ip_address=_ip(request),
    )


@router.post(
    "/purchase-orders/{purchase_order_id}/cancel", response_model=PurchaseOrderResponse
)
def cancel_purchase_order(
    purchase_order_id: int,
    data: PurchaseOrderReason,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("purchase_orders.cancel")),
):
    return service.cancel_purchase_order(
        db,
        purchase_order_id,
        data.reason,
        actor_id=actor.id,
        ip_address=_ip(request),
    )


@router.post(
    "/purchase-orders/{purchase_order_id}/receive",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def receive_purchase_order(
    purchase_order_id: int,
    data: GoodsReceiptCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("goods_receipts.create")),
):
    return service.receive_purchase_order(
        db, purchase_order_id, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.get("/goods-receipts", response_model=GoodsReceiptListResponse)
def list_goods_receipts(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    actor: User = Depends(require_permission("goods_receipts.read")),
):
    return service.list_goods_receipts(db, page=page, size=size)


@router.get("/goods-receipts/{receipt_id}", response_model=GoodsReceiptResponse)
def get_goods_receipt(
    receipt_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("goods_receipts.read")),
):
    return service.get_goods_receipt(db, receipt_id)
