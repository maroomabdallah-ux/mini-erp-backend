from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.agent import actions
from app.agent.action_schemas import PreparePurchaseOrderRequest
from app.agent.models import AgentPendingAction
from app.agent.tools.registry import READ_ONLY_TOOLS
from app.agent.tools.write_registry import get_write_tools_for_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, value):
        value.id = value.id or 51
        value.status = value.status or "pending"


def user(user_id=1, authorized=True):
    permissions = [SimpleNamespace(code="purchase_orders.create")] if authorized else []
    return SimpleNamespace(
        id=user_id,
        roles=[SimpleNamespace(is_active=True, permissions=permissions)],
    )


def request(product_id=12):
    return PreparePurchaseOrderRequest.model_validate(
        {
            "supplier_id": 4,
            "warehouse_id": 2,
            "expected_date": str(date.today() + timedelta(days=7)),
            "notes": "Agent PO test",
            "items": [{"product_id": product_id, "quantity": 20}],
        }
    )


def product(product_id=12):
    return SimpleNamespace(
        id=product_id,
        sku=f"SKU-{product_id}",
        name="Widget",
        cost_price=Decimal("7.50"),
    )


def preview():
    return SimpleNamespace(
        items=[SimpleNamespace(line_total=Decimal("150.00"))],
        total_amount=Decimal("150.00"),
    )


def patch_prepare(monkeypatch):
    monkeypatch.setattr(
        actions.repository,
        "get_conversation",
        lambda db, conversation_id, user_id: SimpleNamespace(id=conversation_id),
    )
    monkeypatch.setattr(
        actions.repository,
        "list_pending_actions_for_update",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        actions,
        "get_supplier",
        lambda db, supplier_id: SimpleNamespace(id=supplier_id, name="Supplier"),
    )
    monkeypatch.setattr(
        actions,
        "get_warehouse",
        lambda db, warehouse_id: SimpleNamespace(
            id=warehouse_id, code="MAIN", name="Main Warehouse"
        ),
    )
    monkeypatch.setattr(actions, "get_product", lambda db, product_id: product(product_id))
    monkeypatch.setattr(actions, "preview_purchase_order", lambda db, data: preview())


def pending_action(*, owner=1, status="pending", expired=False):
    payload = {
        "supplier_id": 4,
        "warehouse_id": 2,
        "expected_date": str(date.today() + timedelta(days=7)),
        "notes": "Agent PO test",
        "items": [
            {
                "product_id": 12,
                "quantity": 20,
                "unit_cost": "7.50",
            }
        ],
    }
    return SimpleNamespace(
        id=51,
        user_id=owner,
        conversation_id=3,
        action_type="create_purchase_order",
        payload=payload,
        summary={"total_amount": "150.00"},
        status=status,
        expires_at=datetime.now(UTC) + timedelta(minutes=-1 if expired else 10),
        executed_at=None,
        purchase_order_id=None,
        failure_category=None,
    )


def purchase_order():
    return SimpleNamespace(
        id=88,
        number="PO-2026-0088",
        supplier_id=4,
        warehouse_id=2,
        total_amount=Decimal("150.00"),
    )


def test_authorized_preparation_creates_pending_without_po(monkeypatch):
    db = FakeSession()
    patch_prepare(monkeypatch)
    create_calls = []
    monkeypatch.setattr(
        actions,
        "create_purchase_order",
        lambda *args, **kwargs: create_calls.append(1),
    )

    result = actions.prepare_create_purchase_order(
        db, user=user(), conversation_id=3, request=request()
    )

    pending = next(value for value in db.added if isinstance(value, AgentPendingAction))
    assert create_calls == []
    assert pending.payload["items"][0]["unit_cost"] == "7.50"
    assert result["summary"]["supplier"]["name"] == "Supplier"
    assert result["summary"]["warehouse"]["code"] == "MAIN"
    assert result["summary"]["total_amount"] == "150.00"
    assert "prepare_create_purchase_order" not in {tool.name for tool in READ_ONLY_TOOLS}
    assert {tool.name for tool in get_write_tools_for_user(user(), 3)} == {
        "prepare_create_purchase_order"
    }


def test_unauthorized_preparation_and_changed_permission_confirmation(monkeypatch):
    db = FakeSession()
    with pytest.raises(ForbiddenError, match="cannot perform"):
        actions.prepare_create_purchase_order(
            db, user=user(authorized=False), conversation_id=3, request=request()
        )

    action = pending_action()
    monkeypatch.setattr(
        actions.repository,
        "get_pending_action_for_update",
        lambda *args, **kwargs: action,
    )
    with pytest.raises(ForbiddenError, match="cannot perform"):
        actions.confirm_pending_action(
            db, action_id=51, user=user(authorized=False), ip_address=None
        )


def test_successful_confirmation_uses_stored_payload_and_audits(monkeypatch):
    db = FakeSession()
    action = pending_action()
    captured = {}
    audits = []
    monkeypatch.setattr(
        actions.repository,
        "get_pending_action_for_update",
        lambda db, action_id, user_id: action if user_id == action.user_id else None,
    )

    def fake_create(db, data, **kwargs):
        captured["data"] = data
        captured["kwargs"] = kwargs
        return purchase_order()

    monkeypatch.setattr(actions, "create_purchase_order", fake_create)
    monkeypatch.setattr(actions, "add_audit_log", lambda db, **kwargs: audits.append(kwargs))

    result = actions.confirm_pending_action(db, action_id=51, user=user(), ip_address=None)

    assert captured["data"].supplier_id == 4
    assert captured["data"].warehouse_id == 2
    assert captured["data"].items[0].quantity == 20
    assert captured["data"].items[0].unit_cost == Decimal("7.50")
    assert captured["kwargs"]["commit"] is False
    assert action.status == "executed"
    assert action.purchase_order_id == 88
    assert result["purchase_order_number"] == "PO-2026-0088"
    assert audits[0]["action"] == "agent_create_purchase_order"
    assert audits[0]["new_values"]["pending_action_id"] == 51
    assert audits[0]["new_values"]["success"] is True

    with pytest.raises(ConflictError, match="already been completed"):
        actions.confirm_pending_action(db, action_id=51, user=user(), ip_address=None)


def test_cross_user_and_expired_purchase_order_actions(monkeypatch):
    db = FakeSession()
    action = pending_action(expired=True)
    monkeypatch.setattr(
        actions.repository,
        "get_pending_action_for_update",
        lambda db, action_id, user_id: action if user_id == action.user_id else None,
    )
    with pytest.raises(NotFoundError):
        actions.confirm_pending_action(db, action_id=51, user=user(2), ip_address=None)
    with pytest.raises(ConflictError, match="expired"):
        actions.confirm_pending_action(db, action_id=51, user=user(1), ip_address=None)
    assert action.status == "expired"


@pytest.mark.parametrize("dependency", ["get_supplier", "get_warehouse", "get_product"])
def test_invalid_entities_fail_before_pending_action(monkeypatch, dependency):
    db = FakeSession()
    patch_prepare(monkeypatch)
    monkeypatch.setattr(
        actions,
        dependency,
        lambda *args, **kwargs: (_ for _ in ()).throw(NotFoundError("Unavailable")),
    )

    with pytest.raises(NotFoundError, match="Unavailable"):
        actions.prepare_create_purchase_order(
            db, user=user(), conversation_id=3, request=request()
        )

    assert not any(isinstance(value, AgentPendingAction) for value in db.added)


def test_purchase_order_service_failure_rolls_back_and_marks_failed(monkeypatch):
    db = FakeSession()
    action = pending_action()
    audits = []
    monkeypatch.setattr(
        actions.repository,
        "get_pending_action_for_update",
        lambda *args, **kwargs: action,
    )
    monkeypatch.setattr(
        actions,
        "create_purchase_order",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("PO service failed")),
    )
    monkeypatch.setattr(actions, "add_audit_log", lambda db, **kwargs: audits.append(kwargs))

    with pytest.raises(RuntimeError, match="PO service failed"):
        actions.confirm_pending_action(db, action_id=51, user=user(), ip_address=None)

    assert db.rollbacks == 1
    assert action.status == "failed"
    assert action.purchase_order_id is None
    assert audits[0]["new_values"]["success"] is False
