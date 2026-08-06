from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.suppliers import service
from app.features.suppliers.schemas import (
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)
from app.features.users.model import User

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=SupplierListResponse)
def list_suppliers(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    is_active: bool | None = None,
    actor: User = Depends(require_permission("suppliers.read")),
):
    return service.list_suppliers(db, page=page, size=size, search=search, is_active=is_active)


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("suppliers.read")),
):
    return service.get_supplier(db, supplier_id)


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    data: SupplierCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("suppliers.manage")),
):
    return service.create_supplier(db, data, actor_id=actor.id, ip_address=_ip(request))


@router.put("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("suppliers.manage")),
):
    return service.update_supplier(
        db, supplier_id, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.delete("/{supplier_id}", response_model=SupplierResponse)
def deactivate_supplier(
    supplier_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("suppliers.manage")),
):
    return service.deactivate_supplier(db, supplier_id, actor_id=actor.id, ip_address=_ip(request))
