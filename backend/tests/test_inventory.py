from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, or_, select

from app.db.session import SessionLocal
from app.features.inventory.models import StockLevel, StockMovement
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
    response = client.post(
        "/auth/login", json={"login": "admin", "password": "Passw0rd!"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_inventory_entities(suffix: str, min_stock: str = "5.00") -> tuple[dict, dict]:
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

    increased = adjust(product["id"], warehouse["id"], "12.00", "Opening count")
    assert increased.status_code == 200
    assert increased.json()["quantity"] == "12.00"

    decreased = adjust(product["id"], warehouse["id"], "-4.50", "Damaged units")
    assert decreased.status_code == 200
    assert decreased.json()["quantity"] == "7.50"

    movements = client.get(
        f"/inventory/movements?product_id={product['id']}&warehouse_id={warehouse['id']}",
        headers=admin_headers(),
    )
    assert movements.status_code == 200
    assert movements.json()["total"] == 2
    assert movements.json()["items"][0]["quantity"] == "-4.50"


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
    assert stock.json()["items"][0]["quantity"] == "3.00"
    assert stock.json()["total_quantity"] == "3.00"


def test_low_stock_and_warehouse_deactivation_guard() -> None:
    suffix = uuid4().hex[:8]
    product, warehouse = create_inventory_entities(suffix, min_stock="10.00")
    assert adjust(product["id"], warehouse["id"], "2.00").status_code == 200

    low_stock = client.get("/inventory/low-stock", headers=admin_headers())
    assert low_stock.status_code == 200
    item = next(row for row in low_stock.json() if row["product_id"] == product["id"])
    assert item["total_quantity"] == "2.00"
    assert item["shortage"] == "8.00"

    blocked = client.delete(
        f"/warehouses/{warehouse['id']}", headers=admin_headers()
    )
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
    login = client.post(
        "/auth/login", json={"login": username, "password": "Passw0rd!"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/inventory/stock", headers=headers).status_code == 200
    assert client.post(
        "/inventory/adjustments",
        headers=headers,
        json={
            "product_id": 1,
            "warehouse_id": 1,
            "quantity_change": "1.00",
            "reason": "Not allowed",
        },
    ).status_code == 403
