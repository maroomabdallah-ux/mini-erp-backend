from app.agent.tools.customer_tools import (
    get_customer,
    search_customers,
)
from app.agent.tools.inventory_tools import (
    get_low_stock_products,
    get_stock,
)
from app.agent.tools.product_tools import get_products
from app.agent.tools.report_tools import (
    get_dashboard_summary,
    get_monthly_sales,
    get_profit_report,
    get_receivables_aging,
    get_top_products,
)

READ_ONLY_TOOLS = [
    get_products,
    get_low_stock_products,
    get_stock,
    get_customer,
    search_customers,
    get_dashboard_summary,
    get_monthly_sales,
     get_top_products,
     get_profit_report,
     get_receivables_aging,
]