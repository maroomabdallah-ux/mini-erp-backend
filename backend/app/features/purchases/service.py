from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.features.audit.service import add_audit_log
from app.features.inventory import repository as inventory_repository
from app.features.inventory.models import StockLevel, StockMovement
from app.features.products import repository as product_repository
from app.features.purchases import repository
from app.features.purchases.exceptions import (
    GoodsReceiptNotFoundError,
    PurchaseOrderConflictError,
    PurchaseOrderEntityError,
    PurchaseOrderNotFoundError,
    PurchaseOrderStateError,
)
from app.features.purchases.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
)
from app.features.purchases.schemas import (
    GoodsReceiptCreate,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)
from app.features.suppliers import repository as supplier_repository
from app.features.warehouses import repository as warehouse_repository


def _now() -> datetime:
    return datetime.now(UTC)


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("The purchase operation conflicted with another update.") from exc


def _order_or_error(db: Session, purchase_order_id: int, *, lock: bool = False) -> PurchaseOrder:
    order = (
        repository.get_purchase_order_for_update(db, purchase_order_id)
        if lock
        else repository.get_purchase_order(db, purchase_order_id)
    )
    if order is None:
        raise PurchaseOrderNotFoundError(purchase_order_id)
    return order


def _validate_entities(db: Session, data: PurchaseOrderCreate | PurchaseOrderUpdate):
    supplier = supplier_repository.get_supplier(db, data.supplier_id)
    if supplier is None:
        from app.features.suppliers.exceptions import SupplierNotFoundError

        raise SupplierNotFoundError(data.supplier_id)
    if not supplier.is_active:
        raise PurchaseOrderEntityError("Purchase orders require an active supplier.")

    products = {}
    for item in data.items:
        product = product_repository.get_product(db, item.product_id)
        if product is None:
            from app.features.products.exceptions import ProductNotFoundError

            raise ProductNotFoundError(item.product_id)
        if not product.is_active:
            raise PurchaseOrderEntityError(
                f"Product with id {product.id} is inactive and cannot be ordered."
            )
        products[product.id] = product
    return supplier, products


def _replace_items(order: PurchaseOrder, data: PurchaseOrderCreate | PurchaseOrderUpdate) -> None:
    order.items = [
        PurchaseOrderItem(
            product_id=item.product_id,
            quantity=item.quantity,
            unit_cost=item.unit_cost,
            line_total=item.unit_cost * item.quantity,
        )
        for item in data.items
    ]
    order.total_amount = sum(
        (item.line_total for item in order.items), start=Decimal("0.00")
    )


def _snapshot(order: PurchaseOrder) -> dict:
    return {
        "number": order.number,
        "supplier_id": order.supplier_id,
        "status": order.status,
        "notes": order.notes,
        "total_amount": _money(order.total_amount),
        "items": [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_cost": _money(item.unit_cost),
                "line_total": _money(item.line_total),
            }
            for item in order.items
        ],
    }


def list_purchase_orders(
    db: Session,
    *,
    page: int,
    size: int,
    search: str | None,
    status: str | None,
    supplier_id: int | None,
    created_by: int | None,
) -> dict:
    return {
        "items": repository.list_purchase_orders(
            db,
            offset=(page - 1) * size,
            limit=size,
            search=search,
            status=status,
            supplier_id=supplier_id,
            created_by=created_by,
        ),
        "page": page,
        "size": size,
        "total": repository.count_purchase_orders(
            db,
            search=search,
            status=status,
            supplier_id=supplier_id,
            created_by=created_by,
        ),
    }


def get_purchase_order(db: Session, purchase_order_id: int) -> PurchaseOrder:
    return _order_or_error(db, purchase_order_id)


def create_purchase_order(
    db: Session,
    data: PurchaseOrderCreate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> PurchaseOrder:
    _validate_entities(db, data)
    order = PurchaseOrder(
        number=f"PO-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        supplier_id=data.supplier_id,
        notes=data.notes,
        status="draft",
        created_by=actor_id,
    )
    _replace_items(order, data)
    db.add(order)
    db.flush()
    add_audit_log(
        db,
        user_id=actor_id,
        action="create",
        table_name="purchase_orders",
        record_id=order.id,
        ip_address=ip_address,
        new_values=_snapshot(order),
    )
    _commit(db)
    return _order_or_error(db, order.id)


def update_purchase_order(
    db: Session,
    purchase_order_id: int,
    data: PurchaseOrderUpdate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> PurchaseOrder:
    order = _order_or_error(db, purchase_order_id, lock=True)
    if order.status != "draft":
        raise PurchaseOrderStateError("Only draft purchase orders can be edited.")
    _validate_entities(db, data)
    old_values = _snapshot(order)
    order.supplier_id = data.supplier_id
    order.notes = data.notes
    _replace_items(order, data)
    db.flush()
    add_audit_log(
        db,
        user_id=actor_id,
        action="update",
        table_name="purchase_orders",
        record_id=order.id,
        ip_address=ip_address,
        old_values=old_values,
        new_values=_snapshot(order),
    )
    _commit(db)
    return _order_or_error(db, order.id)


def submit_purchase_order(
    db: Session, purchase_order_id: int, *, actor_id: int, ip_address: str | None
) -> PurchaseOrder:
    order = _order_or_error(db, purchase_order_id, lock=True)
    if order.status != "draft":
        raise PurchaseOrderStateError("Only draft purchase orders can be submitted.")
    if not order.items:
        raise PurchaseOrderStateError("A purchase order must contain at least one item.")
    order.status = "pending_approval"
    order.submitted_at = _now()
    add_audit_log(
        db,
        user_id=actor_id,
        action="submit",
        table_name="purchase_orders",
        record_id=order.id,
        ip_address=ip_address,
        old_values={"status": "draft"},
        new_values={"status": order.status},
    )
    _commit(db)
    return _order_or_error(db, order.id)


def approve_purchase_order(
    db: Session,
    purchase_order_id: int,
    *,
    actor_id: int,
    actor_is_admin: bool = False,
    ip_address: str | None,
) -> PurchaseOrder:
    order = _order_or_error(db, purchase_order_id, lock=True)
    if order.status != "pending_approval":
        raise PurchaseOrderStateError("Only pending purchase orders can be approved.")
    if order.created_by == actor_id and not actor_is_admin:
        raise PurchaseOrderConflictError(
            "The user who created a purchase order cannot approve the same order."
        )
    order.status = "approved"
    order.approved_by = actor_id
    order.approved_at = _now()
    add_audit_log(
        db,
        user_id=actor_id,
        action="approve",
        table_name="purchase_orders",
        record_id=order.id,
        ip_address=ip_address,
        old_values={"status": "pending_approval"},
        new_values={"status": order.status, "approved_by": actor_id},
    )
    _commit(db)
    return _order_or_error(db, order.id)


def reject_purchase_order(
    db: Session,
    purchase_order_id: int,
    reason: str,
    *,
    actor_id: int,
    actor_is_admin: bool = False,
    ip_address: str | None,
) -> PurchaseOrder:
    order = _order_or_error(db, purchase_order_id, lock=True)
    if order.status != "pending_approval":
        raise PurchaseOrderStateError("Only pending purchase orders can be rejected.")
    if order.created_by == actor_id and not actor_is_admin:
        raise PurchaseOrderConflictError(
            "The user who created a purchase order cannot reject the same order."
        )
    order.status = "rejected"
    order.rejected_by = actor_id
    order.rejected_at = _now()
    order.rejection_reason = reason
    add_audit_log(
        db,
        user_id=actor_id,
        action="reject",
        table_name="purchase_orders",
        record_id=order.id,
        ip_address=ip_address,
        old_values={"status": "pending_approval"},
        new_values={"status": order.status, "reason": reason},
    )
    _commit(db)
    return _order_or_error(db, order.id)


def cancel_purchase_order(
    db: Session,
    purchase_order_id: int,
    reason: str,
    *,
    actor_id: int,
    ip_address: str | None,
) -> PurchaseOrder:
    order = _order_or_error(db, purchase_order_id, lock=True)
    if order.status not in {"draft", "pending_approval", "approved"}:
        raise PurchaseOrderStateError(
            "Only draft, pending, or approved purchase orders can be cancelled."
        )
    old_status = order.status
    order.status = "cancelled"
    order.cancelled_by = actor_id
    order.cancelled_at = _now()
    order.cancellation_reason = reason
    add_audit_log(
        db,
        user_id=actor_id,
        action="cancel",
        table_name="purchase_orders",
        record_id=order.id,
        ip_address=ip_address,
        old_values={"status": old_status},
        new_values={"status": order.status, "reason": reason},
    )
    _commit(db)
    return _order_or_error(db, order.id)


def receive_purchase_order(
    db: Session,
    purchase_order_id: int,
    data: GoodsReceiptCreate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> PurchaseOrder:
    order = _order_or_error(db, purchase_order_id, lock=True)
    if order.status != "approved":
        raise PurchaseOrderStateError("Only approved purchase orders can be received.")
    warehouse = warehouse_repository.get_warehouse(db, data.warehouse_id)
    if warehouse is None:
        from app.features.warehouses.exceptions import WarehouseNotFoundError

        raise WarehouseNotFoundError(data.warehouse_id)
    if not warehouse.is_active:
        raise PurchaseOrderEntityError("Goods can only be received into an active warehouse.")

    receipt = GoodsReceipt(
        number=f"GRN-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        purchase_order_id=order.id,
        warehouse_id=warehouse.id,
        notes=data.notes,
        received_by=actor_id,
    )
    db.add(receipt)
    db.flush()
    for item in order.items:
        product = inventory_repository.lock_product(db, item.product_id)
        if product is None or not product.is_active:
            raise PurchaseOrderEntityError(
                f"Product with id {item.product_id} is unavailable for receiving."
            )
        stock = inventory_repository.get_stock_level_for_update(
            db, item.product_id, warehouse.id
        )
        if stock is None:
            stock = StockLevel(
                product_id=item.product_id, warehouse_id=warehouse.id, quantity=0
            )
            db.add(stock)
            db.flush()
        stock.quantity += item.quantity
        db.add(
            StockMovement(
                product_id=item.product_id,
                warehouse_id=warehouse.id,
                type="in",
                quantity=item.quantity,
                reference_type="goods_receipt",
                reference_id=receipt.number,
                reason=data.notes or f"Received against {order.number}",
                created_by=actor_id,
            )
        )
        receipt.items.append(
            GoodsReceiptItem(product_id=item.product_id, quantity=item.quantity)
        )

    order.status = "received"
    add_audit_log(
        db,
        user_id=actor_id,
        action="receive",
        table_name="purchase_orders",
        record_id=order.id,
        ip_address=ip_address,
        old_values={"status": "approved"},
        new_values={
            "status": order.status,
            "goods_receipt_id": receipt.id,
            "goods_receipt_number": receipt.number,
            "warehouse_id": warehouse.id,
        },
    )
    _commit(db)
    return _order_or_error(db, order.id)


def list_goods_receipts(db: Session, *, page: int, size: int) -> dict:
    return {
        "items": repository.list_goods_receipts(
            db, offset=(page - 1) * size, limit=size
        ),
        "page": page,
        "size": size,
        "total": repository.count_goods_receipts(db),
    }


def get_goods_receipt(db: Session, receipt_id: int) -> GoodsReceipt:
    receipt = repository.get_goods_receipt(db, receipt_id)
    if receipt is None:
        raise GoodsReceiptNotFoundError(receipt_id)
    return receipt
