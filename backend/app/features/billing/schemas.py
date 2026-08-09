from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

InvoiceStatus = Literal["draft", "issued", "partially_paid", "paid", "cancelled"]
PaymentMethod = Literal["cash", "bank_transfer", "card", "cheque"]


class InvoiceCreate(BaseModel):
    sales_order_id: int = Field(gt=0)
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ReasonPayload(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return value.strip()


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_date: date
    method: PaymentMethod
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("reference", "notes")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else None
        return cleaned or None


class PaymentAllocationInput(BaseModel):
    invoice_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class CustomerPaymentCreate(PaymentCreate):
    customer_id: int = Field(gt=0)
    allocations: list[PaymentAllocationInput] = Field(default_factory=list, max_length=200)


class PaymentAllocationResponse(BaseModel):
    id: int
    invoice_id: int
    allocated_amount: Decimal
    model_config = ConfigDict(from_attributes=True)


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


class SalesOrderSummary(BaseModel):
    id: int
    number: str
    status: str
    total_amount: Decimal
    customer: CustomerSummary
    model_config = ConfigDict(from_attributes=True)


class InvoiceItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    product: ProductSummary
    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    id: int
    number: str
    invoice_id: int | None
    customer_id: int
    amount: Decimal
    payment_date: date
    method: PaymentMethod
    reference: str | None
    notes: str | None
    status: Literal["posted", "reversed"]
    created_by: int
    reversed_by: int | None
    reversed_at: datetime | None
    reversal_reason: str | None
    created_at: datetime
    allocations: list[PaymentAllocationResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: int
    number: str
    document_type: Literal["invoice", "credit_note"]
    sales_order_id: int | None
    reversed_invoice_id: int | None
    customer_id: int
    status: InvoiceStatus
    issue_date: date | None
    due_date: date
    notes: str | None
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    created_by: int
    issued_by: int | None
    issued_at: datetime | None
    cancelled_by: int | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    customer: CustomerSummary
    sales_order: SalesOrderSummary | None
    items: list[InvoiceItemResponse]
    payments: list[PaymentResponse]
    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def balance_due(self) -> Decimal:
        if self.document_type == "credit_note":
            return Decimal("0.00")
        return self.total_amount - self.paid_amount


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    page: int
    size: int
    total: int
