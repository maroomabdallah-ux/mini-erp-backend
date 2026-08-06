# app/core/dependencies.py

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.features.users import repository
from app.features.users.model import User

bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    description="Paste the access_token returned by POST /auth/login.",
    auto_error=False,
)

DatabaseSession = Annotated[
    Session,
    Depends(get_db),
]


def get_token_payload(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> dict:
    if credentials is None:
        raise UnauthorizedError("Authentication credentials are required.")

    try:
        payload = decode_token(credentials.credentials)

    except ValueError as exc:
        raise UnauthorizedError("Invalid or expired access token.") from exc

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type.")

    return payload


def get_current_user(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: DatabaseSession,
) -> User:
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid access token subject.") from exc

    user = repository.get_user_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists.")
    if not user.is_active:
        raise ForbiddenError("This account is deactivated.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission_code: str):
    def permission_dependency(current_user: CurrentUser) -> User:
        permissions = {
            permission.code
            for role in current_user.roles
            if role.is_active
            for permission in role.permissions
        }
        if permission_code not in permissions:
            raise ForbiddenError(f"Missing required permission: {permission_code}.")
        return current_user

    return permission_dependency
