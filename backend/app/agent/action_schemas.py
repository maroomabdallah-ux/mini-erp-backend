from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class PrepareQuotationItem(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    discount_percent: Decimal = Field(
        default=Decimal("0.00"), ge=0, le=100, max_digits=5, decimal_places=2
    )


class PrepareQuotationRequest(BaseModel):
    customer_id: int = Field(gt=0)
    valid_until: date
    notes: str | None = Field(default=None, max_length=2000)
    discount_percent: Decimal = Field(
        default=Decimal("0.00"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    tax_percent: Decimal = Field(
        default=Decimal("0.00"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    items: list[PrepareQuotationItem] = Field(min_length=1, max_length=200)


class PreparePurchaseOrderItem(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class PreparePurchaseOrderRequest(BaseModel):
    supplier_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    expected_date: date
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PreparePurchaseOrderItem] = Field(min_length=1, max_length=200)


class PrepareSalesOrderConfirmationRequest(BaseModel):
    sales_order_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)


class PendingActionResponse(BaseModel):
    action_id: int
    action_type: Literal[
        "create_quotation", "create_purchase_order", "confirm_sales_order"
    ]
    status: Literal["pending", "executed", "expired", "cancelled", "failed"]
    expires_at: datetime
    summary: dict


class ActionExecutionResponse(BaseModel):
    action_id: int
    status: Literal["executed"]
    action_type: Literal[
        "create_quotation", "create_purchase_order", "confirm_sales_order"
    ]
    quotation_id: int | None = None
    quotation_number: str | None = None
    purchase_order_id: int | None = None
    purchase_order_number: str | None = None
    sales_order_id: int | None = None
    sales_order_number: str | None = None
    total_amount: str


class ActionCancellationResponse(BaseModel):
    action_id: int
    status: Literal["cancelled"]
