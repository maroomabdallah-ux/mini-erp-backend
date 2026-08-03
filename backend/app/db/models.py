"""Register all SQLAlchemy models with metadata for Alembic."""

from app.features.audit.model import AuditLog
from app.features.products.models import Category, Product
from app.features.users.model import Permission, RefreshToken, Role, User

__all__ = [
    "AuditLog",
    "Category",
    "Permission",
    "Product",
    "RefreshToken",
    "Role",
    "User",
]
