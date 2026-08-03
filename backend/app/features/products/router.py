from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.products import service
from app.features.products.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    ProductCreate,
    ProductImportResponse,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.features.users.model import User

router = APIRouter()


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    tags=["Categories"],
)
def list_categories(
    db: DatabaseSession,
    include_inactive: bool = False,
    actor: User = Depends(require_permission("products.read")),
):
    return service.list_categories(db, include_inactive=include_inactive)


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Categories"],
)
def create_category(
    data: CategoryCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("products.manage")),
):
    return service.create_category(
        db, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.put(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    tags=["Categories"],
)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("products.manage")),
):
    return service.update_category(
        db, category_id, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.delete(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    tags=["Categories"],
)
def deactivate_category(
    category_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("products.manage")),
):
    return service.deactivate_category(
        db, category_id, actor_id=actor.id, ip_address=_ip(request)
    )


@router.get("/products", response_model=ProductListResponse, tags=["Products"])
def list_products(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
    category_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
    actor: User = Depends(require_permission("products.read")),
):
    return service.list_products(
        db,
        page=page,
        size=size,
        search=search,
        category_id=category_id,
        is_active=is_active,
    )


@router.get("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
def get_product(
    product_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("products.read")),
):
    return service.get_product(db, product_id)


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Products"],
)
def create_product(
    data: ProductCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("products.manage")),
):
    return service.create_product(
        db, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.post(
    "/products/import",
    response_model=ProductImportResponse,
    tags=["Products"],
)
async def import_products(
    request: Request,
    db: DatabaseSession,
    file: UploadFile = File(...),
    actor: User = Depends(require_permission("products.manage")),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        from app.core.exceptions import BusinessRuleError

        raise BusinessRuleError("Only CSV files are supported.")
    return service.import_products(
        db,
        await file.read(),
        actor_id=actor.id,
        ip_address=_ip(request),
    )


@router.put("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
def update_product(
    product_id: int,
    data: ProductUpdate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("products.manage")),
):
    return service.update_product(
        db, product_id, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.delete(
    "/products/{product_id}", response_model=ProductResponse, tags=["Products"]
)
def deactivate_product(
    product_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("products.manage")),
):
    return service.deactivate_product(
        db, product_id, actor_id=actor.id, ip_address=_ip(request)
    )
