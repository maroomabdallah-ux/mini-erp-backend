from fastapi import APIRouter, Request, Response, status

from app.core.dependencies import CurrentUser, DatabaseSession
from app.features.users import auth_service
from app.features.users.schemas import (
    AccessTokenResponse,
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: DatabaseSession):
    ip_address = request.client.host if request.client else "unknown"
    access_token, refresh_token, user = auth_service.login(
        db, data.login, data.password, ip_address
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(data: RefreshRequest, db: DatabaseSession):
    return AccessTokenResponse(access_token=auth_service.refresh(db, data.refresh_token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: RefreshRequest, db: DatabaseSession) -> Response:
    auth_service.logout(db, data.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: CurrentUser):
    user_data = UserResponse.model_validate(current_user).model_dump()
    return CurrentUserResponse(
        **user_data,
        permissions=auth_service.permission_codes(current_user),
    )
