from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, or_

from app.db.session import SessionLocal
from app.features.products.models import Category, Product
from app.features.users.model import User
from app.main import app

client = TestClient(app)


def remove_test_data() -> None:
    with SessionLocal() as db:
        db.execute(delete(Product).where(or_(Product.sku.like("SKU-%"), Product.sku.like("CSV-%"))))
        db.execute(delete(Category).where(Category.name.like("Child %")))
        db.execute(
            delete(Category).where(
                or_(
                    Category.name.like("Parent %"),
                    Category.name.like("Product Category %"),
                )
            )
        )
        db.execute(delete(User).where(User.username.like("buyer_%")))
        db.commit()


@pytest.fixture(autouse=True)
def clean_product_test_data():
    remove_test_data()
    yield
    remove_test_data()


def admin_headers() -> dict[str, str]:
    response = client.post("/auth/login", json={"login": "admin", "password": "Passw0rd!"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_category(name: str, parent_id: int | None = None) -> dict:
    response = client.post(
        "/categories",
        headers=admin_headers(),
        json={"name": name, "parent_id": parent_id},
    )
    assert response.status_code == 201
    return response.json()


def product_payload(suffix: str, category_id: int | None = None) -> dict:
    return {
        "sku": f"sku-{suffix}",
        "name": f"Test Product {suffix}",
        "barcode": f"barcode-{suffix}",
        "category_id": category_id,
        "cost_price": "12.50",
        "sale_price": "19.99",
        "min_stock_level": "5.00",
    }


def test_category_hierarchy_rejects_cycles() -> None:
    suffix = uuid4().hex[:8]
    parent = create_category(f"Parent {suffix}")
    child = create_category(f"Child {suffix}", parent["id"])

    response = client.put(
        f"/categories/{parent['id']}",
        headers=admin_headers(),
        json={"parent_id": child["id"]},
    )
    assert response.status_code == 422
    assert "parent or descendant" in response.json()["detail"]


def test_product_crud_search_and_deactivation() -> None:
    suffix = uuid4().hex[:8]
    category = create_category(f"Product Category {suffix}")
    payload = product_payload(suffix, category["id"])

    created = client.post("/products", headers=admin_headers(), json=payload)
    assert created.status_code == 201
    product = created.json()
    assert product["sku"] == payload["sku"].upper()
    assert product["category"]["id"] == category["id"]
    assert product["sale_price"] == "19.99"

    listed = client.get(
        f"/products?page=1&size=5&search={suffix}&category_id={category['id']}",
        headers=admin_headers(),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == product["id"]

    updated = client.put(
        f"/products/{product['id']}",
        headers=admin_headers(),
        json={"name": f"Updated Product {suffix}", "barcode": None},
    )
    assert updated.status_code == 200
    assert updated.json()["name"].startswith("Updated")
    assert updated.json()["barcode"] is None

    blocked_category = client.delete(f"/categories/{category['id']}", headers=admin_headers())
    assert blocked_category.status_code == 422

    deactivated = client.delete(f"/products/{product['id']}", headers=admin_headers())
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    category_deactivated = client.delete(f"/categories/{category['id']}", headers=admin_headers())
    assert category_deactivated.status_code == 200
    assert category_deactivated.json()["is_active"] is False


def test_duplicate_sku_barcode_and_negative_prices_are_rejected() -> None:
    suffix = uuid4().hex[:8]
    payload = product_payload(suffix)
    assert client.post("/products", headers=admin_headers(), json=payload).status_code == 201

    duplicate_sku = {**product_payload(f"other-{suffix}"), "sku": payload["sku"]}
    response = client.post("/products", headers=admin_headers(), json=duplicate_sku)
    assert response.status_code == 409

    duplicate_barcode = {
        **product_payload(f"barcode-other-{suffix}"),
        "barcode": payload["barcode"],
    }
    response = client.post("/products", headers=admin_headers(), json=duplicate_barcode)
    assert response.status_code == 409

    invalid = {**product_payload(f"negative-{suffix}"), "cost_price": "-1.00"}
    response = client.post("/products", headers=admin_headers(), json=invalid)
    assert response.status_code == 422


def test_products_permissions_separate_read_from_manage() -> None:
    suffix = uuid4().hex[:8]
    roles = client.get("/roles", headers=admin_headers()).json()
    read_only_role = next(role for role in roles if role["name"] == "sales_officer")
    username = f"buyer_{suffix}"
    created = client.post(
        "/users",
        headers=admin_headers(),
        json={
            "username": username,
            "first_name": "Purchase",
            "last_name": "Officer",
            "email": f"{username}@example.com",
            "password": "Passw0rd!",
            "role_ids": [read_only_role["id"]],
        },
    )
    assert created.status_code == 201
    login = client.post("/auth/login", json={"login": username, "password": "Passw0rd!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/products", headers=headers).status_code == 200
    assert (
        client.post(
            "/products", headers=headers, json=product_payload(f"forbidden-{suffix}")
        ).status_code
        == 403
    )


def test_csv_import_creates_valid_rows_and_reports_invalid_rows() -> None:
    suffix = uuid4().hex[:8]
    content = (
        "sku,name,barcode,cost_price,sale_price,min_stock_level\n"
        f"CSV-{suffix},Imported Product {suffix},CSV-BAR-{suffix},10.00,15.00,2.00\n"
        f"CSV-BAD-{suffix},Invalid Product {suffix},,-1.00,15.00,2.00\n"
    )
    response = client.post(
        "/products/import",
        headers=admin_headers(),
        files={"file": ("products.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created_count"] == 1
    assert body["error_count"] == 1
    assert body["errors"][0]["row"] == 3

    listed = client.get(f"/products?search=CSV-{suffix}", headers=admin_headers())
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
