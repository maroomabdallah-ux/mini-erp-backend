from fastapi import APIRouter, Request, Response, status

from app.core.dependencies import CurrentUser, DatabaseSession
from app.features.users import auth_service
from app.features.users.schemas import (
    AccessTokenResponse,
    CurrentUserResponse,
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
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


@router.put("/me", response_model=CurrentUserResponse)
def update_me(
    data: ProfileUpdate,
    request: Request,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    from app.features.users import service

    updated = service.update_own_profile(
        db,
        current_user,
        data,
        ip_address=request.client.host if request.client else None,
    )
    user_data = UserResponse.model_validate(updated).model_dump()
    return CurrentUserResponse(
        **user_data,
        permissions=auth_service.permission_codes(updated),
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChange,
    request: Request,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Response:
    from app.features.users import service

    service.change_own_password(
        db,
        current_user,
        current_password=data.current_password,
        new_password=data.new_password,
        ip_address=request.client.host if request.client else None,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
