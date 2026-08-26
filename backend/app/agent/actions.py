from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.agent import repository
from app.agent.action_schemas import (
    PreparePurchaseOrderRequest,
    PrepareQuotationRequest,
    PrepareSalesOrderConfirmationRequest,
)
from app.agent.models import AgentPendingAction
from app.core.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.features.audit.service import add_audit_log
from app.features.customers.service import get_customer
from app.features.products.service import get_product
from app.features.purchases.schemas import PurchaseOrderCreate, PurchaseOrderItemInput
from app.features.purchases.service import create_purchase_order, preview_purchase_order
from app.features.quotations.schemas import QuotationCreate, QuotationItemInput
from app.features.quotations.service import create_quotation, preview_quotation
from app.features.sales.schemas import SalesOrderConfirm
from app.features.sales.service import confirm_order, validate_order_confirmation
from app.features.suppliers.service import get_supplier
from app.features.users.model import User
from app.features.warehouses.service import get_warehouse

CREATE_QUOTATION_PERMISSION = "quotations.manage"
CREATE_QUOTATION_ACTION = "create_quotation"
CREATE_PURCHASE_ORDER_PERMISSION = "purchase_orders.create"
CREATE_PURCHASE_ORDER_ACTION = "create_purchase_order"
CONFIRM_SALES_ORDER_PERMISSION = "sales_orders.confirm"
CONFIRM_SALES_ORDER_ACTION = "confirm_sales_order"

ACTION_PERMISSIONS = {
    CREATE_QUOTATION_ACTION: CREATE_QUOTATION_PERMISSION,
    CREATE_PURCHASE_ORDER_ACTION: CREATE_PURCHASE_ORDER_PERMISSION,
    CONFIRM_SALES_ORDER_ACTION: CONFIRM_SALES_ORDER_PERMISSION,
}

ACTION_TABLES = {
    CREATE_QUOTATION_ACTION: "quotations",
    CREATE_PURCHASE_ORDER_ACTION: "purchase_orders",
    CONFIRM_SALES_ORDER_ACTION: "sales_orders",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _has_permission(user: User, permission_code: str) -> bool:
    return any(
        permission.code == permission_code
        for role in user.roles
        if role.is_active
        for permission in role.permissions
    )


def _require_permission(user: User, permission_code: str) -> None:
    if not _has_permission(user, permission_code):
        raise ForbiddenError("You cannot perform this action.")


def _store_pending_action(
    db: Session,
    *,
    user: User,
    conversation_id: int,
    action_type: str,
    payload: dict,
    summary: dict,
) -> AgentPendingAction:
    existing_actions = repository.list_pending_actions_for_update(
        db,
        user_id=user.id,
        conversation_id=conversation_id,
        action_type=action_type,
    )
    action = next(
        (
            existing
            for existing in existing_actions
            if existing.payload == payload and existing.expires_at > _now()
        ),
        None,
    )
    if action is None:
        for existing in existing_actions:
            existing.status = "cancelled"
        action = AgentPendingAction(
            user_id=user.id,
            conversation_id=conversation_id,
            action_type=action_type,
            payload=payload,
            summary=summary,
            expires_at=_now() + timedelta(minutes=settings.agent_pending_action_minutes),
        )
        db.add(action)
        db.commit()
        db.refresh(action)
    else:
        for existing in existing_actions:
            if existing.id != action.id:
                existing.status = "cancelled"
        db.commit()
    return action


def _pending_result(action: AgentPendingAction) -> dict:
    return {
        "action_id": action.id,
        "action_type": action.action_type,
        "status": action.status,
        "expires_at": action.expires_at,
        "summary": action.summary,
    }


def _require_owned_conversation(db: Session, conversation_id: int, user_id: int) -> None:
    if repository.get_conversation(db, conversation_id, user_id) is None:
        raise NotFoundError("Conversation was not found.")


def prepare_create_quotation(
    db: Session,
    *,
    user: User,
    conversation_id: int,
    request: PrepareQuotationRequest,
) -> dict:
    _require_permission(user, CREATE_QUOTATION_PERMISSION)
    _require_owned_conversation(db, conversation_id, user.id)
    customer = get_customer(db, request.customer_id)
    products = [get_product(db, item.product_id) for item in request.items]
    data = QuotationCreate(
        customer_id=request.customer_id,
        valid_until=request.valid_until,
        notes=request.notes,
        discount_percent=request.discount_percent,
        tax_percent=request.tax_percent,
        items=[
            QuotationItemInput(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=product.sale_price,
                discount_percent=item.discount_percent,
            )
            for item, product in zip(request.items, products, strict=True)
        ],
    )
    preview = preview_quotation(db, data)
    summary = {
        "customer": {"id": customer.id, "code": customer.code, "name": customer.name},
        "valid_until": data.valid_until.isoformat(),
        "items": [
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": item.quantity,
                "unit_price": str(product.sale_price),
                "discount_percent": str(item.discount_percent),
                "line_total": str(preview.items[index].line_total),
            }
            for index, (item, product) in enumerate(zip(request.items, products, strict=True))
        ],
        "subtotal": str(preview.subtotal),
        "discount_amount": str(preview.discount_amount),
        "tax_amount": str(preview.tax_amount),
        "total_amount": str(preview.total_amount),
        "confirmation_required": True,
    }
    action = _store_pending_action(
        db,
        user=user,
        conversation_id=conversation_id,
        action_type=CREATE_QUOTATION_ACTION,
        payload=data.model_dump(mode="json"),
        summary=summary,
    )
    return _pending_result(action)


def prepare_create_purchase_order(
    db: Session,
    *,
    user: User,
    conversation_id: int,
    request: PreparePurchaseOrderRequest,
) -> dict:
    _require_permission(user, CREATE_PURCHASE_ORDER_PERMISSION)
    _require_owned_conversation(db, conversation_id, user.id)
    supplier = get_supplier(db, request.supplier_id)
    warehouse = get_warehouse(db, request.warehouse_id)
    products = [get_product(db, item.product_id) for item in request.items]
    data = PurchaseOrderCreate(
        supplier_id=request.supplier_id,
        warehouse_id=request.warehouse_id,
        expected_date=request.expected_date,
        notes=request.notes,
        items=[
            PurchaseOrderItemInput(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_cost=product.cost_price,
            )
            for item, product in zip(request.items, products, strict=True)
        ],
    )
    preview = preview_purchase_order(db, data)
    summary = {
        "supplier": {"id": supplier.id, "name": supplier.name},
        "warehouse": {"id": warehouse.id, "code": warehouse.code, "name": warehouse.name},
        "expected_date": data.expected_date.isoformat(),
        "items": [
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": item.quantity,
                "unit_cost": str(product.cost_price),
                "line_total": str(preview.items[index].line_total),
            }
            for index, (item, product) in enumerate(zip(request.items, products, strict=True))
        ],
        "total_amount": str(preview.total_amount),
        "confirmation_required": True,
    }
    action = _store_pending_action(
        db,
        user=user,
        conversation_id=conversation_id,
        action_type=CREATE_PURCHASE_ORDER_ACTION,
        payload=data.model_dump(mode="json"),
        summary=summary,
    )
    return _pending_result(action)


def prepare_confirm_sales_order(
    db: Session,
    *,
    user: User,
    conversation_id: int,
    request: PrepareSalesOrderConfirmationRequest,
) -> dict:
    _require_permission(user, CONFIRM_SALES_ORDER_PERMISSION)
    _require_owned_conversation(db, conversation_id, user.id)
    confirmation = SalesOrderConfirm(warehouse_id=request.warehouse_id)
    order, warehouse, open_receivables, exposure, limit_exceeded = (
        validate_order_confirmation(db, request.sales_order_id, confirmation)
    )
    payload = request.model_dump(mode="json")
    summary = {
        "sales_order": {"id": order.id, "number": order.number},
        "customer": {
            "id": order.customer.id,
            "code": order.customer.code,
            "name": order.customer.name,
        },
        "warehouse": {"id": warehouse.id, "code": warehouse.code, "name": warehouse.name},
        "current_status": order.status,
        "items": [
            {
                "product_id": item.product.id,
                "sku": item.product.sku,
                "name": item.product.name,
                "quantity": item.quantity,
                "line_total": str(item.line_total),
            }
            for item in order.items
        ],
        "total_amount": str(order.total_amount),
        "open_receivables": str(open_receivables),
        "resulting_exposure": str(exposure),
        "credit_limit_warning": limit_exceeded,
        "confirmation_required": True,
    }
    action = _store_pending_action(
        db,
        user=user,
        conversation_id=conversation_id,
        action_type=CONFIRM_SALES_ORDER_ACTION,
        payload=payload,
        summary=summary,
    )
    return _pending_result(action)


def _confirm_quotation(
    db: Session, action: AgentPendingAction, user: User, ip_address: str | None
) -> dict:
    data = QuotationCreate.model_validate(action.payload)
    quotation = create_quotation(
        db, data, actor_id=user.id, ip_address=ip_address, commit=False
    )
    action.quotation_id = quotation.id
    return {
        "action_type": CREATE_QUOTATION_ACTION,
        "quotation_id": quotation.id,
        "quotation_number": quotation.number,
        "total_amount": f"{quotation.total_amount:.2f}",
        "table_name": "quotations",
        "record_id": quotation.id,
        "audit_values": {
            "customer_id": quotation.customer_id,
            "item_count": len(data.items),
            "total_amount": f"{quotation.total_amount:.2f}",
        },
    }


def _confirm_purchase_order(
    db: Session, action: AgentPendingAction, user: User, ip_address: str | None
) -> dict:
    data = PurchaseOrderCreate.model_validate(action.payload)
    order = create_purchase_order(
        db, data, actor_id=user.id, ip_address=ip_address, commit=False
    )
    action.purchase_order_id = order.id
    return {
        "action_type": CREATE_PURCHASE_ORDER_ACTION,
        "purchase_order_id": order.id,
        "purchase_order_number": order.number,
        "total_amount": f"{order.total_amount:.2f}",
        "table_name": "purchase_orders",
        "record_id": order.id,
        "audit_values": {
            "supplier_id": order.supplier_id,
            "warehouse_id": order.warehouse_id,
            "item_count": len(data.items),
            "total_amount": f"{order.total_amount:.2f}",
        },
    }


def _confirm_sales_order(
    db: Session, action: AgentPendingAction, user: User, ip_address: str | None
) -> dict:
    request = PrepareSalesOrderConfirmationRequest.model_validate(action.payload)
    order = confirm_order(
        db,
        request.sales_order_id,
        SalesOrderConfirm(warehouse_id=request.warehouse_id),
        actor_id=user.id,
        ip_address=ip_address,
        commit=False,
    )
    action.sales_order_id = order.id
    return {
        "action_type": CONFIRM_SALES_ORDER_ACTION,
        "sales_order_id": order.id,
        "sales_order_number": order.number,
        "total_amount": f"{order.total_amount:.2f}",
        "table_name": "sales_orders",
        "record_id": order.id,
        "audit_values": {
            "old_status": "draft",
            "new_status": order.status,
            "warehouse_id": order.warehouse_id,
        },
    }


def confirm_pending_action(
    db: Session,
    *,
    action_id: int,
    user: User,
    ip_address: str | None,
) -> dict:
    action = repository.get_pending_action_for_update(db, action_id, user.id)
    if action is None:
        raise NotFoundError("Pending action was not found.")
    permission = ACTION_PERMISSIONS.get(action.action_type)
    if permission is None:
        raise ConflictError("This action type is not supported.")
    _require_permission(user, permission)
    if action.status == "executed":
        raise ConflictError("This action has already been completed.")
    if action.status != "pending":
        raise ConflictError("This action is no longer available.")
    if action.expires_at <= _now():
        action.status = "expired"
        db.commit()
        raise ConflictError("This action has expired.")

    try:
        if action.action_type == CREATE_QUOTATION_ACTION:
            result = _confirm_quotation(db, action, user, ip_address)
        elif action.action_type == CREATE_PURCHASE_ORDER_ACTION:
            result = _confirm_purchase_order(db, action, user, ip_address)
        else:
            result = _confirm_sales_order(db, action, user, ip_address)
        action.status = "executed"
        action.executed_at = _now()
        table_name = result.pop("table_name")
        record_id = result.pop("record_id")
        audit_values = result.pop("audit_values")
        add_audit_log(
            db,
            user_id=user.id,
            action=f"agent_{action.action_type}",
            table_name=table_name,
            record_id=record_id,
            ip_address=ip_address,
            new_values={
                "conversation_id": action.conversation_id,
                "pending_action_id": action.id,
                "success": True,
                **audit_values,
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        failed_action = repository.get_pending_action_for_update(db, action_id, user.id)
        if failed_action is not None and failed_action.status == "pending":
            failed_action.status = "failed"
            failed_action.failure_category = type(exc).__name__[:100]
            add_audit_log(
                db,
                user_id=user.id,
                action=f"agent_{action.action_type}",
                table_name=ACTION_TABLES[action.action_type],
                ip_address=ip_address,
                new_values={
                    "conversation_id": failed_action.conversation_id,
                    "pending_action_id": failed_action.id,
                    "success": False,
                    "error_category": type(exc).__name__,
                },
            )
            db.commit()
        raise

    return {"action_id": action.id, "status": "executed", **result}


def cancel_pending_action(db: Session, *, action_id: int, user: User) -> dict:
    action = repository.get_pending_action_for_update(db, action_id, user.id)
    if action is None:
        raise NotFoundError("Pending action was not found.")
    permission = ACTION_PERMISSIONS.get(action.action_type)
    if permission is None:
        raise ConflictError("This action type is not supported.")
    _require_permission(user, permission)
    if action.status != "pending":
        raise ConflictError("This action is no longer available.")
    action.status = "cancelled"
    db.commit()
    return {"action_id": action.id, "status": "cancelled"}
