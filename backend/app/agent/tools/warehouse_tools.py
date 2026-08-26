from datetime import datetime

from langchain.tools import tool

from app.core.config import settings
from app.db.session import SessionLocal
from app.features.inventory.service import list_counts, list_movements, list_stock


@tool
def get_stock_movements(
    product_id: int | None = None,
    warehouse_id: int | None = None,
    movement_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
) -> list[dict]:
    """List bounded stock movements using existing inventory filters."""
    limit = max(1, min(limit, settings.agent_max_tool_results))
    db = SessionLocal()
    try:
        result = list_movements(
            db,
            page=1,
            size=limit,
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            date_from=date_from,
            date_to=date_to,
        )
        return [
            {
                "id": movement.id,
                "product": {
                    "id": movement.product.id,
                    "sku": movement.product.sku,
                    "name": movement.product.name,
                },
                "warehouse": {
                    "id": movement.warehouse.id,
                    "code": movement.warehouse.code,
                    "name": movement.warehouse.name,
                },
                "movement_type": movement.type,
                "quantity": str(movement.quantity),
                "reference_type": movement.reference_type,
                "reference_id": movement.reference_id,
                "reason": movement.reason,
                "created_at": movement.created_at,
            }
            for movement in result["items"]
        ]
    finally:
        db.close()


@tool
def get_inventory_by_warehouse(
    warehouse_id: int,
    product_id: int | None = None,
    search: str | None = None,
    limit: int = 20,
) -> dict:
    """Get bounded stock details for a specific warehouse."""
    limit = max(1, min(limit, settings.agent_max_tool_results))
    db = SessionLocal()
    try:
        result = list_stock(
            db,
            page=1,
            size=limit,
            product_id=product_id,
            warehouse_id=warehouse_id,
            search=search,
        )
        return {
            "warehouse_id": warehouse_id,
            "total_quantity": str(result["total_quantity"]),
            "items": [
                {
                    "product_id": stock.product.id,
                    "sku": stock.product.sku,
                    "product_name": stock.product.name,
                    "quantity": str(stock.quantity),
                    "minimum_stock_level": str(stock.product.min_stock_level),
                    "updated_at": stock.updated_at,
                }
                for stock in result["items"]
            ],
        }
    finally:
        db.close()


@tool
def get_inventory_counts(status: str | None = None, limit: int = 20) -> list[dict]:
    """List bounded physical inventory counts using the existing status filter."""
    limit = max(1, min(limit, settings.agent_max_tool_results))
    db = SessionLocal()
    try:
        result = list_counts(db, page=1, size=limit, status=status)
        return [
            {
                "id": count.id,
                "reference": count.reference,
                "product": {
                    "id": count.product.id,
                    "sku": count.product.sku,
                    "name": count.product.name,
                },
                "warehouse": {
                    "id": count.warehouse.id,
                    "code": count.warehouse.code,
                    "name": count.warehouse.name,
                },
                "expected_quantity": str(count.expected_quantity),
                "counted_quantity": str(count.counted_quantity),
                "variance": str(count.variance),
                "status": count.status,
                "created_at": count.created_at,
            }
            for count in result["items"]
        ]
    finally:
        db.close()
