"""Register all SQLAlchemy models with metadata for Alembic."""

from app.features.audit.model import AuditLog
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
from app.features.suppliers.models import Supplier
from app.features.users.model import Permission, RefreshToken, Role, User
from app.features.warehouses.models import Warehouse

__all__ = [
    "AuditLog",
    "Category",
    "Customer",
    "GoodsReceipt",
    "GoodsReceiptItem",
    "InventoryCount",
    "Permission",
    "Product",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "Quotation",
    "QuotationItem",
    "RefreshToken",
    "Role",
    "StockLevel",
    "StockMovement",
    "Supplier",
    "User",
    "Warehouse",
]
