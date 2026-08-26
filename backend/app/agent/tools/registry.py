from app.agent.tools.accounting_tools import (
    get_customer_statement,
    get_inventory_valuation,
    get_invoice_balance,
    get_journal_entries,
    get_supplier_statement,
)
from app.agent.tools.customer_tools import (
    get_customer,
    search_customers,
)
from app.agent.tools.inventory_tools import (
    get_low_stock_products,
    get_stock,
)
from app.agent.tools.product_tools import get_products
from app.agent.tools.purchase_tools import (
    get_goods_receipts,
    get_pending_purchase_orders,
    get_purchase_order,
    get_purchase_orders,
)
from app.agent.tools.report_tools import (
    get_dashboard_summary,
    get_monthly_sales,
    get_profit_report,
    get_receivables_aging,
    get_top_products,
)
from app.agent.tools.sales_tools import (
    get_customer_sales,
    get_invoices,
    get_quotation,
    get_quotations,
    get_sales_order,
    get_sales_orders,
)
from app.agent.tools.supplier_tools import get_supplier, search_suppliers
from app.agent.tools.warehouse_tools import (
    get_inventory_by_warehouse,
    get_inventory_counts,
    get_stock_movements,
)

READ_ONLY_TOOLS = [
    get_products,
    get_low_stock_products,
    get_stock,
    get_customer,
    search_customers,
    search_suppliers,
    get_supplier,
    get_purchase_orders,
    get_purchase_order,
    get_pending_purchase_orders,
    get_goods_receipts,
    get_quotations,
    get_quotation,
    get_sales_orders,
    get_sales_order,
    get_invoices,
    get_customer_sales,
    get_stock_movements,
    get_inventory_by_warehouse,
    get_inventory_counts,
    get_customer_statement,
    get_supplier_statement,
    get_invoice_balance,
    get_journal_entries,
    get_inventory_valuation,
    get_dashboard_summary,
    get_monthly_sales,
     get_top_products,
     get_profit_report,
     get_receivables_aging,
]
