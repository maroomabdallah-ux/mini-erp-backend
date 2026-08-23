from langchain.tools import tool

from app.db.session import SessionLocal
from app.features.customers.service import (
    get_customer as get_customer_service,
)
from app.features.customers.service import (
    list_customers,
)


@tool
def get_customer(customer_id: int) -> dict:
    """
    Get a customer by ID from the Mini ERP.

    Use this tool when the user asks for information
    about a specific customer and provides the customer ID.
    """

    db = SessionLocal()

    try:
        customer = get_customer_service(db, customer_id)

        return {
            "id": customer.id,
            "code": customer.code,
            "name": customer.name,
            "city": customer.city,
            "credit_limit": f"{customer.credit_limit:.2f}",
            "is_active": customer.is_active,
        }

    finally:
        db.close()


@tool
def search_customers(search: str, limit: int = 10) -> list[dict]:
    """
    Search active customers by name, code, or other
    supported customer search fields.

    Use this tool when the user knows the customer name
    or code but does not know the customer ID.
    """

    limit = max(1, min(limit, 20))

    db = SessionLocal()

    try:
        result = list_customers(
            db,
            page=1,
            size=limit,
            search=search,
            is_active=True,
            city=None,
        )

        return [
            {
                "id": customer.id,
                "code": customer.code,
                "name": customer.name,
                "city": customer.city,
                "credit_limit": f"{customer.credit_limit:.2f}",
            }
            for customer in result["items"]
        ]

    finally:
        db.close()