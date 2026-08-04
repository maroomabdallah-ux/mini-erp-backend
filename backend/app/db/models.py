"""Register all SQLAlchemy models with metadata for Alembic."""

from app.features.audit.model import AuditLog
from app.features.inventory.models import StockLevel, StockMovement
from app.features.products.models import Category, Product
from app.features.suppliers.models import Supplier
from app.features.users.model import Permission, RefreshToken, Role, User
from app.features.warehouses.models import Warehouse

__all__ = [
    "AuditLog",
    "Category",
    "Permission",
    "Product",
    "RefreshToken",
    "Role",
    "StockLevel",
    "StockMovement",
    "Supplier",
    "User",
    "Warehouse",
]
