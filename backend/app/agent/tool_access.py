from app.agent.permissions import (
    AgentPermission,
    has_permission,
)


def get_tools_for_role(role: str, tools: dict):
    allowed_tools = []

    if has_permission(role, AgentPermission.VIEW_PRODUCTS):
        if "get_products" in tools:
            allowed_tools.append(tools["get_products"])

    if has_permission(role, AgentPermission.VIEW_CUSTOMERS):
        if "get_customers" in tools:
            allowed_tools.append(tools["get_customers"])

    if has_permission(role, AgentPermission.VIEW_SALES):
        if "get_sales" in tools:
            allowed_tools.append(tools["get_sales"])

    if has_permission(role, AgentPermission.VIEW_INVOICES):
        if "get_invoices" in tools:
            allowed_tools.append(tools["get_invoices"])

    if has_permission(role, AgentPermission.VIEW_PAYMENTS):
        if "get_payments" in tools:
            allowed_tools.append(tools["get_payments"])

    if has_permission(role, AgentPermission.VIEW_STOCK):
        if "get_stock" in tools:
            allowed_tools.append(tools["get_stock"])

    if has_permission(role, AgentPermission.VIEW_PURCHASES):
        if "get_purchase_orders" in tools:
            allowed_tools.append(tools["get_purchase_orders"])

    if has_permission(role, AgentPermission.VIEW_FINANCIALS):
        if "get_financial_summary" in tools:
            allowed_tools.append(tools["get_financial_summary"])

    return allowed_tools