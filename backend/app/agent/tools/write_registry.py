from datetime import date
from decimal import Decimal

from langchain.tools import tool

from app.agent.action_schemas import (
    PreparePurchaseOrderItem,
    PreparePurchaseOrderRequest,
    PrepareQuotationItem,
    PrepareQuotationRequest,
    PrepareSalesOrderConfirmationRequest,
)
from app.agent.actions import (
    CONFIRM_SALES_ORDER_PERMISSION,
    CREATE_PURCHASE_ORDER_PERMISSION,
    CREATE_QUOTATION_PERMISSION,
    prepare_create_purchase_order,
    prepare_create_quotation,
    prepare_confirm_sales_order,
)
from app.db.session import SessionLocal
from app.features.users.model import User


def _has_permission(user: User, permission_code: str) -> bool:
    return any(
        permission.code == permission_code
        for role in user.roles
        if role.is_active
        for permission in role.permissions
    )


def get_write_tools_for_user(user: User, conversation_id: int):
    """Build preparation-only write capabilities for the current user and conversation."""
    write_tools = []

    if _has_permission(user, CREATE_QUOTATION_PERMISSION):

        @tool("prepare_create_quotation")
        def prepare_quotation(
            customer_id: int,
            valid_until: date,
            items: list[PrepareQuotationItem],
            notes: str | None = None,
            discount_percent: Decimal = Decimal("0.00"),
            tax_percent: Decimal = Decimal("0.00"),
        ) -> dict:
            """Prepare a quotation for explicit backend confirmation; never create it."""
            db = SessionLocal()
            try:
                return prepare_create_quotation(
                    db,
                    user=user,
                    conversation_id=conversation_id,
                    request=PrepareQuotationRequest(
                        customer_id=customer_id,
                        valid_until=valid_until,
                        items=items,
                        notes=notes,
                        discount_percent=discount_percent,
                        tax_percent=tax_percent,
                    ),
                )
            finally:
                db.close()

        write_tools.append(prepare_quotation)

    if _has_permission(user, CREATE_PURCHASE_ORDER_PERMISSION):

        @tool("prepare_create_purchase_order")
        def prepare_purchase_order(
            supplier_id: int,
            warehouse_id: int,
            expected_date: date,
            items: list[PreparePurchaseOrderItem],
            notes: str | None = None,
        ) -> dict:
            """Prepare a purchase order for explicit backend confirmation; never create it."""
            db = SessionLocal()
            try:
                return prepare_create_purchase_order(
                    db,
                    user=user,
                    conversation_id=conversation_id,
                    request=PreparePurchaseOrderRequest(
                        supplier_id=supplier_id,
                        warehouse_id=warehouse_id,
                        expected_date=expected_date,
                        items=items,
                        notes=notes,
                    ),
                )
            finally:
                db.close()

        write_tools.append(prepare_purchase_order)

    if _has_permission(user, CONFIRM_SALES_ORDER_PERMISSION):

        @tool("prepare_confirm_sales_order")
        def prepare_sales_order_confirmation(
            sales_order_id: int,
            warehouse_id: int,
        ) -> dict:
            """Prepare a sales-order confirmation for explicit backend approval."""
            db = SessionLocal()
            try:
                return prepare_confirm_sales_order(
                    db,
                    user=user,
                    conversation_id=conversation_id,
                    request=PrepareSalesOrderConfirmationRequest(
                        sales_order_id=sales_order_id,
                        warehouse_id=warehouse_id,
                    ),
                )
            finally:
                db.close()

        write_tools.append(prepare_sales_order_confirmation)

    return write_tools


WRITE_TOOL_FACTORIES = [get_write_tools_for_user]
WRITE_TOOLS = WRITE_TOOL_FACTORIES
