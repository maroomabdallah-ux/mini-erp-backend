from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AccountInput(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=150)
    type: Literal["asset", "liability", "equity", "revenue", "expense"]
    parent_id: int | None = Field(default=None, gt=0)

    @field_validator("code", "name")
    @classmethod
    def clean(cls, value: str) -> str:
        return value.strip()


class AccountResponse(AccountInput):
    id: int
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class JournalLineInput(BaseModel):
    account_id: int = Field(gt=0)
    debit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    credit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    memo: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def one_side(self):
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("Exactly one of debit or credit must be positive.")
        return self


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str = Field(min_length=3, max_length=500)
    lines: list[JournalLineInput] = Field(min_length=2, max_length=100)

    @model_validator(mode="after")
    def balanced(self):
        if sum((line.debit for line in self.lines), Decimal("0")) != sum(
            (line.credit for line in self.lines), Decimal("0")
        ):
            raise ValueError("Journal entry debits and credits must be equal.")
        return self


class JournalLineResponse(BaseModel):
    id: int
    account_id: int
    debit: Decimal
    credit: Decimal
    memo: str | None
    account: AccountResponse
    model_config = ConfigDict(from_attributes=True)


class JournalEntryResponse(BaseModel):
    id: int
    number: str
    entry_date: date
    description: str
    source_type: str | None
    source_id: int | None
    source_reference: str
    source_route: str | None
    source_document_id: int | None
    total_amount: Decimal
    created_by: int
    created_at: datetime
    lines: list[JournalLineResponse]
    model_config = ConfigDict(from_attributes=True)


class JournalEntryListResponse(BaseModel):
    items: list[JournalEntryResponse]
    page: int
    size: int
    total: int


class SupplierPaymentCreate(BaseModel):
    supplier_id: int = Field(gt=0)
    purchase_order_id: int | None = Field(default=None, gt=0)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_date: date
    method: Literal["cash", "bank_transfer", "card", "cheque"]
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)


class SupplierPaymentResponse(BaseModel):
    id: int
    number: str
    supplier_id: int
    purchase_order_id: int | None
    amount: Decimal
    payment_date: date
    method: str
    reference: str | None
    notes: str | None
    status: str
    created_by: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SupplierOutstandingResponse(BaseModel):
    purchase_order_id: int
    purchase_order_number: str
    supplier_id: int
    supplier_name: str
    total_amount: Decimal
    paid_amount: Decimal
    remaining_amount: Decimal


class AccountingDashboardResponse(BaseModel):
    cash: Decimal
    bank: Decimal
    accounts_receivable: Decimal
    accounts_payable: Decimal
    inventory_value: Decimal
    profit_this_month: Decimal


class TimelineEvent(BaseModel):
    key: str
    label: str
    occurred_at: datetime
    reference: str
    route: str | None
    document_id: int | None


class ReasonPayload(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class StatementLine(BaseModel):
    date: date
    reference: str
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class StatementResponse(BaseModel):
    entity_id: int
    entity_name: str
    date_from: date
    date_to: date
    opening_balance: Decimal
    closing_balance: Decimal
    lines: list[StatementLine]


class SalesSettings(BaseModel):
    credit_limit_behavior: Literal["block", "warn"]
