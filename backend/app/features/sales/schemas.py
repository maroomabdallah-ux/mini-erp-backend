from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SalesOrderStatus = Literal["draft", "confirmed", "delivered", "cancelled"]


class SalesOrderItemInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    discount_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2
    )


class SalesOrderCreate(BaseModel):
    customer_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=2000)
    discount_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    tax_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)
    items: list[SalesOrderItemInput] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_products(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each product may appear only once in a sales order.")
        return self


class SalesOrderReason(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return value.strip()


class SalesOrderConfirm(BaseModel):
    warehouse_id: int = Field(gt=0)


class SalesDeliveryCreate(BaseModel):
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else None
        return cleaned or None


class ProductSummary(BaseModel):
    id: int
    sku: str
    name: str
    model_config = ConfigDict(from_attributes=True)


class CustomerSummary(BaseModel):
    id: int
    code: str
    name: str
    email: str | None
    phone: str | None
    model_config = ConfigDict(from_attributes=True)


class WarehouseSummary(BaseModel):
    id: int
    code: str
    name: str
    model_config = ConfigDict(from_attributes=True)


class SalesOrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    discount_percent: Decimal
    line_total: Decimal
    product: ProductSummary
    model_config = ConfigDict(from_attributes=True)


class SalesDeliveryItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: ProductSummary
    model_config = ConfigDict(from_attributes=True)


class SalesDeliveryResponse(BaseModel):
    id: int
    number: str
    sales_order_id: int
    warehouse_id: int
    notes: str | None
    delivered_by: int
    delivered_at: datetime
    warehouse: WarehouseSummary
    items: list[SalesDeliveryItemResponse]
    model_config = ConfigDict(from_attributes=True)


class SalesOrderResponse(BaseModel):
    id: int
    number: str
    quotation_id: int | None
    customer_id: int
    warehouse_id: int | None
    status: SalesOrderStatus
    notes: str | None
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    created_by: int
    confirmed_by: int | None
    confirmed_at: datetime | None
    cancelled_by: int | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    credit_warning: str | None
    created_at: datetime
    updated_at: datetime
    customer: CustomerSummary
    warehouse: WarehouseSummary | None
    items: list[SalesOrderItemResponse]
    delivery: SalesDeliveryResponse | None
    model_config = ConfigDict(from_attributes=True)


class SalesOrderListResponse(BaseModel):
    items: list[SalesOrderResponse]
    page: int
    size: int
    total: int


class AvailabilityItem(BaseModel):
    product_id: int
    sku: str
    name: str
    required: int
    available: int
    sufficient: bool


class WarehouseAvailability(BaseModel):
    warehouse: WarehouseSummary
    ready: bool
    items: list[AvailabilityItem]
