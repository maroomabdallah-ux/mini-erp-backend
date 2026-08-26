from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.agent.security.permissions import get_allowed_tools
from app.agent.tools import purchase_tools, supplier_tools


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def supplier(supplier_id=1):
    return SimpleNamespace(
        id=supplier_id,
        name="Acme Supplies",
        email="orders@acme.test",
        phone="12345",
        credit_terms="Net 30",
        is_active=True,
    )


def purchase_order(status="pending_approval"):
    product = SimpleNamespace(id=3, sku="SKU-3", name="Widget")
    item = SimpleNamespace(
        id=4,
        product=product,
        quantity=5,
        received_quantity=1,
        unit_cost=Decimal("12.50"),
        line_total=Decimal("62.50"),
    )
    return SimpleNamespace(
        id=7,
        number="PO-2026-0007",
        supplier=supplier(),
        warehouse=SimpleNamespace(id=2, code="MAIN", name="Main Warehouse"),
        status=status,
        expected_date=date(2026, 9, 1),
        total_amount=Decimal("62.50"),
        notes="Handle carefully",
        items=[item],
    )


def test_search_suppliers_bounds_limit_and_closes_session(monkeypatch):
    session = FakeSession()
    captured = {}
    monkeypatch.setattr(supplier_tools, "SessionLocal", lambda: session)

    def fake_list(db, **kwargs):
        captured.update(kwargs)
        return {"items": [supplier()]}

    monkeypatch.setattr(supplier_tools, "list_suppliers", fake_list)
    result = supplier_tools.search_suppliers.invoke({"search": "Acme", "limit": 999})

    assert result[0]["name"] == "Acme Supplies"
    assert captured == {"page": 1, "size": 20, "search": "Acme", "is_active": True}
    assert session.closed


def test_get_supplier_uses_service_and_closes_session(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(supplier_tools, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        supplier_tools,
        "get_supplier_service",
        lambda db, supplier_id: supplier(supplier_id),
    )

    result = supplier_tools.get_supplier.invoke({"supplier_id": 9})

    assert result["id"] == 9
    assert result["credit_terms"] == "Net 30"
    assert session.closed


def test_get_purchase_orders_uses_filters_and_preserves_decimal(monkeypatch):
    session = FakeSession()
    captured = {}
    monkeypatch.setattr(purchase_tools, "SessionLocal", lambda: session)

    def fake_list(db, **kwargs):
        captured.update(kwargs)
        return {"items": [purchase_order("approved")]}

    monkeypatch.setattr(purchase_tools, "list_purchase_orders", fake_list)
    result = purchase_tools.get_purchase_orders.invoke(
        {"search": "PO-2026", "status": "approved", "supplier_id": 1, "limit": 500}
    )

    assert captured["size"] == 50
    assert captured["status"] == "approved"
    assert result[0]["total_amount"] == Decimal("62.50")
    assert isinstance(result[0]["total_amount"], Decimal)
    assert session.closed


def test_get_purchase_order_includes_lines(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(purchase_tools, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        purchase_tools,
        "get_purchase_order_service",
        lambda db, order_id: purchase_order(),
    )

    result = purchase_tools.get_purchase_order.invoke({"purchase_order_id": 7})

    assert result["po_number"] == "PO-2026-0007"
    assert result["items"][0]["unit_cost"] == Decimal("12.50")
    assert result["items"][0]["product"]["sku"] == "SKU-3"
    assert session.closed


def test_pending_purchase_orders_uses_real_pending_status(monkeypatch):
    session = FakeSession()
    captured = {}
    monkeypatch.setattr(purchase_tools, "SessionLocal", lambda: session)

    def fake_list(db, **kwargs):
        captured.update(kwargs)
        return {"items": [purchase_order()]}

    monkeypatch.setattr(purchase_tools, "list_purchase_orders", fake_list)
    result = purchase_tools.get_pending_purchase_orders.invoke({"limit": 10})

    assert captured["status"] == "pending_approval"
    assert result[0]["status"] == "pending_approval"
    assert session.closed


def test_get_goods_receipts_uses_existing_read_service(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(purchase_tools, "SessionLocal", lambda: session)
    receipt = SimpleNamespace(
        id=8,
        number="GR-2026-0008",
        purchase_order_id=7,
        warehouse=SimpleNamespace(id=2, code="MAIN", name="Main Warehouse"),
        received_at=datetime(2026, 8, 26),
        items=[
            SimpleNamespace(
                product_id=3,
                product=SimpleNamespace(sku="SKU-3", name="Widget"),
                quantity=2,
            )
        ],
    )
    monkeypatch.setattr(
        purchase_tools,
        "list_goods_receipts",
        lambda db, **kwargs: {"items": [receipt]},
    )

    result = purchase_tools.get_goods_receipts.invoke({"limit": 20})

    assert result[0]["receipt_number"] == "GR-2026-0008"
    assert result[0]["items"][0]["quantity"] == 2
    assert session.closed


def test_purchasing_officer_gets_tools_and_unauthorized_role_does_not():
    purchasing_role = SimpleNamespace(
        name="Purchasing Officer",
        is_active=True,
        permissions=[
            SimpleNamespace(code="suppliers.read"),
            SimpleNamespace(code="purchase_orders.read"),
            SimpleNamespace(code="goods_receipts.read"),
        ],
    )
    unauthorized_role = SimpleNamespace(name="Unauthorized", is_active=True, permissions=[])

    purchasing_names = {
        tool.name for tool in get_allowed_tools(SimpleNamespace(roles=[purchasing_role]))
    }
    unauthorized_names = {
        tool.name for tool in get_allowed_tools(SimpleNamespace(roles=[unauthorized_role]))
    }
    expected = {
        "search_suppliers",
        "get_supplier",
        "get_purchase_orders",
        "get_purchase_order",
        "get_pending_purchase_orders",
        "get_goods_receipts",
    }

    assert expected <= purchasing_names
    assert expected.isdisjoint(unauthorized_names)
