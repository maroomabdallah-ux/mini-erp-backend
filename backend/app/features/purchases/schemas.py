from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PurchaseOrderStatus = Literal[
    "draft", "pending_approval", "approved", "rejected", "cancelled", "received"
]


def _clean_optional(value: str | None) -> str | None:
    normalized = value.strip() if value else None
    return normalized or None


class PurchaseOrderItemInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    unit_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PurchaseOrderItemInput] = Field(min_length=1, max_length=200)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @model_validator(mode="after")
    def unique_products(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each product may appear only once in a purchase order.")
        return self


class PurchaseOrderUpdate(PurchaseOrderCreate):
    pass


class PurchaseOrderReason(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return value.strip()


class GoodsReceiptCreate(BaseModel):
    warehouse_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class SupplierSummary(BaseModel):
    id: int
    name: str
    email: str
    model_config = ConfigDict(from_attributes=True)


class ProductSummary(BaseModel):
    id: int
    sku: str
    name: str
    model_config = ConfigDict(from_attributes=True)


class WarehouseSummary(BaseModel):
    id: int
    code: str
    name: str
    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_cost: Decimal
    line_total: Decimal
    product: ProductSummary
    model_config = ConfigDict(from_attributes=True)


class GoodsReceiptItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    product: ProductSummary
    model_config = ConfigDict(from_attributes=True)


class GoodsReceiptResponse(BaseModel):
    id: int
    number: str
    purchase_order_id: int
    warehouse_id: int
    notes: str | None
    received_by: int
    received_at: datetime
    warehouse: WarehouseSummary
    items: list[GoodsReceiptItemResponse]
    model_config = ConfigDict(from_attributes=True)


class GoodsReceiptListResponse(BaseModel):
    items: list[GoodsReceiptResponse]
    page: int
    size: int
    total: int


class PurchaseOrderResponse(BaseModel):
    id: int
    number: str
    supplier_id: int
    status: PurchaseOrderStatus
    notes: str | None
    total_amount: Decimal
    created_by: int
    submitted_at: datetime | None
    approved_by: int | None
    approved_at: datetime | None
    rejected_by: int | None
    rejected_at: datetime | None
    rejection_reason: str | None
    cancelled_by: int | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    supplier: SupplierSummary
    items: list[PurchaseOrderItemResponse]
    receipt: GoodsReceiptResponse | None
    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderResponse]
    page: int
    size: int
    total: int
