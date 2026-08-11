from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.features.billing.models import Invoice, InvoiceItem
from app.features.inventory import repository as inventory_repository
from app.features.inventory.models import StockLevel, StockMovement
from app.features.purchases.models import PurchaseOrder
from app.features.quotations.models import Quotation

CENT = Decimal("0.01")


def _invoices(db: Session, date_from: date, date_to: date) -> list[Invoice]:
    return list(
        db.scalars(
            select(Invoice)
            .options(
                selectinload(Invoice.items).selectinload(InvoiceItem.product),
                selectinload(Invoice.customer),
            )
            .where(
                Invoice.issue_date >= date_from,
                Invoice.issue_date <= date_to,
                Invoice.status != "draft",
            )
        ).all()
    )


def profit(db: Session, date_from: date, date_to: date, category_id: int | None = None) -> dict:
    revenue = Decimal("0")
    cogs = Decimal("0")
    for invoice in _invoices(db, date_from, date_to):
        sign = Decimal("-1") if invoice.document_type == "credit_note" else Decimal("1")
        selected = [
            item
            for item in invoice.items
            if category_id is None or item.product.category_id == category_id
        ]
        item_total = sum((item.line_total for item in invoice.items), Decimal("0"))
        selected_total = sum((item.line_total for item in selected), Decimal("0"))
        net_invoice_sales = invoice.total_amount - invoice.tax_amount
        selected_sales = (
            net_invoice_sales * selected_total / item_total if item_total else Decimal("0")
        )
        revenue += sign * selected_sales
        cogs += sign * sum(
            (Decimal(item.quantity) * item.product.cost_price for item in selected),
            Decimal("0"),
        )
    gross = revenue - cogs
    margin = (gross / revenue * 100) if revenue else Decimal("0")
    return {
        "date_from": date_from,
        "date_to": date_to,
        "revenue": revenue,
        "cost_of_goods_sold": cogs,
        "gross_profit": gross,
        "gross_margin_percent": margin.quantize(CENT, rounding=ROUND_HALF_UP),
    }


def top_products(
    db: Session, date_from: date, date_to: date, limit: int, sort_by: str
) -> list[dict]:
    totals: dict[int, dict] = {}
    for invoice in _invoices(db, date_from, date_to):
        sign = -1 if invoice.document_type == "credit_note" else 1
        item_total = sum((item.line_total for item in invoice.items), Decimal("0"))
        net_invoice_sales = invoice.total_amount - invoice.tax_amount
        for item in invoice.items:
            row = totals.setdefault(
                item.product_id,
                {
                    "product_id": item.product_id,
                    "sku": item.product.sku,
                    "product_name": item.product.name,
                    "quantity_sold": 0,
                    "net_sales": Decimal("0"),
                },
            )
            row["quantity_sold"] += sign * item.quantity
            item_net_sales = (
                net_invoice_sales * item.line_total / item_total
                if item_total
                else Decimal("0")
            )
            row["net_sales"] += sign * item_net_sales
    key = "quantity_sold" if sort_by == "quantity" else "net_sales"
    return sorted(totals.values(), key=lambda row: row[key], reverse=True)[:limit]


def inventory_valuation(db: Session) -> dict:
    levels = db.scalars(
        select(StockLevel)
        .options(selectinload(StockLevel.product), selectinload(StockLevel.warehouse))
        .order_by(StockLevel.warehouse_id, StockLevel.product_id)
    ).all()
    items = []
    for level in levels:
        items.append(
            {
                "warehouse_id": level.warehouse_id,
                "warehouse_name": level.warehouse.name,
                "product_id": level.product_id,
                "sku": level.product.sku,
                "product_name": level.product.name,
                "quantity": level.quantity,
                "unit_cost": level.product.cost_price,
                "inventory_value": Decimal(level.quantity) * level.product.cost_price,
            },
        )
    items.sort(key=lambda row: row["inventory_value"], reverse=True)
    return {
        "total_quantity": sum(row["quantity"] for row in items),
        "total_value": sum((row["inventory_value"] for row in items), Decimal("0")),
        "items": items,
    }


def receivables_aging(db: Session, as_of: date) -> dict:
    invoices = db.scalars(
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .where(
            Invoice.document_type == "invoice",
            Invoice.status.in_(["issued", "partially_paid"]),
            Invoice.issue_date <= as_of,
        )
    ).all()
    customers: dict[int, dict] = {}
    for invoice in invoices:
        balance = invoice.total_amount - invoice.paid_amount
        if balance <= 0:
            continue
        days = (as_of - invoice.due_date).days
        bucket = (
            "days_0_30"
            if days <= 30
            else "days_31_60"
            if days <= 60
            else "days_61_90"
            if days <= 90
            else "over_90"
        )
        row = customers.setdefault(
            invoice.customer_id,
            {
                "customer_id": invoice.customer_id,
                "customer_name": invoice.customer.name,
                "days_0_30": Decimal("0"),
                "days_31_60": Decimal("0"),
                "days_61_90": Decimal("0"),
                "over_90": Decimal("0"),
                "total": Decimal("0"),
            },
        )
        row[bucket] += balance
        row["total"] += balance
    items = sorted(customers.values(), key=lambda row: row["total"], reverse=True)
    return {
        "as_of": as_of,
        "total_outstanding": sum((row["total"] for row in items), Decimal("0")),
        "items": items,
    }


class _MonthlyTotal(TypedDict):
    invoice_count: int
    net_sales: Decimal


def monthly_sales(db: Session, months: int) -> list[dict]:
    today = date.today()
    first = (today.replace(day=1) - timedelta(days=months * 31)).replace(day=1)
    invoices = _invoices(db, first, today)
    totals: defaultdict[str, _MonthlyTotal] = defaultdict(
        lambda: {"invoice_count": 0, "net_sales": Decimal("0")}
    )
    for invoice in invoices:
        key = invoice.issue_date.strftime("%Y-%m")
        totals[key]["invoice_count"] += 1
        net_sales = invoice.total_amount - invoice.tax_amount
        amount = -net_sales if invoice.document_type == "credit_note" else net_sales
        totals[key]["net_sales"] += amount
    keys = []
    cursor = today.replace(day=1)
    for _ in range(months):
        keys.append(cursor.strftime("%Y-%m"))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return [{"month": key, **totals[key]} for key in reversed(keys)]


def stock_movements(
    db: Session,
    product_id: int,
    warehouse_id: int | None,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    statement = (
        select(StockMovement)
        .options(selectinload(StockMovement.product), selectinload(StockMovement.warehouse))
        .where(StockMovement.product_id == product_id)
        .order_by(StockMovement.created_at, StockMovement.id)
    )
    if warehouse_id:
        statement = statement.where(StockMovement.warehouse_id == warehouse_id)
    movements = list(db.scalars(statement).all())
    balance = 0
    rows = []
    for movement in movements:
        balance += movement.quantity
        occurred = movement.created_at.date()
        if date_from and occurred < date_from:
            continue
        if date_to and occurred > date_to:
            continue
        rows.append(
            {
                "id": movement.id,
                "occurred_at": movement.created_at,
                "product_id": movement.product_id,
                "sku": movement.product.sku,
                "product_name": movement.product.name,
                "warehouse_id": movement.warehouse_id,
                "warehouse_name": movement.warehouse.name,
                "reference": (
                    f"{movement.reference_type or 'manual'} {movement.reference_id or movement.id}"
                ),
                "movement_type": movement.type,
                "quantity_in": max(movement.quantity, 0),
                "quantity_out": abs(min(movement.quantity, 0)),
                "running_balance": balance,
            }
        )
    return rows


def dashboard(db: Session) -> dict:
    today = date.today()
    start = today.replace(day=1)
    earnings = profit(db, start, today)
    valuation = inventory_valuation(db)
    aging = receivables_aging(db, today)
    overdue = db.scalars(
        select(Invoice).where(
            Invoice.document_type == "invoice",
            Invoice.status.in_(["issued", "partially_paid"]),
            Invoice.due_date < today,
        )
    ).all()
    low_stock_ids = {row["product_id"] for row in inventory_repository.list_low_stock(db)}
    pending = len(
        db.scalars(select(PurchaseOrder.id).where(PurchaseOrder.status == "pending_approval")).all()
    )
    expiring = len(
        db.scalars(
            select(Quotation.id).where(
                Quotation.status == "sent",
                Quotation.valid_until >= today,
                Quotation.valid_until <= today + timedelta(days=7),
            )
        ).all()
    )
    return {
        "sales_this_month": earnings["revenue"],
        "profit_this_month": earnings["gross_profit"],
        "receivables": aging["total_outstanding"],
        "inventory_value": valuation["total_value"],
        "overdue_invoices": len(overdue),
        "low_stock_products": len(low_stock_ids),
        "pending_purchase_approvals": pending,
        "quotations_expiring_soon": expiring,
    }
