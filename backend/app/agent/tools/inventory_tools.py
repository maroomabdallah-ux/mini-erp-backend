from langchain.tools import tool

from app.db.session import SessionLocal
from app.features.inventory.service import (
    list_low_stock,
    list_stock,
)


@tool
def get_low_stock_products() -> list[dict]:
    """
    Get products whose current stock is below
    their configured minimum stock level.
    """

    db = SessionLocal()

    try:
        return list_low_stock(db)

    finally:
        db.close()


@tool
def get_stock(
    product_id: int | None = None,
    warehouse_id: int | None = None,
) -> dict:
    """
    Get current stock information from the Mini ERP.

    Use this tool when the user asks:
    - how much stock a product has
    - stock in a specific warehouse
    - total stock for a product

    product_id and warehouse_id are optional.
    """

    db = SessionLocal()

    try:
        result = list_stock(
            db,
            page=1,
            size=50,
            product_id=product_id,
            warehouse_id=warehouse_id,
            search=None,
        )

        return {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "total_quantity": str(result["total_quantity"]),
            "stock_records": result["total"],
        }

    finally:
        db.close()