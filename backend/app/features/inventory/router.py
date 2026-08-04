from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.core.dependencies import DatabaseSession, require_permission
from app.features.inventory import service
from app.features.inventory.schemas import (
    InventoryCountCreate,
    InventoryCountListResponse,
    InventoryCountResponse,
    LowStockResponse,
    StockAdjustmentCreate,
    StockLevelResponse,
    StockListResponse,
    StockMovementListResponse,
    StockTransferCreate,
    StockTransferResponse,
)
from app.features.users.model import User

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/stock", response_model=StockListResponse)
def get_stock(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    product_id: int | None = Query(default=None, gt=0),
    warehouse_id: int | None = Query(default=None, gt=0),
    search: str | None = Query(default=None, max_length=255),
    actor: User = Depends(require_permission("inventory.read")),
):
    return service.list_stock(
        db,
        page=page,
        size=size,
        product_id=product_id,
        warehouse_id=warehouse_id,
        search=search,
    )


@router.get("/movements", response_model=StockMovementListResponse)
def get_movements(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    product_id: int | None = Query(default=None, gt=0),
    warehouse_id: int | None = Query(default=None, gt=0),
    movement_type: Literal["in", "out", "adjust"] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    actor: User = Depends(require_permission("inventory.read")),
):
    return service.list_movements(
        db,
        page=page,
        size=size,
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/adjustments", response_model=StockLevelResponse)
def create_adjustment(
    data: StockAdjustmentCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("inventory.adjust")),
):
    return service.adjust_stock(db, data, actor_id=actor.id, ip_address=_ip(request))


@router.post("/transfers", response_model=StockTransferResponse, status_code=201)
def create_transfer(
    data: StockTransferCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("inventory.transfer")),
):
    return service.transfer_stock(db, data, actor_id=actor.id, ip_address=_ip(request))


@router.get("/low-stock", response_model=list[LowStockResponse])
def get_low_stock(
    db: DatabaseSession,
    actor: User = Depends(require_permission("inventory.low_stock.read")),
):
    return service.list_low_stock(db)


@router.get("/counts", response_model=InventoryCountListResponse)
def get_counts(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Literal["pending", "approved"] | None = None,
    actor: User = Depends(require_permission("inventory.read")),
):
    return service.list_counts(db, page=page, size=size, status=status)


@router.post("/counts", response_model=InventoryCountResponse, status_code=201)
def create_count(
    data: InventoryCountCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("inventory.count")),
):
    return service.create_count(db, data, actor_id=actor.id, ip_address=_ip(request))


@router.post("/counts/{count_id}/approve", response_model=InventoryCountResponse)
def approve_count(
    count_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("inventory.count.approve")),
):
    return service.approve_count(db, count_id, actor_id=actor.id, ip_address=_ip(request))
