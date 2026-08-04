from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, or_, select

from app.db.session import SessionLocal
from app.features.inventory.models import InventoryCount, StockLevel, StockMovement
from app.features.products.models import Product
from app.features.users.model import User
from app.features.warehouses.models import Warehouse
from app.main import app

client = TestClient(app)


def remove_inventory_test_data() -> None:
    with SessionLocal() as db:
        product_ids = select(Product.id).where(Product.sku.like("TINV-%"))
        warehouse_ids = select(Warehouse.id).where(Warehouse.code.like("TINV-%"))
        db.execute(
            delete(InventoryCount).where(
                or_(
                    InventoryCount.product_id.in_(product_ids),
                    InventoryCount.warehouse_id.in_(warehouse_ids),
                )
            )
        )
        db.execute(
            delete(StockMovement).where(
                or_(
                    StockMovement.product_id.in_(product_ids),
                    StockMovement.warehouse_id.in_(warehouse_ids),
                )
            )
        )
        db.execute(
            delete(StockLevel).where(
                or_(
                    StockLevel.product_id.in_(product_ids),
                    StockLevel.warehouse_id.in_(warehouse_ids),
                )
            )
        )
        db.execute(delete(Product).where(Product.sku.like("TINV-%")))
        db.execute(delete(Warehouse).where(Warehouse.code.like("TINV-%")))
        db.execute(delete(User).where(User.username.like("inventory_reader_%")))
        db.commit()


@pytest.fixture(autouse=True)
def clean_inventory_test_data():
    remove_inventory_test_data()
    yield
    remove_inventory_test_data()


def admin_headers() -> dict[str, str]:
    response = client.post("/auth/login", json={"login": "admin", "password": "Passw0rd!"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_inventory_entities(suffix: str, min_stock: int = 5) -> tuple[dict, dict]:
    warehouse = client.post(
        "/warehouses",
        headers=admin_headers(),
        json={
            "code": f"TINV-WH-{suffix}",
            "name": f"Inventory Warehouse {suffix}",
            "address": "Test location",
        },
    )
    assert warehouse.status_code == 201
    product = client.post(
        "/products",
        headers=admin_headers(),
        json={
            "sku": f"TINV-PROD-{suffix}",
            "name": f"Inventory Product {suffix}",
            "cost_price": "10.00",
            "sale_price": "15.00",
            "min_stock_level": min_stock,
        },
    )
    assert product.status_code == 201
    return product.json(), warehouse.json()


def adjust(product_id: int, warehouse_id: int, change: str, reason: str = "Cycle count"):
    return client.post(
        "/inventory/adjustments",
        headers=admin_headers(),
        json={
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "quantity_change": change,
            "reason": reason,
        },
    )


def test_adjustment_updates_stock_and_records_movement() -> None:
    suffix = uuid4().hex[:8]
    product, warehouse = create_inventory_entities(suffix)

    increased = adjust(product["id"], warehouse["id"], "12", "Opening count")
    assert increased.status_code == 200
    assert increased.json()["quantity"] == 12

    decreased = adjust(product["id"], warehouse["id"], "-4", "Damaged units")
    assert decreased.status_code == 200
    assert decreased.json()["quantity"] == 8

    movements = client.get(
        f"/inventory/movements?product_id={product['id']}&warehouse_id={warehouse['id']}",
        headers=admin_headers(),
    )
    assert movements.status_code == 200
    assert movements.json()["total"] == 2
    assert movements.json()["items"][0]["quantity"] == -4


def test_fractional_inventory_quantities_are_rejected() -> None:
    suffix = uuid4().hex[:8]
    product, warehouse = create_inventory_entities(suffix)

    rejected = adjust(product["id"], warehouse["id"], "0.09")

    assert rejected.status_code == 422


def test_negative_stock_is_rejected_without_changing_quantity() -> None:
    suffix = uuid4().hex[:8]
    product, warehouse = create_inventory_entities(suffix)
    assert adjust(product["id"], warehouse["id"], "3.00").status_code == 200

    rejected = adjust(product["id"], warehouse["id"], "-4.00")
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "CONFLICT"

    stock = client.get(
        f"/inventory/stock?product_id={product['id']}&warehouse_id={warehouse['id']}",
        headers=admin_headers(),
    )
    assert stock.status_code == 200
    assert stock.json()["items"][0]["quantity"] == 3
    assert stock.json()["total_quantity"] == 3


def test_low_stock_and_warehouse_deactivation_guard() -> None:
    suffix = uuid4().hex[:8]
    product, warehouse = create_inventory_entities(suffix, min_stock=10)
    assert adjust(product["id"], warehouse["id"], "2.00").status_code == 200

    low_stock = client.get("/inventory/low-stock", headers=admin_headers())
    assert low_stock.status_code == 200
    item = next(row for row in low_stock.json() if row["product_id"] == product["id"])
    assert item["total_quantity"] == 2
    assert item["shortage"] == 8

    blocked = client.delete(f"/warehouses/{warehouse['id']}", headers=admin_headers())
    assert blocked.status_code == 422
    assert "holding stock" in blocked.json()["detail"]


def test_inventory_read_permission_does_not_allow_adjustment() -> None:
    roles = client.get("/roles", headers=admin_headers()).json()
    sales_role = next(role for role in roles if role["name"] == "sales_officer")
    suffix = uuid4().hex[:8]
    username = f"inventory_reader_{suffix}"
    created = client.post(
        "/users",
        headers=admin_headers(),
        json={
            "username": username,
            "first_name": "Inventory",
            "last_name": "Reader",
            "email": f"{username}@example.com",
            "password": "Passw0rd!",
            "role_ids": [sales_role["id"]],
        },
    )
    assert created.status_code == 201
    login = client.post("/auth/login", json={"login": username, "password": "Passw0rd!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/inventory/stock", headers=headers).status_code == 200
    assert (
        client.post(
            "/inventory/adjustments",
            headers=headers,
            json={
                "product_id": 1,
                "warehouse_id": 1,
                "quantity_change": "1.00",
                "reason": "Not allowed",
            },
        ).status_code
        == 403
    )


def test_transfer_moves_stock_atomically_and_records_linked_movements() -> None:
    suffix = uuid4().hex[:8]
    product, source = create_inventory_entities(suffix)
    destination_response = client.post(
        "/warehouses",
        headers=admin_headers(),
        json={
            "code": f"TINV-DST-{suffix}",
            "name": f"Destination Warehouse {suffix}",
            "address": "Destination location",
        },
    )
    assert destination_response.status_code == 201
    destination = destination_response.json()
    assert adjust(product["id"], source["id"], "15.00").status_code == 200

    transferred = client.post(
        "/inventory/transfers",
        headers=admin_headers(),
        json={
            "product_id": product["id"],
            "source_warehouse_id": source["id"],
            "destination_warehouse_id": destination["id"],
            "quantity": "6.00",
            "reason": "Replenish secondary location",
        },
    )
    assert transferred.status_code == 201
    body = transferred.json()
    assert body["transfer_reference"].startswith("TRF-")
    assert body["source_quantity"] == 9
    assert body["destination_quantity"] == 6

    movements = client.get(
        f"/inventory/movements?product_id={product['id']}",
        headers=admin_headers(),
    ).json()["items"]
    linked = [
        movement for movement in movements if movement["reference_id"] == body["transfer_reference"]
    ]
    assert len(linked) == 2
    assert {movement["type"] for movement in linked} == {"in", "out"}
    assert {movement["quantity"] for movement in linked} == {6, -6}


def test_transfer_rejects_same_warehouse_and_insufficient_stock() -> None:
    suffix = uuid4().hex[:8]
    product, source = create_inventory_entities(suffix)
    _, destination = create_inventory_entities(f"DST-{suffix}")
    assert adjust(product["id"], source["id"], "2.00").status_code == 200
    payload = {
        "product_id": product["id"],
        "source_warehouse_id": source["id"],
        "destination_warehouse_id": destination["id"],
        "quantity": "3.00",
        "reason": "Transfer test",
    }

    insufficient = client.post("/inventory/transfers", headers=admin_headers(), json=payload)
    assert insufficient.status_code == 409
    assert "enough stock" in insufficient.json()["detail"]

    payload["destination_warehouse_id"] = source["id"]
    same_warehouse = client.post("/inventory/transfers", headers=admin_headers(), json=payload)
    assert same_warehouse.status_code == 422


def test_physical_count_requires_approval_before_adjusting_stock() -> None:
    suffix = uuid4().hex[:8]
    product, warehouse = create_inventory_entities(suffix)
    assert adjust(product["id"], warehouse["id"], "10.00").status_code == 200

    created = client.post(
        "/inventory/counts",
        headers=admin_headers(),
        json={
            "product_id": product["id"],
            "warehouse_id": warehouse["id"],
            "counted_quantity": "7.00",
            "notes": "Three damaged units found",
        },
    )
    assert created.status_code == 201
    count = created.json()
    assert count["status"] == "pending"
    assert count["expected_quantity"] == 10
    assert count["variance"] == -3

    before_approval = client.get(
        f"/inventory/stock?product_id={product['id']}&warehouse_id={warehouse['id']}",
        headers=admin_headers(),
    ).json()["items"][0]
    assert before_approval["quantity"] == 10

    same_user_approval = client.post(
        f"/inventory/counts/{count['id']}/approve", headers=admin_headers()
    )
    assert same_user_approval.status_code == 409
    assert "cannot approve" in same_user_approval.json()["detail"]

    roles = client.get("/roles", headers=admin_headers()).json()
    manager_role = next(role for role in roles if role["name"] == "manager")
    username = f"inventory_reader_manager_{suffix}"
    manager = client.post(
        "/users",
        headers=admin_headers(),
        json={
            "username": username,
            "first_name": "Count",
            "last_name": "Approver",
            "email": f"{username}@example.com",
            "password": "Passw0rd!",
            "role_ids": [manager_role["id"]],
        },
    )
    assert manager.status_code == 201
    login = client.post("/auth/login", json={"login": username, "password": "Passw0rd!"})
    manager_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    approved = client.post(f"/inventory/counts/{count['id']}/approve", headers=manager_headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    after_approval = client.get(
        f"/inventory/stock?product_id={product['id']}&warehouse_id={warehouse['id']}",
        headers=admin_headers(),
    ).json()["items"][0]
    assert after_approval["quantity"] == 7
    movements = client.get(
        f"/inventory/movements?product_id={product['id']}",
        headers=admin_headers(),
    ).json()["items"]
    assert any(
        movement["reference_type"] == "physical_count"
        and movement["reference_id"] == count["reference"]
        and movement["quantity"] == -3
        for movement in movements
    )


def test_count_approval_rejects_stock_changed_after_count() -> None:
    suffix = uuid4().hex[:8]
    product, warehouse = create_inventory_entities(suffix)
    assert adjust(product["id"], warehouse["id"], "5.00").status_code == 200
    count = client.post(
        "/inventory/counts",
        headers=admin_headers(),
        json={
            "product_id": product["id"],
            "warehouse_id": warehouse["id"],
            "counted_quantity": "4.00",
            "notes": "Physical count",
        },
    ).json()
    assert adjust(product["id"], warehouse["id"], "1.00").status_code == 200

    approval = client.post(f"/inventory/counts/{count['id']}/approve", headers=admin_headers())
    assert approval.status_code == 409
    assert "Stock changed" in approval.json()["detail"]
