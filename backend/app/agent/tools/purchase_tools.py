from langchain.tools import tool

from app.db.session import SessionLocal
from app.features.purchases.service import get_purchase_order as get_purchase_order_service
from app.features.purchases.service import list_goods_receipts, list_purchase_orders


def _purchase_order_summary(order) -> dict:
    return {
        "id": order.id,
        "po_number": order.number,
        "supplier": {"id": order.supplier.id, "name": order.supplier.name},
        "warehouse": {
            "id": order.warehouse.id,
            "code": order.warehouse.code,
            "name": order.warehouse.name,
        },
        "status": order.status,
        "expected_date": order.expected_date,
        "total_amount": order.total_amount,
    }


def _purchase_order_detail(order) -> dict:
    result = _purchase_order_summary(order)
    result.update(
        {
            "notes": order.notes,
            "items": [
                {
                    "id": item.id,
                    "product": {
                        "id": item.product.id,
                        "sku": item.product.sku,
                        "name": item.product.name,
                    },
                    "quantity": item.quantity,
                    "received_quantity": item.received_quantity,
                    "unit_cost": item.unit_cost,
                    "line_total": item.line_total,
                }
                for item in order.items
            ],
        }
    )
    return result


@tool
def get_purchase_orders(
    search: str | None = None,
    status: str | None = None,
    supplier_id: int | None = None,
    limit: int = 20,
) -> list[dict]:
    """List purchase orders, optionally filtered by search, status, or supplier ID."""
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        result = list_purchase_orders(
            db,
            page=1,
            size=limit,
            search=search,
            status=status,
            supplier_id=supplier_id,
            created_by=None,
        )
        return [_purchase_order_summary(order) for order in result["items"]]
    finally:
        db.close()


@tool
def get_purchase_order(purchase_order_id: int) -> dict:
    """Get a purchase order and its line items by ID."""
    db = SessionLocal()
    try:
        return _purchase_order_detail(get_purchase_order_service(db, purchase_order_id))
    finally:
        db.close()


@tool
def get_pending_purchase_orders(limit: int = 20) -> list[dict]:
    """List purchase orders that are pending approval."""
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        result = list_purchase_orders(
            db,
            page=1,
            size=limit,
            search=None,
            status="pending_approval",
            supplier_id=None,
            created_by=None,
        )
        return [_purchase_order_summary(order) for order in result["items"]]
    finally:
        db.close()


@tool
def get_goods_receipts(limit: int = 20) -> list[dict]:
    """List recent goods receipts from the Mini ERP."""
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        result = list_goods_receipts(db, page=1, size=limit)
        return [
            {
                "id": receipt.id,
                "receipt_number": receipt.number,
                "purchase_order_id": receipt.purchase_order_id,
                "warehouse": {
                    "id": receipt.warehouse.id,
                    "code": receipt.warehouse.code,
                    "name": receipt.warehouse.name,
                },
                "received_at": receipt.received_at,
                "items": [
                    {
                        "product_id": item.product_id,
                        "sku": item.product.sku,
                        "name": item.product.name,
                        "quantity": item.quantity,
                    }
                    for item in receipt.items
                ],
            }
            for receipt in result["items"]
        ]
    finally:
        db.close()
