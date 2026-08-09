from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.features.audit.model import AuditLog
from app.features.suppliers.models import Supplier
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_suppliers():
    yield
    with SessionLocal() as db:
        supplier_ids = list(
            db.scalars(select(Supplier.id).where(Supplier.name.like("Test Supplier %"))).all()
        )
        if supplier_ids:
            db.execute(
                delete(AuditLog).where(
                    AuditLog.table_name == "suppliers",
                    AuditLog.record_id.in_([str(item) for item in supplier_ids]),
                )
            )
        db.execute(delete(Supplier).where(Supplier.name.like("Test Supplier %")))
        db.commit()


def login_headers(login: str, password: str = "Passw0rd!") -> dict[str, str]:
    response = client.post("/auth/login", json={"login": login, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def supplier_payload(suffix: str) -> dict:
    return {
        "name": f"Test Supplier {suffix}",
        "email": f"SUPPLIER-{suffix}@Example.COM",
        "phone": "+962 6 555 0100",
        "credit_terms": "Net 30",
    }


def test_supplier_crud_search_filter_and_audit() -> None:
    suffix = uuid4().hex[:8]
    headers = login_headers("admin")
    payload = supplier_payload(suffix)

    created = client.post("/suppliers", headers=headers, json=payload)
    assert created.status_code == 201
    supplier = created.json()
    assert supplier["email"] == payload["email"].lower()
    assert supplier["is_active"] is True

    fetched = client.get(f"/suppliers/{supplier['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == supplier["id"]

    listed = client.get(
        f"/suppliers?page=1&size=5&search={suffix}&is_active=true",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    updated = client.put(
        f"/suppliers/{supplier['id']}",
        headers=headers,
        json={"phone": None, "credit_terms": "Net 45"},
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] is None
    assert updated.json()["credit_terms"] == "Net 45"

    deactivated = client.delete(f"/suppliers/{supplier['id']}", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert client.delete(f"/suppliers/{supplier['id']}", headers=headers).status_code == 422

    with SessionLocal() as db:
        actions = list(
            db.scalars(
                select(AuditLog.action).where(
                    AuditLog.table_name == "suppliers",
                    AuditLog.record_id == str(supplier["id"]),
                )
            ).all()
        )
    assert actions == ["create", "update", "deactivate"]


def test_supplier_validation_and_not_found() -> None:
    headers = login_headers("admin")
    invalid = supplier_payload(uuid4().hex[:8])
    invalid["email"] = "not-an-email"
    assert client.post("/suppliers", headers=headers, json=invalid).status_code == 422
    assert client.get("/suppliers/999999", headers=headers).status_code == 404


def test_purchasing_can_manage_suppliers_and_sales_cannot_access() -> None:
    suffix = uuid4().hex[:8]
    purchasing_headers = login_headers("purchasing")
    sales_headers = login_headers("sales")

    created = client.post("/suppliers", headers=purchasing_headers, json=supplier_payload(suffix))
    assert created.status_code == 201
    assert client.get("/suppliers", headers=purchasing_headers).status_code == 200

    assert client.get("/suppliers", headers=sales_headers).status_code == 403
    assert (
        client.post(
            "/suppliers", headers=sales_headers, json=supplier_payload(f"S-{suffix}")
        ).status_code
        == 403
    )
