from enum import Enum


class AgentPermission(str, Enum):
    VIEW_PRODUCTS = "view_products"
    VIEW_CUSTOMERS = "view_customers"
    VIEW_SALES = "view_sales"
    VIEW_INVOICES = "view_invoices"
    VIEW_PAYMENTS = "view_payments"
    VIEW_STOCK = "view_stock"
    VIEW_PURCHASES = "view_purchases"
    VIEW_FINANCIALS = "view_financials"


ROLE_PERMISSIONS = {
    "Admin": {
        AgentPermission.VIEW_PRODUCTS,
        AgentPermission.VIEW_CUSTOMERS,
        AgentPermission.VIEW_SALES,
        AgentPermission.VIEW_INVOICES,
        AgentPermission.VIEW_PAYMENTS,
        AgentPermission.VIEW_STOCK,
        AgentPermission.VIEW_PURCHASES,
        AgentPermission.VIEW_FINANCIALS,
    },

    "Manager": {
        AgentPermission.VIEW_PRODUCTS,
        AgentPermission.VIEW_CUSTOMERS,
        AgentPermission.VIEW_SALES,
        AgentPermission.VIEW_INVOICES,
        AgentPermission.VIEW_PAYMENTS,
        AgentPermission.VIEW_STOCK,
        AgentPermission.VIEW_PURCHASES,
        AgentPermission.VIEW_FINANCIALS,
    },

    "Sales": {
        AgentPermission.VIEW_PRODUCTS,
        AgentPermission.VIEW_CUSTOMERS,
        AgentPermission.VIEW_SALES,
        AgentPermission.VIEW_INVOICES,
    },

    "Warehouse": {
        AgentPermission.VIEW_PRODUCTS,
        AgentPermission.VIEW_STOCK,
    },

    "Purchasing Officer": {
        AgentPermission.VIEW_PRODUCTS,
        AgentPermission.VIEW_PURCHASES,
        AgentPermission.VIEW_STOCK,
    },
}