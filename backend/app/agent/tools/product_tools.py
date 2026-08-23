from langchain.tools import tool

from app.db.session import SessionLocal
from app.features.products.service import list_products


@tool
def get_products(limit: int = 20) -> list[dict]:
    """
    Get active products from the Mini ERP.

    Use this tool when the user asks to view
    or list available products.
    """

    limit = max(1, min(limit, 50))

    db = SessionLocal()

    try:
        result = list_products(
            db,
            page=1,
            size=limit,
            search=None,
            category_id=None,
            is_active=True,
        )

        return [
            {
                "id": product.id,
                "sku": product.sku,
                "name": product.name,
                "sale_price": str(product.sale_price),
            }
            for product in result["items"]
        ]

    finally:
        db.close()