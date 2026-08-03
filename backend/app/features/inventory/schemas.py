from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InventoryProductSummary(BaseModel):
    id: int
    sku: str
    name: str
    min_stock_level: Decimal
    model_config = ConfigDict(from_attributes=True)


class InventoryWarehouseSummary(BaseModel):
    id: int
    code: str
    name: str
    model_config = ConfigDict(from_attributes=True)


class StockLevelResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    quantity: Decimal
    product: InventoryProductSummary
    warehouse: InventoryWarehouseSummary
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StockListResponse(BaseModel):
    items: list[StockLevelResponse]
    page: int
    size: int
    total: int
    total_quantity: Decimal


class StockAdjustmentCreate(BaseModel):
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    quantity_change: Decimal = Field(max_digits=12, decimal_places=2)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("quantity_change")
    @classmethod
    def quantity_must_not_be_zero(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("Quantity change must not be zero.")
        return value

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return value.strip()


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    type: str
    quantity: Decimal
    reference_type: str | None
    reference_id: str | None
    reason: str | None
    created_by: int
    created_at: datetime
    product: InventoryProductSummary
    warehouse: InventoryWarehouseSummary
    model_config = ConfigDict(from_attributes=True)


class StockMovementListResponse(BaseModel):
    items: list[StockMovementResponse]
    page: int
    size: int
    total: int


class LowStockResponse(BaseModel):
    product_id: int
    sku: str
    name: str
    total_quantity: Decimal
    min_stock_level: Decimal
    shortage: Decimal
