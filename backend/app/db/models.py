"""Register all SQLAlchemy models with metadata for Alembic."""

from app.features.accounting.models import (
    Account,
    JournalEntry,
    JournalEntryLine,
    SupplierPayment,
    SystemSetting,
)
from app.features.audit.model import AuditLog
from app.features.billing.models import Invoice, InvoiceItem, Payment
from app.features.customers.models import Customer
from app.features.inventory.models import InventoryCount, StockLevel, StockMovement
from app.features.products.models import Category, Product
from app.features.purchases.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
)
from app.features.quotations.models import Quotation, QuotationItem
from app.features.sales.models import SalesDelivery, SalesDeliveryItem, SalesOrder, SalesOrderItem
from app.features.suppliers.models import Supplier
from app.features.users.model import Permission, RefreshToken, Role, User
from app.features.warehouses.models import Warehouse

__all__ = [
    "AuditLog",
    "Account",
    "Category",
    "Customer",
    "GoodsReceipt",
    "GoodsReceiptItem",
    "InventoryCount",
    "Invoice",
    "InvoiceItem",
    "JournalEntry",
    "JournalEntryLine",
    "Permission",
    "Payment",
    "Product",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "Quotation",
    "QuotationItem",
    "SalesDelivery",
    "SalesDeliveryItem",
    "SalesOrder",
    "SalesOrderItem",
    "RefreshToken",
    "Role",
    "StockLevel",
    "StockMovement",
    "Supplier",
    "SupplierPayment",
    "SystemSetting",
    "User",
    "Warehouse",
]
