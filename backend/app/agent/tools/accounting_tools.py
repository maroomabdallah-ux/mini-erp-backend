from datetime import date

from langchain.tools import tool

from app.core.config import settings
from app.db.session import SessionLocal
from app.features.accounting.service import customer_statement, list_entries, supplier_statement
from app.features.billing.service import get_invoice as get_invoice_service
from app.features.reports.service import inventory_valuation


def _statement_result(statement: dict) -> dict:
    return {
        "entity_id": statement["entity_id"],
        "entity_name": statement["entity_name"],
        "date_from": statement["date_from"],
        "date_to": statement["date_to"],
        "opening_balance": str(statement["opening_balance"]),
        "closing_balance": str(statement["closing_balance"]),
        "lines": [
            {
                "date": line["date"],
                "reference": line["reference"],
                "description": line["description"],
                "debit": str(line["debit"]),
                "credit": str(line["credit"]),
                "balance": str(line["balance"]),
            }
            for line in statement["lines"][: settings.agent_max_tool_results]
        ],
    }


@tool
def get_customer_statement(customer_id: int, date_from: date, date_to: date) -> dict:
    """Get an existing customer statement for a date range."""
    db = SessionLocal()
    try:
        return _statement_result(customer_statement(db, customer_id, date_from, date_to))
    finally:
        db.close()


@tool
def get_supplier_statement(supplier_id: int, date_from: date, date_to: date) -> dict:
    """Get an existing supplier statement for a date range."""
    db = SessionLocal()
    try:
        return _statement_result(supplier_statement(db, supplier_id, date_from, date_to))
    finally:
        db.close()


@tool
def get_invoice_balance(invoice_id: int) -> dict:
    """Get the current balance of an invoice using the existing invoice service."""
    db = SessionLocal()
    try:
        invoice = get_invoice_service(db, invoice_id)
        return {
            "id": invoice.id,
            "invoice_number": invoice.number,
            "customer_id": invoice.customer_id,
            "status": invoice.status,
            "total_amount": str(invoice.total_amount),
            "paid_amount": str(invoice.paid_amount),
            "balance": str(invoice.total_amount - invoice.paid_amount),
            "due_date": invoice.due_date,
        }
    finally:
        db.close()


@tool
def get_journal_entries(
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: int | None = None,
    source_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """List bounded journal entries using existing accounting filters."""
    limit = max(1, min(limit, settings.agent_max_tool_results))
    db = SessionLocal()
    try:
        result = list_entries(
            db,
            page=1,
            size=limit,
            search=search,
            date_from=date_from,
            date_to=date_to,
            account_id=account_id,
            source_type=source_type,
        )
        return [
            {
                "id": entry["id"],
                "journal_number": entry["number"],
                "entry_date": entry["entry_date"],
                "description": entry["description"],
                "source_type": entry["source_type"],
                "source_reference": entry["source_reference"],
                "total_amount": str(entry["total_amount"]),
            }
            for entry in result["items"]
        ]
    finally:
        db.close()


@tool
def get_inventory_valuation(limit: int = 20) -> dict:
    """Get inventory valuation from the existing management report service."""
    limit = max(1, min(limit, settings.agent_max_tool_results))
    db = SessionLocal()
    try:
        result = inventory_valuation(db)
        return {
            "total_quantity": str(result["total_quantity"]),
            "total_value": str(result["total_value"]),
            "items": [
                {
                    **row,
                    "quantity": str(row["quantity"]),
                    "unit_cost": str(row["unit_cost"]),
                    "inventory_value": str(row["inventory_value"]),
                }
                for row in result["items"][:limit]
            ],
        }
    finally:
        db.close()
