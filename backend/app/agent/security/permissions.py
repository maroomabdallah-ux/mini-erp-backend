from app.features.users.model import User
from app.agent.tools.registry import READ_ONLY_TOOLS
from langchain.tools import tool as langchain_tool

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
        user_permissions = get_user_permission_codes(user)

        if not required_permissions.issubset(user_permissions):
            raise PermissionError("Tool access denied.")

        return base_tool.invoke(kwargs)

    return langchain_tool(
        base_tool.name,
        description=base_tool.description,
        args_schema=base_tool.args_schema,
    )(run_secure_tool)