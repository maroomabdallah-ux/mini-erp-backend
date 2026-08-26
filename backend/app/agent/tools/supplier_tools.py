from langchain.tools import tool

from app.db.session import SessionLocal
from app.features.suppliers.service import get_supplier as get_supplier_service
from app.features.suppliers.service import list_suppliers


def _supplier_result(supplier) -> dict:
    return {
        "id": supplier.id,
        "name": supplier.name,
        "email": supplier.email,
        "phone": supplier.phone,
        "credit_terms": supplier.credit_terms,
        "is_active": supplier.is_active,
    }


@tool
def search_suppliers(search: str, limit: int = 10) -> list[dict]:
    """Search active suppliers by the fields supported by the supplier service."""
    limit = max(1, min(limit, 20))
    db = SessionLocal()
    try:
        result = list_suppliers(
            db,
            page=1,
            size=limit,
            search=search,
            is_active=True,
        )
        return [_supplier_result(supplier) for supplier in result["items"]]
    finally:
        db.close()


@tool
def get_supplier(supplier_id: int) -> dict:
    """Get a supplier by ID from the Mini ERP."""
    db = SessionLocal()
    try:
        return _supplier_result(get_supplier_service(db, supplier_id))
    finally:
        db.close()
