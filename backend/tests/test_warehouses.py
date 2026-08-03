from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.features.users.model import User
from app.features.warehouses.models import Warehouse
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_warehouses():
    yield
    with SessionLocal() as db:
        db.execute(delete(Warehouse).where(Warehouse.code.like("TWH-%")))
        db.execute(delete(User).where(User.username.like("warehouse_reader_%")))
        db.commit()


def admin_headers() -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"login": "admin", "password": "Passw0rd!"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def warehouse_payload(suffix: str) -> dict[str, str]:
    return {
        "code": f"TWH-{suffix}",
        "name": f"Test Warehouse {suffix}",
        "address": "Industrial Area, Amman",
    }


def test_warehouse_crud_search_and_deactivation() -> None:
    suffix = uuid4().hex[:8]
    payload = warehouse_payload(suffix)

    created = client.post("/warehouses", headers=admin_headers(), json=payload)
    assert created.status_code == 201
    warehouse = created.json()
    assert warehouse["code"] == payload["code"].upper()
    assert warehouse["is_active"] is True

    fetched = client.get(
        f"/warehouses/{warehouse['id']}", headers=admin_headers()
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == warehouse["id"]

    listed = client.get(
        f"/warehouses?page=1&size=5&search={suffix}&is_active=true",
        headers=admin_headers(),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    updated = client.put(
        f"/warehouses/{warehouse['id']}",
        headers=admin_headers(),
        json={"name": f"Updated Warehouse {suffix}", "address": None},
    )
    assert updated.status_code == 200
    assert updated.json()["name"].startswith("Updated")
    assert updated.json()["address"] is None

    deactivated = client.delete(
        f"/warehouses/{warehouse['id']}", headers=admin_headers()
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    repeated = client.delete(
        f"/warehouses/{warehouse['id']}", headers=admin_headers()
    )
    assert repeated.status_code == 422


def test_duplicate_code_and_invalid_input_are_rejected() -> None:
    suffix = uuid4().hex[:8]
    payload = warehouse_payload(suffix)
    assert client.post(
        "/warehouses", headers=admin_headers(), json=payload
    ).status_code == 201

    duplicate = {**warehouse_payload(f"OTHER-{suffix}"), "code": payload["code"].lower()}
    response = client.post("/warehouses", headers=admin_headers(), json=duplicate)
    assert response.status_code == 409

    invalid = client.post(
        "/warehouses",
        headers=admin_headers(),
        json={"code": " ", "name": "A", "address": ""},
    )
    assert invalid.status_code == 422


def test_warehouse_permissions_separate_read_from_manage() -> None:
    roles = client.get("/roles", headers=admin_headers()).json()
    purchasing_role = next(role for role in roles if role["name"] == "purchasing_officer")
    suffix = uuid4().hex[:8]
    username = f"warehouse_reader_{suffix}"
    created = client.post(
        "/users",
        headers=admin_headers(),
        json={
            "username": username,
            "first_name": "Warehouse",
            "last_name": "Reader",
            "email": f"{username}@example.com",
            "password": "Passw0rd!",
            "role_ids": [purchasing_role["id"]],
        },
    )
    assert created.status_code == 201
    login = client.post(
        "/auth/login", json={"login": username, "password": "Passw0rd!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/warehouses", headers=headers).status_code == 200
    assert client.post(
        "/warehouses", headers=headers, json=warehouse_payload(suffix)
    ).status_code == 403
