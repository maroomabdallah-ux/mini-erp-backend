from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    parent_id: int | None = Field(default=None, gt=0)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    parent_id: int | None = Field(default=None, gt=0)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


Money = Decimal


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=2, max_length=255)
    barcode: str | None = Field(default=None, max_length=100)
    category_id: int | None = Field(default=None, gt=0)
    cost_price: Money = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    sale_price: Money = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    min_stock_level: int = Field(default=0, ge=0)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("barcode")
    @classmethod
    def clean_barcode(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None


class ProductUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=2, max_length=255)
    barcode: str | None = Field(default=None, max_length=100)
    category_id: int | None = Field(default=None, gt=0)
    cost_price: Money | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    sale_price: Money | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    min_stock_level: int | None = Field(default=None, ge=0)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("name", "barcode")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None


class CategorySummary(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    barcode: str | None
    category_id: int | None
    category: CategorySummary | None
    cost_price: Decimal
    sale_price: Decimal
    min_stock_level: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    page: int
    size: int
    total: int


class ProductImportError(BaseModel):
    row: int
    field_errors: dict[str, str]


class ProductImportResponse(BaseModel):
    created_count: int
    error_count: int
    errors: list[ProductImportError]
