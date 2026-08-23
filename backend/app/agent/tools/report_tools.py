from datetime import date, timedelta

from langchain.tools import tool

from app.db.session import SessionLocal
from app.features.reports.service import (
    dashboard,
    monthly_sales,
    top_products,
     profit,
     receivables_aging,
)

@tool
def get_dashboard_summary() -> dict:

    """
    Get a high-level summary of the Mini ERP.

    Use this tool when the user asks about:
    - current business performance
    - this month's sales or profit
    - receivables
    - inventory value
    - overdue invoices
    - low stock products
    - pending purchase approvals
    """

    db = SessionLocal()

    try:
        result = dashboard(db)

        return {
            "sales_this_month": str(result["sales_this_month"]),
            "profit_this_month": str(result["profit_this_month"]),
            "receivables": str(result["receivables"]),
            "inventory_value": str(result["inventory_value"]),
            "overdue_invoices": result["overdue_invoices"],
            "low_stock_products": result["low_stock_products"],
            "pending_purchase_approvals": result["pending_purchase_approvals"],
            "quotations_expiring_soon": result["quotations_expiring_soon"],
        }

    finally:
        db.close()


@tool
def get_monthly_sales(months: int = 6) -> list[dict]:
    """
    Get monthly sales for the Mini ERP.

    Use this tool when the user asks about:
    - monthly sales
    - sales trends
    - sales over the last few months
    - invoice count by month
    """

    months = max(1, min(months, 12))

    db = SessionLocal()

    try:
        result = monthly_sales(db, months)

        return [
            {
                "month": row["month"],
                "invoice_count": row["invoice_count"],
                "net_sales": str(row["net_sales"]),
            }
            for row in result
        ]

    finally:
        db.close()




@tool
def get_top_products(
    days: int = 30,
    limit: int = 5,
    sort_by: str = "revenue",
) -> list[dict]:
    """
    Get the top-selling products from the Mini ERP.

    Use this tool when the user asks about:
    - best-selling products
    - top products by revenue
    - top products by quantity sold

    sort_by must be either:
    - revenue
    - quantity
    """
#Guardrails
    days = max(1, min(days, 365))
    limit = max(1, min(limit, 20))

    if sort_by not in {"revenue", "quantity"}:
        raise ValueError("sort_by must be 'revenue' or 'quantity'")

    date_to = date.today()
    date_from = date_to - timedelta(days=days)

    db = SessionLocal()

    try:
        result = top_products(
            db,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            sort_by=sort_by,
        )

        return [
            {
                "product_id": row["product_id"],
                "sku": row["sku"],
                "product_name": row["product_name"],
                "quantity_sold": row["quantity_sold"],
                "net_sales": str(row["net_sales"]),
            }
            for row in result
        ]

    finally:
        db.close()




@tool
def get_profit_report(
    days: int = 30,
    category_id: int | None = None,
) -> dict:
    """
    Get the profit report for the Mini ERP.

    Use this tool when the user asks about:
    - revenue
    - profit
    - gross profit
    - cost of goods sold
    - gross margin
    - profitability for a recent period
    """

    days = max(1, min(days, 365))

    date_to = date.today()
    date_from = date_to - timedelta(days=days)

    db = SessionLocal()

    try:
        result = profit(
            db,
            date_from=date_from,
            date_to=date_to,
            category_id=category_id,
        )

        return {
            "date_from": str(result["date_from"]),
            "date_to": str(result["date_to"]),
            "revenue": str(result["revenue"]),
            "cost_of_goods_sold": str(result["cost_of_goods_sold"]),
            "gross_profit": str(result["gross_profit"]),
            "gross_margin_percent": str(result["gross_margin_percent"]),
        }

    finally:
        db.close()



@tool
def get_receivables_aging() -> dict:
    """
    Get current receivables aging for the Mini ERP.

    Use this tool when the user asks about:
    - overdue customer balances
    - receivables
    - unpaid invoices
    - aging buckets
    - customers with outstanding balances
    """

    db = SessionLocal()

    try:
        result = receivables_aging(
            db,
            as_of=date.today(),
        )

        return {
            "as_of": str(result["as_of"]),
            "total_outstanding": str(result["total_outstanding"]),
            "items": [
                {
                    "customer_id": row["customer_id"],
                    "customer_name": row["customer_name"],
                    "days_0_30": str(row["days_0_30"]),
                    "days_31_60": str(row["days_31_60"]),
                    "days_61_90": str(row["days_61_90"]),
                    "over_90": str(row["over_90"]),
                    "total": str(row["total"]),
                }
                for row in result["items"]
            ],
        }

    finally:
        db.close()