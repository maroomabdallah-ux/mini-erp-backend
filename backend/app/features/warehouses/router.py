from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.users.model import User
from app.features.warehouses import service
from app.features.warehouses.schemas import (
    WarehouseCreate,
    WarehouseListResponse,
    WarehouseResponse,
    WarehouseUpdate,
)

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=WarehouseListResponse)
def list_warehouses(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    is_active: bool | None = None,
    actor: User = Depends(require_permission("warehouses.read")),
):
    return service.list_warehouses(
        db, page=page, size=size, search=search, is_active=is_active
    )


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse(
    warehouse_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("warehouses.read")),
):
    return service.get_warehouse(db, warehouse_id)


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    data: WarehouseCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("warehouses.manage")),
):
    return service.create_warehouse(
        db, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.put("/{warehouse_id}", response_model=WarehouseResponse)
def update_warehouse(
    warehouse_id: int,
    data: WarehouseUpdate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("warehouses.manage")),
):
    return service.update_warehouse(
        db, warehouse_id, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.delete("/{warehouse_id}", response_model=WarehouseResponse)
def deactivate_warehouse(
    warehouse_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("warehouses.manage")),
):
    return service.deactivate_warehouse(
        db, warehouse_id, actor_id=actor.id, ip_address=_ip(request)
    )
