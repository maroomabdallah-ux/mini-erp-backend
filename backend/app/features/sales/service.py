from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.features.accounting.service import credit_limit_behavior
from app.features.audit.service import add_audit_log
from app.features.billing.models import Invoice
from app.features.customers import repository as customer_repository
from app.features.inventory import repository as inventory_repository
from app.features.inventory.models import StockMovement
from app.features.products import repository as product_repository
from app.features.quotations import repository as quotation_repository
from app.features.sales import repository
from app.features.sales.exceptions import (
    SalesOrderConversionError,
    SalesOrderNotFoundError,
    SalesOrderStateError,
    SalesOrderStockError,
)
from app.features.sales.models import SalesDelivery, SalesDeliveryItem, SalesOrder, SalesOrderItem
from app.features.sales.schemas import SalesDeliveryCreate, SalesOrderConfirm, SalesOrderCreate
from app.features.warehouses import repository as warehouse_repository


def _now() -> datetime:
    return datetime.now(UTC)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("The sales operation conflicted with another update.") from exc


def _get(db: Session, order_id: int, *, lock: bool = False) -> SalesOrder:
    order = repository.get_order(db, order_id, lock=lock)
    if order is None:
        raise SalesOrderNotFoundError(order_id)
    return order


def list_orders(
    db: Session,
    *,
    page: int,
    size: int,
    search: str | None,
    status: str | None,
    customer_id: int | None,
) -> dict:
    return {
        "items": repository.list_orders(
            db,
            offset=(page - 1) * size,
            limit=size,
            search=search,
            status=status,
            customer_id=customer_id,
        ),
        "page": page,
        "size": size,
        "total": repository.count_orders(db, search=search, status=status, customer_id=customer_id),
    }


def get_order(db: Session, order_id: int) -> SalesOrder:
    return _get(db, order_id)


def create_order(
    db: Session, data: SalesOrderCreate, *, actor_id: int, ip_address: str | None
) -> SalesOrder:
    customer = customer_repository.get_customer(db, data.customer_id)
    if customer is None or not customer.is_active:
        raise SalesOrderStateError("Sales orders require an active customer.")
    items = []
    gross = Decimal("0")
    net = Decimal("0")
    for input_item in data.items:
        product = product_repository.get_product(db, input_item.product_id)
        if product is None or not product.is_active:
            raise SalesOrderStateError(f"Product {input_item.product_id} is unavailable.")
        line_gross = input_item.unit_price * input_item.quantity
        line_total = (line_gross * (Decimal("100") - input_item.discount_percent) / 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        gross += line_gross
        net += line_total
        items.append(
            SalesOrderItem(
                product_id=input_item.product_id,
                quantity=input_item.quantity,
                unit_price=input_item.unit_price,
                discount_percent=input_item.discount_percent,
                line_total=line_total,
            )
        )
    order_discount = (net * data.discount_percent / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    discount_amount = gross - net + order_discount
    taxable = gross - discount_amount
    tax_amount = (taxable * data.tax_percent / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    order = SalesOrder(
        number=f"SO-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        customer_id=data.customer_id,
        notes=data.notes.strip() if data.notes else None,
        subtotal=gross,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        total_amount=taxable + tax_amount,
        created_by=actor_id,
        items=items,
    )
    db.add(order)
    db.flush()
    add_audit_log(
        db,
        user_id=actor_id,
        action="create",
        table_name="sales_orders",
        record_id=order.id,
        ip_address=ip_address,
        new_values={"number": order.number, "status": "draft", "source": "direct"},
    )
    _commit(db)
    return _get(db, order.id)


def convert_quotation(
    db: Session, quotation_id: int, *, actor_id: int, ip_address: str | None
) -> SalesOrder:
    quotation = quotation_repository.get_quotation(db, quotation_id, lock=True)
    if quotation is None:
        from app.features.quotations.exceptions import QuotationNotFoundError

        raise QuotationNotFoundError(quotation_id)
    if quotation.status != "accepted":
        raise SalesOrderConversionError(
            "Only accepted quotations can be converted to sales orders."
        )
    existing = repository.get_by_quotation(db, quotation_id)
    if existing is not None:
        raise SalesOrderConversionError(f"Quotation already converted to {existing.number}.")
    order = SalesOrder(
        number=f"SO-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        quotation_id=quotation.id,
        customer_id=quotation.customer_id,
        status="draft",
        notes=quotation.notes,
        subtotal=quotation.subtotal,
        discount_amount=quotation.discount_amount,
        tax_amount=quotation.tax_amount,
        total_amount=quotation.total_amount,
        created_by=actor_id,
        items=[
            SalesOrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_percent=item.discount_percent,
                line_total=item.line_total,
            )
            for item in quotation.items
        ],
    )
    db.add(order)
    db.flush()
    quotation.status = "converted"
    quotation.converted_at = _now()
    add_audit_log(
        db,
        user_id=actor_id,
        action="convert",
        table_name="quotations",
        record_id=quotation.id,
        ip_address=ip_address,
        old_values={"status": "accepted"},
        new_values={
            "status": "converted",
            "sales_order_id": order.id,
            "sales_order_number": order.number,
        },
    )
    add_audit_log(
        db,
        user_id=actor_id,
        action="create",
        table_name="sales_orders",
        record_id=order.id,
        ip_address=ip_address,
        new_values={
            "number": order.number,
            "quotation_id": quotation.id,
            "customer_id": order.customer_id,
            "status": order.status,
            "total_amount": f"{order.total_amount:.2f}",
        },
    )
    _commit(db)
    return _get(db, order.id)


def confirm_order(
    db: Session,
    order_id: int,
    data: SalesOrderConfirm,
    *,
    actor_id: int,
    ip_address: str | None,
) -> SalesOrder:
    order = _get(db, order_id, lock=True)
    if order.status != "draft":
        raise SalesOrderStateError("Only draft sales orders can be confirmed.")
    warehouse = warehouse_repository.get_warehouse(db, data.warehouse_id)
    if warehouse is None:
        from app.features.warehouses.exceptions import WarehouseNotFoundError

        raise WarehouseNotFoundError(data.warehouse_id)
    if not warehouse.is_active:
        raise SalesOrderStateError("Sales orders require an active warehouse.")

    shortages: dict[str, str] = {}
    for item in sorted(order.items, key=lambda value: value.product_id):
        stock = inventory_repository.get_stock_level_for_update(db, item.product_id, warehouse.id)
        available = stock.quantity if stock is not None else 0
        if available < item.quantity:
            shortages[f"line_{item.id}"] = (
                f"{item.product.sku}: available {available}, required {item.quantity}"
            )
    if shortages:
        db.rollback()
        raise SalesOrderStockError("Insufficient stock", field_errors=shortages)

    open_receivables = db.scalar(
        select(func.coalesce(func.sum(Invoice.total_amount - Invoice.paid_amount), 0)).where(
            Invoice.customer_id == order.customer_id,
            Invoice.document_type == "invoice",
            Invoice.status.in_(("issued", "partially_paid")),
        )
    ) or Decimal("0.00")
    exposure = open_receivables + order.total_amount
    limit_exceeded = exposure > order.customer.credit_limit
    if limit_exceeded and credit_limit_behavior(db) == "block":
        db.rollback()
        raise SalesOrderStateError(
            "Customer credit limit exceeded.",
            field_errors={
                "credit_limit": f"Limit {order.customer.credit_limit:.2f}",
                "open_receivables": f"Open receivables {open_receivables:.2f}",
                "order_total": f"Order total {order.total_amount:.2f}",
                "exposure": f"Resulting exposure {exposure:.2f}",
            },
        )
    order.credit_warning = (
        f"Credit limit {order.customer.credit_limit:.2f} exceeded; exposure {exposure:.2f}."
        if limit_exceeded
        else None
    )
    order.warehouse_id = warehouse.id
    order.status = "confirmed"
    order.confirmed_by = actor_id
    order.confirmed_at = _now()
    add_audit_log(
        db,
        user_id=actor_id,
        action="confirm",
        table_name="sales_orders",
        record_id=order.id,
        ip_address=ip_address,
        old_values={"status": "draft"},
        new_values={
            "status": "confirmed",
            "warehouse_id": warehouse.id,
            "open_receivables": f"{open_receivables:.2f}",
            "credit_exposure": f"{exposure:.2f}",
        },
    )
    _commit(db)
    return _get(db, order.id)


def cancel_order(
    db: Session, order_id: int, reason: str, *, actor_id: int, ip_address: str | None
) -> SalesOrder:
    order = _get(db, order_id, lock=True)
    if order.status not in {"draft", "confirmed"}:
        raise SalesOrderStateError("Only draft or confirmed sales orders can be cancelled.")
    old = order.status
    order.status = "cancelled"
    order.cancelled_by = actor_id
    order.cancelled_at = _now()
    order.cancellation_reason = reason
    add_audit_log(
        db,
        user_id=actor_id,
        action="cancel",
        table_name="sales_orders",
        record_id=order.id,
        ip_address=ip_address,
        old_values={"status": old},
        new_values={"status": "cancelled", "reason": reason},
    )
    _commit(db)
    return _get(db, order.id)


def availability(db: Session, order_id: int) -> list[dict]:
    order = _get(db, order_id)
    warehouses = warehouse_repository.list_warehouses(
        db, offset=0, limit=100, search=None, is_active=True
    )
    result = []
    for warehouse in warehouses:
        items = []
        for item in order.items:
            rows = inventory_repository.list_stock_levels(
                db,
                offset=0,
                limit=1,
                product_id=item.product_id,
                warehouse_id=warehouse.id,
                search=None,
            )
            available = rows[0].quantity if rows else 0
            items.append(
                {
                    "product_id": item.product_id,
                    "sku": item.product.sku,
                    "name": item.product.name,
                    "required": item.quantity,
                    "available": available,
                    "sufficient": available >= item.quantity,
                }
            )
        result.append(
            {
                "warehouse": warehouse,
                "ready": all(item["sufficient"] for item in items),
                "items": items,
            }
        )
    return result


def deliver_order(
    db: Session, order_id: int, data: SalesDeliveryCreate, *, actor_id: int, ip_address: str | None
) -> SalesOrder:
    order = _get(db, order_id, lock=True)
    if order.status != "confirmed":
        raise SalesOrderStateError("Only confirmed sales orders can be delivered.")
    if order.warehouse_id is None:
        raise SalesOrderStateError("Confirmed sales order has no selected warehouse.")
    warehouse = warehouse_repository.get_warehouse(db, order.warehouse_id)
    if warehouse is None:
        from app.features.warehouses.exceptions import WarehouseNotFoundError

        raise WarehouseNotFoundError(order.warehouse_id)
    if not warehouse.is_active:
        raise SalesOrderStateError("Sales orders require an active delivery warehouse.")
    locked = {}
    for item in sorted(order.items, key=lambda value: value.product_id):
        stock = inventory_repository.get_stock_level_for_update(db, item.product_id, warehouse.id)
        available = stock.quantity if stock is not None else 0
        if stock is None or available < item.quantity:
            db.rollback()
            raise SalesOrderStockError(
                f"Insufficient stock for {item.product.sku} in {warehouse.code}: "
                f"required {item.quantity}, available {available}."
            )
        locked[item.product_id] = stock
    delivery = SalesDelivery(
        number=f"SDN-{uuid4().hex[:12].upper()}",
        sales_order_id=order.id,
        warehouse_id=warehouse.id,
        notes=data.notes,
        delivered_by=actor_id,
        items=[
            SalesDeliveryItem(product_id=item.product_id, quantity=item.quantity)
            for item in order.items
        ],
    )
    db.add(delivery)
    db.flush()
    for item in order.items:
        locked[item.product_id].quantity -= item.quantity
        db.add(
            StockMovement(
                product_id=item.product_id,
                warehouse_id=warehouse.id,
                type="out",
                quantity=-item.quantity,
                reference_type="sales_delivery",
                reference_id=delivery.number,
                reason=data.notes or f"Delivered {order.number}",
                created_by=actor_id,
            )
        )
    order.status = "delivered"
    add_audit_log(
        db,
        user_id=actor_id,
        action="deliver",
        table_name="sales_orders",
        record_id=order.id,
        ip_address=ip_address,
        old_values={"status": "confirmed"},
        new_values={
            "status": "delivered",
            "delivery_number": delivery.number,
            "warehouse_id": warehouse.id,
        },
    )
    _commit(db)
    return _get(db, order.id)
