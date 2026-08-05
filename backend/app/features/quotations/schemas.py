from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

QuotationStatus = Literal["draft", "sent", "accepted", "rejected", "expired"]


class QuotationItemInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class QuotationCreate(BaseModel):
    customer_id: int = Field(gt=0)
    valid_until: date
    notes: str | None = Field(default=None, max_length=2000)
    discount_percent: Decimal = Field(
        default=Decimal("0.00"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    tax_percent: Decimal = Field(
        default=Decimal("0.00"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    items: list[QuotationItemInput] = Field(min_length=1, max_length=200)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else None
        return cleaned or None

    @model_validator(mode="after")
    def unique_products(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each product may appear only once in a quotation.")
        return self


class QuotationUpdate(QuotationCreate):
    pass


class QuotationReason(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return value.strip()


class CustomerSummary(BaseModel):
    id: int
    code: str
    name: str
    email: str | None
    phone: str | None
    model_config = ConfigDict(from_attributes=True)


class ProductSummary(BaseModel):
    id: int
    sku: str
    name: str
    model_config = ConfigDict(from_attributes=True)


class QuotationItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    product: ProductSummary
    model_config = ConfigDict(from_attributes=True)


class QuotationResponse(BaseModel):
    id: int
    number: str
    customer_id: int
    status: QuotationStatus
    valid_until: date
    notes: str | None
    discount_percent: Decimal
    tax_percent: Decimal
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    created_by: int
    sent_at: datetime | None
    accepted_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    customer: CustomerSummary
    items: list[QuotationItemResponse]
    model_config = ConfigDict(from_attributes=True)


class QuotationListResponse(BaseModel):
    items: list[QuotationResponse]
    page: int
    size: int
    total: int
