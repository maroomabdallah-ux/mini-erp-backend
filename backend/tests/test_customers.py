from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.features.audit.model import AuditLog
from app.features.customers.models import Customer
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_customers():
    yield
    with SessionLocal() as db:
        ids = list(
            db.scalars(select(Customer.id).where(Customer.name.like("Test Customer %"))).all()
        )
        if ids:
            db.execute(
                delete(AuditLog).where(
                    AuditLog.table_name == "customers",
                    AuditLog.record_id.in_([str(item) for item in ids]),
                )
            )
        db.execute(delete(Customer).where(Customer.name.like("Test Customer %")))
        db.commit()


def headers(login: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"login": login, "password": "Passw0rd!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def payload(suffix: str) -> dict:
    return {
        "name": f"Test Customer {suffix}",
        "contact_person": "Rana Khalil",
        "email": f"CUSTOMER-{suffix}@Example.COM",
        "phone": "+962 79 555 0100",
        "address": "King Abdullah II Street",
        "city": "Amman",
        "tax_number": f"TAX-{suffix}",
        "credit_limit": "2500.00",
    }


def test_customer_crud_filters_and_audit() -> None:
    suffix = uuid4().hex[:8]
    sales = headers("sales")
    created = client.post("/customers", headers=sales, json=payload(suffix))
    assert created.status_code == 201
    customer = created.json()
    assert customer["code"].startswith("CUS-")
    assert customer["email"] == f"customer-{suffix}@example.com"

    listed = client.get(f"/customers?search={suffix}&city=Amman&is_active=true", headers=sales)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert "Amman" in client.get("/customers/cities", headers=sales).json()

    updated = client.put(
        f"/customers/{customer['id']}",
        headers=sales,
        json={"credit_limit": "3000.00", "phone": None},
    )
    assert updated.status_code == 200
    assert updated.json()["credit_limit"] == "3000.00"
    assert updated.json()["phone"] is None

    deactivated = client.delete(f"/customers/{customer['id']}", headers=sales)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert client.delete(f"/customers/{customer['id']}", headers=sales).status_code == 422

    with SessionLocal() as db:
        actions = list(
            db.scalars(
                select(AuditLog.action).where(
                    AuditLog.table_name == "customers", AuditLog.record_id == str(customer["id"])
                )
            ).all()
        )
    assert actions == ["create", "update", "deactivate"]


def test_customer_rbac_and_validation() -> None:
    suffix = uuid4().hex[:8]
    manager = headers("manager")
    purchasing = headers("purchasing")
    sales = headers("sales")

    assert client.get("/customers", headers=manager).status_code == 200
    assert client.post("/customers", headers=manager, json=payload(suffix)).status_code == 403
    assert client.get("/customers", headers=purchasing).status_code == 403

    invalid = payload(suffix)
    invalid["credit_limit"] = "-1"
    assert client.post("/customers", headers=sales, json=invalid).status_code == 422
    assert client.get("/customers/999999", headers=sales).status_code == 404
