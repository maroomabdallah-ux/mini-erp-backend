from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.users import service
from app.features.users.model import User
from app.features.users.schemas import (
    PasswordReset,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])
AdminUser = Depends(require_permission("users.manage"))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=UserListResponse, dependencies=[AdminUser])
def get_users(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=255),
):
    return service.get_users(db, page=page, size=size, search=search)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("users.manage")),
):
    return service.get_user(db, user_id)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("users.manage")),
):
    return service.create_user(
        db, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("users.manage")),
):
    return service.update_user(
        db, user_id, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.post("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("users.manage")),
):
    return service.deactivate_user(
        db, user_id, actor_id=actor.id, ip_address=_ip(request)
    )


@router.post("/{user_id}/reset-password", response_model=UserResponse)
def reset_password(
    user_id: int,
    data: PasswordReset,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("users.manage")),
):
    return service.reset_user_password(
        db,
        user_id,
        data.new_password,
        actor_id=actor.id,
        ip_address=_ip(request),
    )
