import logging
from time import perf_counter

from langchain.tools import tool as langchain_tool

from app.agent.tools.registry import READ_ONLY_TOOLS
from app.features.users.model import User

logger = logging.getLogger(__name__)

TOOL_PERMISSIONS: dict[str, set[str]] = {
    "get_products": {
        "products.read",
    },

    "get_low_stock_products": {
        "inventory.low_stock.read",
    },

    "get_stock": {
        "inventory.read",
    },

    "get_customer": {
        "customers.read",
    },

    "search_customers": {
        "customers.read",
    },

    "search_suppliers": {
        "suppliers.read",
    },

    "get_supplier": {
        "suppliers.read",
    },

    "get_purchase_orders": {
        "purchase_orders.read",
    },

    "get_purchase_order": {
        "purchase_orders.read",
    },

    "get_pending_purchase_orders": {
        "purchase_orders.read",
    },

    "get_goods_receipts": {
        "goods_receipts.read",
    },

    "get_quotations": {
        "quotations.read",
    },

    "get_quotation": {
        "quotations.read",
    },

    "get_sales_orders": {
        "sales_orders.read",
    },

    "get_sales_order": {
        "sales_orders.read",
    },

    "get_invoices": {
        "invoices.read",
    },

    "get_customer_sales": {
        "sales_orders.read",
        "invoices.read",
    },

    "get_stock_movements": {
        "inventory.read",
    },

    "get_inventory_by_warehouse": {
        "inventory.read",
    },

    "get_inventory_counts": {
        "inventory.read",
    },

    "get_customer_statement": {
        "customer_statements.read",
    },

    "get_supplier_statement": {
        "supplier_statements.read",
    },

    "get_invoice_balance": {
        "invoices.read",
    },

    "get_journal_entries": {
        "journal_entries.read",
    },

    "get_inventory_valuation": {
        "reports.inventory_valuation.read",
    },

    "get_monthly_sales": {
        "reports.monthly_sales.read",
    },

    "get_top_products": {
        "reports.top_products.read",
    },

    "get_profit_report": {
        "reports.profit.read",
    },

    "get_receivables_aging": {
        "reports.receivables.read",
    },

    "get_dashboard_summary": {
        "reports.profit.read",
        "reports.inventory_valuation.read",
        "reports.receivables.read",
        "inventory.low_stock.read",
        "purchase_orders.read",
        "quotations.read",
        "invoices.read",
    },
}


def get_user_permission_codes(user: User) -> set[str]:
    """
    Return all permissions assigned through active roles.
    """

    return {
        permission.code
        for role in user.roles
        if role.is_active
        for permission in role.permissions
    }


def user_can_use_tool(user: User, tool_name: str) -> bool:
    """
    Check whether the current user has all permissions
    required to use a specific Agent tool.
    """

    required_permissions = TOOL_PERMISSIONS.get(tool_name)

    if required_permissions is None:
        return False

    user_permissions = get_user_permission_codes(user)

    return required_permissions.issubset(user_permissions)


def get_allowed_tools(user: User):
    """
    Return only the LangChain tools that the current
    ERP user is authorized to use.
    """

    return [
        tool
        for tool in READ_ONLY_TOOLS
        if user_can_use_tool(user, tool.name)
    ]

def secure_tool_for_user(user: User, base_tool):
    """
    Wrap a LangChain tool with a second permission check.

    Even if the tool is accidentally exposed to a user,
    execution will be blocked unless the user has all
    required ERP permissions.
    """

    required_permissions = TOOL_PERMISSIONS.get(base_tool.name)

    if required_permissions is None:
        raise PermissionError(
            f"No permission policy configured for tool: {base_tool.name}"
        )

    def run_secure_tool(**kwargs):
        started_at = perf_counter()
        user_permissions = get_user_permission_codes(user)

        if not required_permissions.issubset(user_permissions):
            logger.warning(
                "agent_tool_denied user_id=%s tool=%s duration_ms=%.2f",
                user.id,
                base_tool.name,
                (perf_counter() - started_at) * 1000,
            )
            raise PermissionError("Tool access denied.")

        try:
            result = base_tool.invoke(kwargs)
        except Exception as exc:
            logger.exception(
                "agent_tool_failed user_id=%s tool=%s error_category=%s duration_ms=%.2f",
                user.id,
                base_tool.name,
                type(exc).__name__,
                (perf_counter() - started_at) * 1000,
            )
            raise
        logger.info(
            "agent_tool_succeeded user_id=%s tool=%s duration_ms=%.2f",
            user.id,
            base_tool.name,
            (perf_counter() - started_at) * 1000,
        )
        return result

    return langchain_tool(
        base_tool.name,
        description=base_tool.description,
        args_schema=base_tool.args_schema,
    )(run_secure_tool)
