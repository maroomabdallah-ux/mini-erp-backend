from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.agent.security.permissions import (
    TOOL_PERMISSIONS,
    get_allowed_tools,
    secure_tool_for_user,
)
from app.agent.tools import sales_tools
from app.agent.tools.registry import READ_ONLY_TOOLS


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def customer():
    return SimpleNamespace(id=4, code="CUS-004", name="Example Customer")


def product():
    return SimpleNamespace(id=3, sku="SKU-3", name="Widget")


def quotation():
    item = SimpleNamespace(
        id=2,
        product=product(),
        quantity=2,
        unit_price=Decimal("15.00"),
        discount_percent=Decimal("0.00"),
        line_total=Decimal("30.00"),
    )
    return SimpleNamespace(
        id=1,
        number="QT-001",
        customer=customer(),
        status="sent",
        valid_until=date(2026, 9, 30),
        created_at=datetime(2026, 8, 20),
        total_amount=Decimal("34.80"),
        notes=None,
        subtotal=Decimal("30.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("4.80"),
        items=[item],
    )


def sales_order():
    item = SimpleNamespace(
        id=5,
        product=product(),
        quantity=2,
        unit_price=Decimal("15.00"),
        discount_percent=Decimal("0.00"),
        line_total=Decimal("30.00"),
    )
    return SimpleNamespace(
        id=6,
        number="SO-006",
        customer=customer(),
        status="confirmed",
        created_at=datetime(2026, 8, 21),
        total_amount=Decimal("34.80"),
        quotation_id=1,
        notes=None,
        subtotal=Decimal("30.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("4.80"),
        items=[item],
    )


def invoice():
    return SimpleNamespace(
        id=7,
        number="INV-007",
        customer=customer(),
        status="partially_paid",
        issue_date=date(2026, 8, 22),
        due_date=date(2026, 9, 22),
        total_amount=Decimal("34.80"),
        paid_amount=Decimal("10.00"),
    )


def test_get_quotations_uses_existing_filters_and_bounds_limit(monkeypatch):
    session = FakeSession()
    captured = {}
    monkeypatch.setattr(sales_tools, "SessionLocal", lambda: session)

    def fake_list(db, **kwargs):
        captured.update(kwargs)
        return {"items": [quotation()]}

    monkeypatch.setattr(sales_tools, "list_quotations", fake_list)
    result = sales_tools.get_quotations.invoke(
        {"search": "QT", "status": "sent", "customer_id": 4, "limit": 500}
    )

    assert captured["size"] == 50
    assert result[0]["total_amount"] == Decimal("34.80")
    assert session.closed


def test_get_quotation_includes_existing_lines(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(sales_tools, "SessionLocal", lambda: session)
    monkeypatch.setattr(sales_tools, "get_quotation_service", lambda db, item_id: quotation())

    result = sales_tools.get_quotation.invoke({"quotation_id": 1})

    assert result["quotation_number"] == "QT-001"
    assert result["items"][0]["unit_price"] == Decimal("15.00")
    assert session.closed


def test_get_sales_orders_uses_existing_filters(monkeypatch):
    session = FakeSession()
    captured = {}
    monkeypatch.setattr(sales_tools, "SessionLocal", lambda: session)

    def fake_list(db, **kwargs):
        captured.update(kwargs)
        return {"items": [sales_order()]}

    monkeypatch.setattr(sales_tools, "list_orders", fake_list)
    result = sales_tools.get_sales_orders.invoke(
        {"status": "confirmed", "customer_id": 4, "limit": 10}
    )

    assert captured["status"] == "confirmed"
    assert result[0]["sales_order_number"] == "SO-006"
    assert session.closed


def test_get_sales_order_includes_existing_lines(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(sales_tools, "SessionLocal", lambda: session)
    monkeypatch.setattr(sales_tools, "get_sales_order_service", lambda db, item_id: sales_order())

    result = sales_tools.get_sales_order.invoke({"sales_order_id": 6})

    assert result["items"][0]["product"]["sku"] == "SKU-3"
    assert result["total_amount"] == Decimal("34.80")
    assert session.closed


def test_get_invoices_returns_money_as_strings(monkeypatch):
    session = FakeSession()
    captured = {}
    monkeypatch.setattr(sales_tools, "SessionLocal", lambda: session)

    def fake_list(db, **kwargs):
        captured.update(kwargs)
        return {"items": [invoice()]}

    monkeypatch.setattr(sales_tools, "list_invoices", fake_list)
    result = sales_tools.get_invoices.invoke({"overdue": True, "limit": 500})

    assert captured["overdue"] is True
    assert captured["size"] == 50
    assert result[0]["total_amount"] == "34.80"
    assert result[0]["balance"] == "24.80"
    assert session.closed


def test_get_customer_sales_reuses_order_and_invoice_filters(monkeypatch):
    session = FakeSession()
    calls = []
    monkeypatch.setattr(sales_tools, "SessionLocal", lambda: session)

    def fake_orders(db, **kwargs):
        calls.append(("orders", kwargs))
        return {"items": [sales_order()]}

    def fake_invoices(db, **kwargs):
        calls.append(("invoices", kwargs))
        return {"items": [invoice()]}

    monkeypatch.setattr(sales_tools, "list_orders", fake_orders)
    monkeypatch.setattr(sales_tools, "list_invoices", fake_invoices)
    result = sales_tools.get_customer_sales.invoke({"customer_id": 4, "limit": 20})

    assert all(call[1]["customer_id"] == 4 for call in calls)
    assert result["sales_orders"][0]["id"] == 6
    assert result["invoices"][0]["id"] == 7
    assert session.closed


def _user(name, permission_codes):
    role = SimpleNamespace(
        name=name,
        is_active=True,
        permissions=[SimpleNamespace(code=code) for code in permission_codes],
    )
    return SimpleNamespace(id=1, roles=[role])


def test_sales_officer_unauthorized_and_admin_tool_access():
    sales_names = {
        tool.name
        for tool in get_allowed_tools(
            _user("sales_officer", {"quotations.read", "sales_orders.read", "invoices.read"})
        )
    }
    expected_sales = {
        "get_quotations",
        "get_quotation",
        "get_sales_orders",
        "get_sales_order",
        "get_invoices",
        "get_customer_sales",
    }
    unauthorized_names = {tool.name for tool in get_allowed_tools(_user("unauthorized", set()))}
    all_permissions = set().union(*TOOL_PERMISSIONS.values())
    admin_names = {tool.name for tool in get_allowed_tools(_user("admin", all_permissions))}

    assert expected_sales <= sales_names
    assert expected_sales.isdisjoint(unauthorized_names)
    assert admin_names == {tool.name for tool in READ_ONLY_TOOLS}


def test_secure_wrapper_rechecks_permission_without_disclosing_details():
    secured = secure_tool_for_user(_user("unauthorized", set()), sales_tools.get_invoices)

    with pytest.raises(PermissionError, match="^Tool access denied\\.$"):
        secured.invoke({})
