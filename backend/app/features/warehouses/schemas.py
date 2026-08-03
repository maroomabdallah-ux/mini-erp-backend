from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=150)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("address")
    @classmethod
    def clean_address(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None


class WarehouseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=50)
    name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("name", "address")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None


class WarehouseResponse(BaseModel):
    id: int
    code: str
    name: str
    address: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WarehouseListResponse(BaseModel):
    items: list[WarehouseResponse]
    page: int
    size: int
    total: int
