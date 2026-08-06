from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.features.audit.model import AuditLog
from app.features.customers.models import Customer
from app.features.quotations.models import Quotation, QuotationItem
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    with SessionLocal() as db:
        quote_ids = list(
            db.scalars(select(Quotation.id).where(Quotation.notes.like("Test quotation %"))).all()
        )
        customer_ids = list(
            db.scalars(select(Customer.id).where(Customer.name.like("Test Quote Customer %"))).all()
        )
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


def setup_entities(sales: dict[str, str], suffix: str) -> tuple[dict, list[dict]]:
    customer = client.post(
        "/customers",
        headers=sales,
        json={
            "name": f"Test Quote Customer {suffix}",
            "email": f"quote-{suffix}@example.com",
            "city": "Amman",
            "credit_limit": "5000",
        },
    )
    assert customer.status_code == 201
    products = client.get("/products?size=2&is_active=true", headers=sales)
    assert products.status_code == 200
    assert len(products.json()["items"]) == 2
    return customer.json(), products.json()["items"]


def quote_payload(customer: dict, products: list[dict], suffix: str) -> dict:
    return {
        "customer_id": customer["id"],
        "valid_until": str(date.today() + timedelta(days=14)),
        "notes": f"Test quotation {suffix}",
        "discount_percent": "0.00",
        "tax_percent": "16.00",
        "items": [
            {
                "product_id": products[0]["id"],
                "quantity": 2,
                "unit_price": "100.00",
                "discount_percent": "10.00",
            },
            {
                "product_id": products[1]["id"],
                "quantity": 1,
                "unit_price": "50.00",
                "discount_percent": "0.00",
            },
        ],
    }


def test_quotation_complete_lifecycle_and_totals() -> None:
    suffix = uuid4().hex[:8]
    sales = headers("sales")
    customer, products = setup_entities(sales, suffix)
    created = client.post(
        "/quotations", headers=sales, json=quote_payload(customer, products, suffix)
    )
    assert created.status_code == 201
    quote = created.json()
    assert quote["status"] == "draft"
    assert quote["subtotal"] == "250.00"
    assert quote["items"][0]["discount_percent"] == "10.00"
    assert quote["discount_amount"] == "20.00"
    assert quote["tax_amount"] == "36.80"
    assert quote["total_amount"] == "266.80"

    listed = client.get(f"/quotations?search={suffix}&status=draft", headers=sales)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    sent = client.post(f"/quotations/{quote['id']}/send", headers=sales)
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert (
        client.put(
            f"/quotations/{quote['id']}",
            headers=sales,
            json=quote_payload(customer, products, suffix),
        ).status_code
        == 422
    )
    accepted = client.post(f"/quotations/{quote['id']}/accept", headers=sales)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"


def test_quotation_rejection_validation_and_rbac() -> None:
    suffix = uuid4().hex[:8]
    sales = headers("sales")
    manager = headers("manager")
    purchasing = headers("purchasing")
    customer, products = setup_entities(sales, suffix)
    created = client.post(
        "/quotations", headers=sales, json=quote_payload(customer, products, suffix)
    ).json()
    assert client.post(f"/quotations/{created['id']}/send", headers=sales).status_code == 200
    rejected = client.post(
        f"/quotations/{created['id']}/reject",
        headers=sales,
        json={"reason": "Customer selected another offer"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["rejection_reason"] == "Customer selected another offer"
    assert client.get("/quotations", headers=manager).status_code == 200
    assert (
        client.post(
            "/quotations", headers=manager, json=quote_payload(customer, products, suffix)
        ).status_code
        == 403
    )
    assert client.get("/quotations", headers=purchasing).status_code == 403
