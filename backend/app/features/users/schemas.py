from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class PermissionResponse(BaseModel):
    id: int
    code: str
    description: str | None
    model_config = ConfigDict(from_attributes=True)


class RoleSummary(BaseModel):
    id: int
    name: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class RoleListResponse(RoleSummary):
    description: str | None


class RoleResponse(RoleListResponse):
    permissions: list[PermissionResponse] = []


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    first_name: str = Field(min_length=2, max_length=100)
    last_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role_ids: list[int] = []

    @field_validator("username", "email", mode="after")
    @classmethod
    def normalize_login_fields(cls, value: str) -> str:
        return value.lower()


class UserUpdate(BaseModel):
    username: str | None = Field(
        default=None, min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    first_name: str | None = Field(default=None, min_length=2, max_length=100)
    last_name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    role_ids: list[int] | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    email: EmailStr
    is_active: bool
    roles: list[RoleSummary] = []
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    items: list[UserResponse]
    page: int
    size: int
    total: int


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9_.-]+$")
    description: str | None = Field(default=None, max_length=255)


class RoleUpdate(BaseModel):
    name: str | None = Field(
        default=None, min_length=2, max_length=50, pattern=r"^[a-z0-9_.-]+$"
    )
    description: str | None = Field(default=None, max_length=255)


class PermissionAssignment(BaseModel):
    permission_ids: list[int]


class LoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(UserResponse):
    permissions: list[str]
