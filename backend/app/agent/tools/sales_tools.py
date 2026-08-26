from langchain.tools import tool

from app.db.session import SessionLocal
from app.features.billing.service import list_invoices
from app.features.quotations.service import get_quotation as get_quotation_service
from app.features.quotations.service import list_quotations
from app.features.sales.service import get_order as get_sales_order_service
from app.features.sales.service import list_orders


def _customer(customer) -> dict:
    return {"id": customer.id, "code": customer.code, "name": customer.name}


def _quotation_summary(quotation) -> dict:
    return {
        "id": quotation.id,
        "quotation_number": quotation.number,
        "customer": _customer(quotation.customer),
        "status": quotation.status,
        "valid_until": quotation.valid_until,
        "created_at": quotation.created_at,
        "total_amount": quotation.total_amount,
    }


def _quotation_detail(quotation) -> dict:
    result = _quotation_summary(quotation)
    result.update(
        {
            "notes": quotation.notes,
            "subtotal": quotation.subtotal,
            "discount_amount": quotation.discount_amount,
            "tax_amount": quotation.tax_amount,
            "items": [
                {
                    "id": item.id,
                    "product": {
                        "id": item.product.id,
                        "sku": item.product.sku,
                        "name": item.product.name,
                    },
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "discount_percent": item.discount_percent,
                    "line_total": item.line_total,
                }
                for item in quotation.items
            ],
        }
    )
    return result


def _sales_order_summary(order) -> dict:
    return {
        "id": order.id,
        "sales_order_number": order.number,
        "customer": _customer(order.customer),
        "status": order.status,
        "created_at": order.created_at,
        "total_amount": order.total_amount,
    }


def _sales_order_detail(order) -> dict:
    result = _sales_order_summary(order)
    result.update(
        {
            "quotation_id": order.quotation_id,
            "notes": order.notes,
            "subtotal": order.subtotal,
            "discount_amount": order.discount_amount,
            "tax_amount": order.tax_amount,
            "items": [
                {
                    "id": item.id,
                    "product": {
                        "id": item.product.id,
                        "sku": item.product.sku,
                        "name": item.product.name,
                    },
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "discount_percent": item.discount_percent,
                    "line_total": item.line_total,
                }
                for item in order.items
            ],
        }
    )
    return result


def _money(value) -> str:
    return f"{value:.2f}"


def _invoice_summary(invoice) -> dict:
    return {
        "id": invoice.id,
        "invoice_number": invoice.number,
        "customer": _customer(invoice.customer),
        "status": invoice.status,
        "issue_date": invoice.issue_date,
        "due_date": invoice.due_date,
        "total_amount": _money(invoice.total_amount),
        "paid_amount": _money(invoice.paid_amount),
        "balance": _money(invoice.total_amount - invoice.paid_amount),
    }


@tool
def get_quotations(
    search: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    limit: int = 20,
) -> list[dict]:
    """List quotations using the existing quotation search and filters."""
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        result = list_quotations(
            db,
            page=1,
            size=limit,
            search=search,
            status=status,
            customer_id=customer_id,
        )
        return [_quotation_summary(quotation) for quotation in result["items"]]
    finally:
        db.close()


@tool
def get_quotation(quotation_id: int) -> dict:
    """Get a quotation and its existing line-item details by ID."""
    db = SessionLocal()
    try:
        return _quotation_detail(get_quotation_service(db, quotation_id))
    finally:
        db.close()


@tool
def get_sales_orders(
    search: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    limit: int = 20,
) -> list[dict]:
    """List sales orders using the existing sales-order search and filters."""
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        result = list_orders(
            db,
            page=1,
            size=limit,
            search=search,
            status=status,
            customer_id=customer_id,
        )
        return [_sales_order_summary(order) for order in result["items"]]
    finally:
        db.close()


@tool
def get_sales_order(sales_order_id: int) -> dict:
    """Get a sales order and its existing line-item details by ID."""
    db = SessionLocal()
    try:
        return _sales_order_detail(get_sales_order_service(db, sales_order_id))
    finally:
        db.close()


@tool
def get_invoices(
    search: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    overdue: bool = False,
    limit: int = 20,
) -> list[dict]:
    """List invoices using the existing invoice search and filters."""
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        result = list_invoices(
            db,
            page=1,
            size=limit,
            search=search,
            status=status,
            customer_id=customer_id,
            overdue=overdue,
        )
        return [_invoice_summary(invoice) for invoice in result["items"]]
    finally:
        db.close()


@tool
def get_customer_sales(customer_id: int, limit: int = 20) -> dict:
    """Get existing sales orders and invoices for a specific customer."""
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        orders = list_orders(
            db,
            page=1,
            size=limit,
            search=None,
            status=None,
            customer_id=customer_id,
        )
        invoices = list_invoices(
            db,
            page=1,
            size=limit,
            search=None,
            status=None,
            customer_id=customer_id,
            overdue=False,
        )
        return {
            "customer_id": customer_id,
            "sales_orders": [_sales_order_summary(order) for order in orders["items"]],
            "invoices": [_invoice_summary(invoice) for invoice in invoices["items"]],
        }
    finally:
        db.close()
