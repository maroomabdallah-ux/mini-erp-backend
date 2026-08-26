from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agent.schemas import AgentChatRequest
from app.agent.security.permissions import TOOL_PERMISSIONS, get_allowed_tools
from app.agent import assistant
from app.agent.tools import accounting_tools, warehouse_tools
from app.agent.tools.registry import READ_ONLY_TOOLS
from app.seed import PERMISSIONS, ROLE_PERMISSIONS


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _product():
    return SimpleNamespace(id=1, sku="SKU-1", name="Widget", min_stock_level=Decimal("5"))


def _warehouse():
    return SimpleNamespace(id=2, code="MAIN", name="Main Warehouse")


def _user(name, permission_codes):
    return SimpleNamespace(
        id=1,
        roles=[
            SimpleNamespace(
                name=name,
                is_active=True,
                permissions=[SimpleNamespace(code=code) for code in permission_codes],
            )
        ],
    )


def test_warehouse_tools_use_services_bound_results_and_close_sessions(monkeypatch):
    sessions = []

    def session_factory():
        session = FakeSession()
        sessions.append(session)
        return session

    movement = SimpleNamespace(
        id=3,
        product=_product(),
        warehouse=_warehouse(),
        type="in",
        quantity=Decimal("4"),
        reference_type="goods_receipt",
        reference_id="8",
        reason=None,
        created_at=datetime(2026, 8, 26),
    )
    stock = SimpleNamespace(
        product=_product(), quantity=Decimal("9"), updated_at=datetime(2026, 8, 26)
    )
    count = SimpleNamespace(
        id=4,
        reference="CNT-4",
        product=_product(),
        warehouse=_warehouse(),
        expected_quantity=Decimal("9"),
        counted_quantity=Decimal("8"),
        variance=Decimal("-1"),
        status="pending",
        created_at=datetime(2026, 8, 26),
    )
    captured = {}
    monkeypatch.setattr(warehouse_tools, "SessionLocal", session_factory)
    def fake_movements(db, **kwargs):
        captured["movements"] = kwargs
        return {"items": [movement]}

    monkeypatch.setattr(warehouse_tools, "list_movements", fake_movements)
    monkeypatch.setattr(
        warehouse_tools,
        "list_stock",
        lambda db, **kwargs: {"items": [stock], "total_quantity": Decimal("9")},
    )
    monkeypatch.setattr(
        warehouse_tools,
        "list_counts",
        lambda db, **kwargs: {"items": [count]},
    )

    movements = warehouse_tools.get_stock_movements.invoke({"limit": 500})
    inventory = warehouse_tools.get_inventory_by_warehouse.invoke({"warehouse_id": 2})
    counts = warehouse_tools.get_inventory_counts.invoke({"status": "pending"})

    assert captured["movements"]["size"] == 50
    assert movements[0]["quantity"] == "4"
    assert inventory["items"][0]["quantity"] == "9"
    assert counts[0]["variance"] == "-1"
    assert all(session.closed for session in sessions)


def test_accounting_tools_use_services_and_decimal_strings(monkeypatch):
    sessions = []

    def session_factory():
        session = FakeSession()
        sessions.append(session)
        return session

    statement = {
        "entity_id": 4,
        "entity_name": "Example",
        "date_from": date(2026, 8, 1),
        "date_to": date(2026, 8, 31),
        "opening_balance": Decimal("10.00"),
        "closing_balance": Decimal("15.00"),
        "lines": [
            {
                "date": date(2026, 8, 2),
                "reference": "INV-1",
                "description": "Invoice",
                "debit": Decimal("5.00"),
                "credit": Decimal("0.00"),
                "balance": Decimal("15.00"),
            }
        ],
    }
    invoice = SimpleNamespace(
        id=7,
        number="INV-7",
        customer_id=4,
        status="issued",
        total_amount=Decimal("30.00"),
        paid_amount=Decimal("5.00"),
        due_date=date(2026, 9, 1),
    )
    monkeypatch.setattr(accounting_tools, "SessionLocal", session_factory)
    monkeypatch.setattr(accounting_tools, "customer_statement", lambda *args: statement)
    monkeypatch.setattr(accounting_tools, "supplier_statement", lambda *args: statement)
    monkeypatch.setattr(accounting_tools, "get_invoice_service", lambda *args: invoice)
    monkeypatch.setattr(
        accounting_tools,
        "list_entries",
        lambda db, **kwargs: {
            "items": [
                {
                    "id": 1,
                    "number": "JE-1",
                    "entry_date": date(2026, 8, 2),
                    "description": "Invoice",
                    "source_type": "sales_invoice",
                    "source_reference": "INV-1",
                    "total_amount": Decimal("30.00"),
                }
            ]
        },
    )
    monkeypatch.setattr(
        accounting_tools,
        "inventory_valuation",
        lambda db: {
            "total_quantity": Decimal("9"),
            "total_value": Decimal("90.00"),
            "items": [
                {
                    "warehouse_id": 2,
                    "product_id": 1,
                    "quantity": Decimal("9"),
                    "unit_cost": Decimal("10.00"),
                    "inventory_value": Decimal("90.00"),
                }
            ],
        },
    )

    customer_result = accounting_tools.get_customer_statement.invoke(
        {"customer_id": 4, "date_from": "2026-08-01", "date_to": "2026-08-31"}
    )
    accounting_tools.get_supplier_statement.invoke(
        {"supplier_id": 4, "date_from": "2026-08-01", "date_to": "2026-08-31"}
    )
    balance = accounting_tools.get_invoice_balance.invoke({"invoice_id": 7})
    entries = accounting_tools.get_journal_entries.invoke({"limit": 500})
    valuation = accounting_tools.get_inventory_valuation.invoke({"limit": 20})

    assert customer_result["closing_balance"] == "15.00"
    assert balance["balance"] == "25.00"
    assert entries[0]["total_amount"] == "30.00"
    assert valuation["total_value"] == "90.00"
    assert all(session.closed for session in sessions)


def test_registry_permissions_roles_and_no_write_exposure():
    registered_names = {tool.name for tool in READ_ONLY_TOOLS}
    assert registered_names <= TOOL_PERMISSIONS.keys()

    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        expected = {
            tool.name
            for tool in READ_ONLY_TOOLS
            if TOOL_PERMISSIONS[tool.name] <= permission_codes
        }
        actual = {tool.name for tool in get_allowed_tools(_user(role_name, permission_codes))}
        assert actual == expected

    admin_names = {tool.name for tool in get_allowed_tools(_user("admin", set(PERMISSIONS)))}
    assert admin_names == registered_names

    forbidden_actions = {"create", "update", "delete", "approve", "cancel", "transfer", "adjust"}
    assert not any(
        action in tool_name.lower()
        for tool_name in registered_names
        for action in forbidden_actions
    )


def test_agent_message_length_validation():
    with pytest.raises(ValidationError):
        AgentChatRequest(message="")
    with pytest.raises(ValidationError):
        AgentChatRequest(message="x" * 2001)


def test_agent_creation_receives_permission_guarded_tools(monkeypatch):
    captured = {}
    user = _user("sales_officer", {"invoices.read"})
    monkeypatch.setattr(assistant, "ChatOpenAI", lambda **kwargs: SimpleNamespace())

    def fake_create_agent(*, model, tools, system_prompt):
        captured["tools"] = tools
        return SimpleNamespace()

    monkeypatch.setattr(assistant, "create_agent", fake_create_agent)
    assistant.build_agent_for_user(user, conversation_id=1)

    invoice_tool = next(tool for tool in captured["tools"] if tool.name == "get_invoices")
    user.roles[0].permissions.clear()
    with pytest.raises(PermissionError, match="^Tool access denied\\.$"):
        invoice_tool.invoke({})
