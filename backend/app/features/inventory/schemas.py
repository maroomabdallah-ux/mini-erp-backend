from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InventoryProductSummary(BaseModel):
    id: int
    sku: str
    name: str
    min_stock_level: int
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
    quantity: int
    product: InventoryProductSummary
    warehouse: InventoryWarehouseSummary
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StockListResponse(BaseModel):
    items: list[StockLevelResponse]
    page: int
    size: int
    total: int
    total_quantity: int


class StockAdjustmentCreate(BaseModel):
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    quantity_change: int
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("quantity_change")
    @classmethod
    def quantity_must_not_be_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Quantity change must not be zero.")
        return value

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return value.strip()


class StockTransferCreate(BaseModel):
    product_id: int = Field(gt=0)
    source_warehouse_id: int = Field(gt=0)
    destination_warehouse_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_transfer_reason(cls, value: str) -> str:
        return value.strip()


class StockTransferResponse(BaseModel):
    transfer_reference: str
    product_id: int
    source_warehouse_id: int
    destination_warehouse_id: int
    quantity: int
    source_quantity: int
    destination_quantity: int


class InventoryCountCreate(BaseModel):
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    counted_quantity: int = Field(ge=0)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def clean_count_notes(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class InventoryCountResponse(BaseModel):
    id: int
    reference: str
    product_id: int
    warehouse_id: int
    expected_quantity: int
    counted_quantity: int
    variance: int
    notes: str | None
    status: str
    created_by: int
    approved_by: int | None
    created_at: datetime
    approved_at: datetime | None
    product: InventoryProductSummary
    warehouse: InventoryWarehouseSummary
    model_config = ConfigDict(from_attributes=True)


class InventoryCountListResponse(BaseModel):
    items: list[InventoryCountResponse]
    page: int
    size: int
    total: int


class StockMovementResponse(BaseModel):
    id: int
    product_id: int
    warehouse_id: int
    type: str
    quantity: int
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
    total_quantity: int
    min_stock_level: int
    shortage: int
