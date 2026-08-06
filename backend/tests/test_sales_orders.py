from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, or_, select

from app.db.session import SessionLocal
from app.features.audit.model import AuditLog
from app.features.customers.models import Customer
from app.features.inventory.models import StockLevel, StockMovement
from app.features.quotations.models import Quotation, QuotationItem
from app.features.sales.models import SalesDelivery, SalesDeliveryItem, SalesOrder, SalesOrderItem
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    with SessionLocal() as db:
        quote_ids = list(
            db.scalars(select(Quotation.id).where(Quotation.notes.like("Test sales flow %"))).all()
        )
        customer_ids = list(
            db.scalars(select(Customer.id).where(Customer.name.like("Test Sales Customer %"))).all()
        )
        order_ids = list(
            db.scalars(
                select(SalesOrder.id).where(
                    or_(
                        SalesOrder.quotation_id.in_(quote_ids),
                        SalesOrder.notes.like("Test direct sales %"),
                    )
                )
            ).all()
        )
        delivery_ids = (
            list(
                db.scalars(
                    select(SalesDelivery.id).where(SalesDelivery.sales_order_id.in_(order_ids))
                ).all()
            )
            if order_ids
            else []
        )
        test_movements = list(
            db.scalars(
                select(StockMovement).where(StockMovement.reason.like("Test sales stock %"))
            ).all()
        )
        delivery_references = (
            list(
                db.scalars(
                    select(SalesDelivery.number).where(SalesDelivery.id.in_(delivery_ids))
                ).all()
            )
            if delivery_ids
            else []
        )
        delivery_movements = (
            list(
                db.scalars(
                    select(StockMovement).where(
                        StockMovement.reference_type == "sales_delivery",
                        StockMovement.reference_id.in_(delivery_references),
                    )
                ).all()
            )
            if delivery_references
            else []
        )
        for movement in [*test_movements, *delivery_movements]:
            stock = db.scalar(
                select(StockLevel).where(
                    StockLevel.product_id == movement.product_id,
                    StockLevel.warehouse_id == movement.warehouse_id,
                )
            )
            if stock is not None:
                stock.quantity -= movement.quantity
        if test_movements:
            db.execute(
                delete(StockMovement).where(
                    StockMovement.id.in_([movement.id for movement in test_movements])
                )
            )
        if delivery_ids:
            db.execute(
                delete(StockMovement).where(
                    StockMovement.reference_type == "sales_delivery",
                    StockMovement.reference_id.in_(delivery_references),
                )
            )
            db.execute(
                delete(SalesDeliveryItem).where(
                    SalesDeliveryItem.sales_delivery_id.in_(delivery_ids)
                )
            )
            db.execute(delete(SalesDelivery).where(SalesDelivery.id.in_(delivery_ids)))
        if order_ids:
            db.execute(
                delete(AuditLog).where(
                    AuditLog.table_name == "sales_orders",
                    AuditLog.record_id.in_([str(item) for item in order_ids]),
                )
            )
            db.execute(delete(SalesOrderItem).where(SalesOrderItem.sales_order_id.in_(order_ids)))
            db.execute(delete(SalesOrder).where(SalesOrder.id.in_(order_ids)))
        if quote_ids:
            db.execute(
                delete(AuditLog).where(
                    AuditLog.table_name == "quotations",
                    AuditLog.record_id.in_([str(item) for item in quote_ids]),
                )
            )
            db.execute(delete(QuotationItem).where(QuotationItem.quotation_id.in_(quote_ids)))
            db.execute(delete(Quotation).where(Quotation.id.in_(quote_ids)))
        if customer_ids:
            db.execute(
                delete(AuditLog).where(
                    AuditLog.table_name == "customers",
                    AuditLog.record_id.in_([str(item) for item in customer_ids]),
                )
            )
            db.execute(delete(Customer).where(Customer.id.in_(customer_ids)))
        db.commit()


def headers(login: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"login": login, "password": "Passw0rd!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def accepted_quote(sales: dict[str, str], suffix: str) -> tuple[dict, list[dict]]:
    customer = client.post(
        "/customers",
        headers=sales,
        json={
            "name": f"Test Sales Customer {suffix}",
            "email": f"sales-{suffix}@example.com",
            "credit_limit": "5000.00",
        },
    ).json()
    products = client.get("/products?size=2&is_active=true", headers=sales).json()["items"]
    created = client.post(
        "/quotations",
        headers=sales,
        json={
            "customer_id": customer["id"],
            "valid_until": str(date.today() + timedelta(days=10)),
            "notes": f"Test sales flow {suffix}",
            "discount_percent": "0",
            "tax_percent": "0",
            "items": [
                {"product_id": product["id"], "quantity": 2, "unit_price": product["sale_price"]}
                for product in products
            ],
        },
    ).json()
    client.post(f"/quotations/{created['id']}/send", headers=sales)
    accepted = client.post(f"/quotations/{created['id']}/accept", headers=sales)
    assert accepted.status_code == 200
    return accepted.json(), products


def test_convert_confirm_and_deliver_deducts_inventory() -> None:
    suffix = uuid4().hex[:8]
    sales = headers("sales")
    warehouse_user = headers("warehouse")
    admin = headers("admin")
    quote, products = accepted_quote(sales, suffix)
    warehouse = client.get("/warehouses?size=1&is_active=true", headers=warehouse_user).json()[
        "items"
    ][0]
    for product in products:
        response = client.post(
            "/inventory/adjustments",
            headers=admin,
            json={
                "product_id": product["id"],
                "warehouse_id": warehouse["id"],
                "quantity_change": 10,
                "reason": f"Test sales stock {suffix}",
            },
        )
        assert response.status_code == 200
    converted = client.post(f"/quotations/{quote['id']}/convert", headers=sales)
    assert converted.status_code == 201
    order = converted.json()
    assert order["status"] == "draft"
    assert order["total_amount"] == quote["total_amount"]
    assert client.post(f"/quotations/{quote['id']}/convert", headers=sales).status_code == 409
    confirmed = client.post(
        f"/sales-orders/{order['id']}/confirm",
        headers=sales,
        json={"warehouse_id": warehouse["id"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["warehouse_id"] == warehouse["id"]
    availability = client.get(f"/sales-orders/{order['id']}/availability", headers=warehouse_user)
    assert availability.status_code == 200
    selected = next(
        item for item in availability.json() if item["warehouse"]["id"] == warehouse["id"]
    )
    assert selected["ready"] is True
    delivered = client.post(
        f"/sales-orders/{order['id']}/deliver",
        headers=warehouse_user,
        json={"notes": "Customer delivery verified"},
    )
    assert delivered.status_code == 201
    assert delivered.json()["status"] == "delivered"
    assert delivered.json()["delivery"]["number"].startswith("SDN-")
    for product in products:
        stock = client.get(
            f"/inventory/stock?product_id={product['id']}&warehouse_id={warehouse['id']}",
            headers=warehouse_user,
        ).json()["items"][0]
        assert stock["quantity"] >= 0
    assert (
        client.post(
            f"/sales-orders/{order['id']}/deliver",
            headers=warehouse_user,
            json={},
        ).status_code
        == 422
    )


def test_sales_order_rbac_and_cancellation() -> None:
    suffix = uuid4().hex[:8]
    sales = headers("sales")
    manager = headers("manager")
    purchasing = headers("purchasing")
    warehouse_user = headers("warehouse")
    quote, _ = accepted_quote(sales, suffix)
    order = client.post(f"/quotations/{quote['id']}/convert", headers=sales).json()
    assert client.get("/sales-orders", headers=manager).status_code == 200
    assert client.get("/sales-orders", headers=purchasing).status_code == 403
    assert (
        client.post(
            f"/sales-orders/{order['id']}/confirm",
            headers=warehouse_user,
            json={"warehouse_id": 1},
        ).status_code
        == 403
    )
    cancelled = client.post(
        f"/sales-orders/{order['id']}/cancel",
        headers=sales,
        json={"reason": "Customer changed the requested delivery"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_create_direct_sales_order() -> None:
    suffix = uuid4().hex[:8]
    sales = headers("sales")
    customer = client.post(
        "/customers",
        headers=sales,
        json={
            "name": f"Test Sales Customer {suffix}",
            "email": f"direct-{suffix}@example.com",
            "credit_limit": "5000.00",
        },
    ).json()
    product = client.get("/products?size=1&is_active=true", headers=sales).json()["items"][0]
    response = client.post(
        "/sales-orders",
        headers=sales,
        json={
            "customer_id": customer["id"],
            "notes": f"Test direct sales {suffix}",
            "tax_percent": "16",
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": 2,
                    "unit_price": "100",
                    "discount_percent": "10",
                }
            ],
        },
    )
    assert response.status_code == 201
    assert response.json()["quotation_id"] is None
    assert response.json()["discount_amount"] == "20.00"
    assert response.json()["total_amount"] == "208.80"
