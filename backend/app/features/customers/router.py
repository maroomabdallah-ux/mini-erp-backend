from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.customers import repository, service
from app.features.customers.schemas import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
)
from app.features.users.model import User

router = APIRouter(prefix="/customers", tags=["Customers"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/cities", response_model=list[str])
def list_customer_cities(
    db: DatabaseSession, actor: User = Depends(require_permission("customers.read"))
):
    return repository.list_cities(db)


@router.get("", response_model=CustomerListResponse)
def list_customers(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    is_active: bool | None = None,
    city: str | None = Query(default=None, max_length=100),
    actor: User = Depends(require_permission("customers.read")),
):
    return service.list_customers(
        db, page=page, size=size, search=search, is_active=is_active, city=city
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("customers.read")),
):
    return service.get_customer(db, customer_id)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    data: CustomerCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("customers.manage")),
):
    return service.create_customer(db, data, actor_id=actor.id, ip_address=_ip(request))


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("customers.manage")),
):
    return service.update_customer(
        db, customer_id, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.delete("/{customer_id}", response_model=CustomerResponse)
def deactivate_customer(
    customer_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("customers.manage")),
):
    return service.deactivate_customer(db, customer_id, actor_id=actor.id, ip_address=_ip(request))
