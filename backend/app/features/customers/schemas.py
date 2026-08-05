from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _optional(value: str | None) -> str | None:
    cleaned = value.strip() if value else None
    return cleaned or None


class CustomerBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    contact_person: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    tax_number: str | None = Field(default=None, max_length=100)
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).strip().lower() if value is not None else None

    @field_validator("contact_person", "phone", "address", "city", "tax_number")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _optional(value)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    contact_person: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    tax_number: str | None = Field(default=None, max_length=100)
    credit_limit: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).strip().lower() if value is not None else None

    @field_validator("contact_person", "phone", "address", "city", "tax_number")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _optional(value)


class CustomerResponse(CustomerBase):
    id: int
    code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    page: int
    size: int
    total: int
