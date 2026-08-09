from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class ProfitReport(BaseModel):
    date_from: date
    date_to: date
    revenue: Decimal
    cost_of_goods_sold: Decimal
    gross_profit: Decimal
    gross_margin_percent: Decimal


class TopProductRow(BaseModel):
    product_id: int
    sku: str
    product_name: str
    quantity_sold: int
    net_sales: Decimal


class InventoryValuationRow(BaseModel):
    product_id: int
    sku: str
    product_name: str
    quantity: int
    unit_cost: Decimal
    inventory_value: Decimal


class InventoryValuationReport(BaseModel):
    total_quantity: int
    total_value: Decimal
    items: list[InventoryValuationRow]


class ReceivableAgingRow(BaseModel):
    customer_id: int
    customer_name: str
    current: Decimal
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    over_90: Decimal
    total: Decimal


class ReceivableAgingReport(BaseModel):
    as_of: date
    total_outstanding: Decimal
    items: list[ReceivableAgingRow]


class MonthlySalesRow(BaseModel):
    month: str
    invoice_count: int
    net_sales: Decimal


class StockMovementRow(BaseModel):
    id: int
    occurred_at: datetime
    product_id: int
    sku: str
    product_name: str
    warehouse_id: int
    warehouse_name: str
    reference: str
    movement_type: str
    quantity_in: int
    quantity_out: int
    running_balance: int


class ManagementDashboard(BaseModel):
    sales_this_month: Decimal
    profit_this_month: Decimal
    receivables: Decimal
    inventory_value: Decimal
    overdue_invoices: int
    low_stock_products: int
    pending_purchase_approvals: int
    quotations_expiring_soon: int

