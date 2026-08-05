from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, or_, select

from app.db.session import SessionLocal
from app.features.audit.model import AuditLog
from app.features.inventory.models import StockLevel, StockMovement
from app.features.products.models import Product
from app.features.purchases.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
)
from app.features.suppliers.models import Supplier
from app.features.warehouses.models import Warehouse
from app.main import app

client = TestClient(app)


def login_headers(login: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"login": login, "password": "Passw0rd!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def cleanup_purchase_data() -> None:
    with SessionLocal() as db:
        test_supplier_ids = select(Supplier.id).where(
            Supplier.name.like("Test PO Supplier %")
        )
        order_ids = select(PurchaseOrder.id).where(
            PurchaseOrder.supplier_id.in_(test_supplier_ids)
        )
        receipt_ids = select(GoodsReceipt.id).where(GoodsReceipt.purchase_order_id.in_(order_ids))
        product_ids = select(Product.id).where(Product.sku.like("TPO-%"))
        db.execute(
            delete(AuditLog).where(
                or_(
                    AuditLog.table_name == "purchase_orders",
                    AuditLog.table_name == "goods_receipts",
                ),
                AuditLog.record_id.in_([str(item) for item in db.scalars(order_ids).all()]),
            )
        )
        db.execute(delete(StockMovement).where(StockMovement.product_id.in_(product_ids)))
        db.execute(delete(StockLevel).where(StockLevel.product_id.in_(product_ids)))
        db.execute(delete(GoodsReceiptItem).where(GoodsReceiptItem.goods_receipt_id.in_(receipt_ids)))
        db.execute(delete(GoodsReceipt).where(GoodsReceipt.id.in_(receipt_ids)))
        db.execute(delete(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id.in_(order_ids)))
        db.execute(delete(PurchaseOrder).where(PurchaseOrder.id.in_(order_ids)))
        db.execute(delete(Product).where(Product.sku.like("TPO-%")))
        db.execute(delete(Warehouse).where(Warehouse.code.like("TPO-%")))
        db.execute(delete(Supplier).where(Supplier.name.like("Test PO Supplier %")))
        db.commit()


@pytest.fixture(autouse=True)
def clean_purchase_test_data():
    cleanup_purchase_data()
    yield
    cleanup_purchase_data()


def create_entities(suffix: str) -> tuple[dict, list[dict], dict]:
    admin = login_headers("admin")
    supplier_response = client.post(
        "/suppliers",
        headers=admin,
        json={
            "name": f"Test PO Supplier {suffix}",
            "email": f"po-{suffix}@example.com",
            "phone": "+962 6 555 0199",
            "credit_terms": "Net 30",
        },
    )
    assert supplier_response.status_code == 201
    products = []
    for index in range(2):
        response = client.post(
            "/products",
            headers=admin,
            json={
                "sku": f"TPO-{suffix}-{index}",
                "name": f"Test PO Product {suffix} {index}",
                "cost_price": "10.00",
                "sale_price": "15.00",
                "min_stock_level": 2,
            },
        )
        assert response.status_code == 201
        products.append(response.json())
    warehouse_response = client.post(
        "/warehouses",
        headers=admin,
        json={
            "code": f"TPO-WH-{suffix}",
            "name": f"Test PO Warehouse {suffix}",
            "address": "Amman",
        },
    )
    assert warehouse_response.status_code == 201
    return supplier_response.json(), products, warehouse_response.json()


def order_payload(supplier: dict, products: list[dict]) -> dict:
    return {
        "supplier_id": supplier["id"],
        "notes": "Monthly replenishment",
        "items": [
            {"product_id": products[0]["id"], "quantity": 2, "unit_cost": "10.00"},
            {"product_id": products[1]["id"], "quantity": 3, "unit_cost": "5.00"},
        ],
    }


def test_complete_purchase_order_workflow_updates_inventory() -> None:
    suffix = uuid4().hex[:8]
    supplier, products, warehouse = create_entities(suffix)
    purchasing = login_headers("purchasing")
    manager = login_headers("manager")
    keeper = login_headers("warehouse")

    created = client.post(
        "/purchase-orders",
        headers=purchasing,
        json=order_payload(supplier, products),
    )
    assert created.status_code == 201
    order = created.json()
    assert order["status"] == "draft"
    assert order["total_amount"] == "35.00"
    assert len(order["items"]) == 2

    listed = client.get(
        f"/purchase-orders?search={order['number']}&status=draft",
        headers=purchasing,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    submitted = client.post(
        f"/purchase-orders/{order['id']}/submit", headers=purchasing
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_approval"
    assert client.post(
        f"/purchase-orders/{order['id']}/approve", headers=purchasing
    ).status_code == 403

    approved = client.post(
        f"/purchase-orders/{order['id']}/approve", headers=manager
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert client.put(
        f"/purchase-orders/{order['id']}",
        headers=purchasing,
        json=order_payload(supplier, products),
    ).status_code == 422

    received = client.post(
        f"/purchase-orders/{order['id']}/receive",
        headers=keeper,
        json={"warehouse_id": warehouse["id"], "notes": "Delivery verified"},
    )
    assert received.status_code == 201
    received_order = received.json()
    assert received_order["status"] == "received"
    assert received_order["receipt"]["warehouse_id"] == warehouse["id"]
    assert received_order["receipt"]["number"].startswith("GRN-")

    repeated = client.post(
        f"/purchase-orders/{order['id']}/receive",
        headers=keeper,
        json={"warehouse_id": warehouse["id"]},
    )
    assert repeated.status_code == 422
    stock = client.get(
        f"/inventory/stock?warehouse_id={warehouse['id']}", headers=keeper
    )
    quantities = {item["product_id"]: item["quantity"] for item in stock.json()["items"]}
    assert quantities == {products[0]["id"]: 2, products[1]["id"]: 3}

    movements = client.get(
        f"/inventory/movements?warehouse_id={warehouse['id']}", headers=keeper
    ).json()["items"]
    assert len(movements) == 2
    assert all(item["reference_type"] == "goods_receipt" for item in movements)
    assert all(item["reference_id"] == received_order["receipt"]["number"] for item in movements)

    receipts = client.get("/goods-receipts", headers=keeper)
    assert receipts.status_code == 200
    assert any(item["id"] == received_order["receipt"]["id"] for item in receipts.json()["items"])


def test_admin_can_approve_an_order_they_created() -> None:
    suffix = uuid4().hex[:8]
    supplier, products, _ = create_entities(suffix)
    admin = login_headers("admin")

    created = client.post(
        "/purchase-orders",
        headers=admin,
        json=order_payload(supplier, products),
    )
    assert created.status_code == 201

    submitted = client.post(
        f"/purchase-orders/{created.json()['id']}/submit",
        headers=admin,
    )
    assert submitted.status_code == 200

    approved = client.post(
        f"/purchase-orders/{created.json()['id']}/approve",
        headers=admin,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == approved.json()["created_by"]


def test_rejection_and_cancellation_are_audited_and_terminal() -> None:
    suffix = uuid4().hex[:8]
    supplier, products, warehouse = create_entities(suffix)
    purchasing = login_headers("purchasing")
    manager = login_headers("manager")
    keeper = login_headers("warehouse")

    created = client.post(
        "/purchase-orders", headers=purchasing, json=order_payload(supplier, products)
    ).json()
    assert client.post(
        f"/purchase-orders/{created['id']}/submit", headers=purchasing
    ).status_code == 200
    rejected = client.post(
        f"/purchase-orders/{created['id']}/reject",
        headers=manager,
        json={"reason": "Budget is not approved"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "Budget is not approved"
    assert client.post(
        f"/purchase-orders/{created['id']}/receive",
        headers=keeper,
        json={"warehouse_id": warehouse["id"]},
    ).status_code == 422

    cancellable = client.post(
        "/purchase-orders", headers=purchasing, json=order_payload(supplier, products)
    ).json()
    cancelled = client.post(
        f"/purchase-orders/{cancellable['id']}/cancel",
        headers=purchasing,
        json={"reason": "Supplier changed the quotation"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.post(
        f"/purchase-orders/{cancellable['id']}/submit", headers=purchasing
    ).status_code == 422


def test_purchase_order_validation_and_rbac() -> None:
    suffix = uuid4().hex[:8]
    supplier, products, _warehouse = create_entities(suffix)
    purchasing = login_headers("purchasing")
    sales = login_headers("sales")
    manager = login_headers("manager")
    payload = order_payload(supplier, products)

    duplicate = payload | {"items": [payload["items"][0], payload["items"][0]]}
    assert client.post(
        "/purchase-orders", headers=purchasing, json=duplicate
    ).status_code == 422
    fractional = payload | {
        "items": [{"product_id": products[0]["id"], "quantity": 0.5, "unit_cost": "10.00"}]
    }
    assert client.post(
        "/purchase-orders", headers=purchasing, json=fractional
    ).status_code == 422
    assert client.post(
        "/purchase-orders", headers=sales, json=payload
    ).status_code == 403
    assert client.get("/purchase-orders", headers=sales).status_code == 403

    order = client.post("/purchase-orders", headers=purchasing, json=payload).json()
    assert client.post(
        f"/purchase-orders/{order['id']}/approve", headers=manager
    ).status_code == 422
