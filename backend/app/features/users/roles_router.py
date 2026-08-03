from fastapi import APIRouter, Depends, Request, status

from app.core.dependencies import DatabaseSession, require_permission
from app.features.users import service
from app.features.users.model import User
from app.features.users.schemas import (
    PermissionAssignment,
    PermissionResponse,
    RoleCreate,
    RoleListResponse,
    RoleResponse,
    RoleUpdate,
)

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("/permissions/all", response_model=list[PermissionResponse])
def get_permissions(
    db: DatabaseSession,
    actor: User = Depends(require_permission("roles.manage")),
):
    return service.get_permissions(db)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[RoleListResponse])
def get_roles(
    db: DatabaseSession,
    actor: User = Depends(require_permission("roles.manage")),
):
    return service.get_roles(db)


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(
    role_id: int,
    db: DatabaseSession,
    actor: User = Depends(require_permission("roles.manage")),
):
    return service.get_role(db, role_id)


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    data: RoleCreate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("roles.manage")),
):
    return service.create_role(db, data, actor_id=actor.id, ip_address=_ip(request))


@router.put("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: int,
    data: RoleUpdate,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("roles.manage")),
):
    return service.update_role(
        db, role_id, data, actor_id=actor.id, ip_address=_ip(request)
    )


@router.delete("/{role_id}", response_model=RoleResponse)
def deactivate_role(
    role_id: int,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("roles.manage")),
):
    return service.deactivate_role(
        db, role_id, actor_id=actor.id, ip_address=_ip(request)
    )


@router.put("/{role_id}/permissions", response_model=RoleResponse)
def assign_permissions(
    role_id: int,
    data: PermissionAssignment,
    request: Request,
    db: DatabaseSession,
    actor: User = Depends(require_permission("roles.manage")),
):
    return service.assign_permissions(
        db,
        role_id,
        data.permission_ids,
        actor_id=actor.id,
        ip_address=_ip(request),
    )
