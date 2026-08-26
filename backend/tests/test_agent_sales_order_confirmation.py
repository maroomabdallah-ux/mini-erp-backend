from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.agent import actions
from app.agent.action_schemas import PrepareSalesOrderConfirmationRequest
from app.agent.models import AgentPendingAction
from app.agent.tools.registry import READ_ONLY_TOOLS
from app.agent.tools.write_registry import get_write_tools_for_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.features.sales.exceptions import SalesOrderStateError


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
        value.id = value.id or 61
        value.status = value.status or "pending"


def user(user_id=1, authorized=True):
    permissions = [SimpleNamespace(code="sales_orders.confirm")] if authorized else []
    return SimpleNamespace(
        id=user_id,
        roles=[SimpleNamespace(is_active=True, permissions=permissions)],
    )


def sales_order(status="draft"):
    item = SimpleNamespace(
        product=SimpleNamespace(id=12, sku="SKU-12", name="Widget"),
        quantity=5,
        line_total=Decimal("50.00"),
    )
    return SimpleNamespace(
        id=24,
        number="SO-2026-0024",
        status=status,
        customer=SimpleNamespace(id=8, code="CUS-8", name="Customer"),
        items=[item],
        total_amount=Decimal("58.00"),
        warehouse_id=None,
    )


def warehouse():
    return SimpleNamespace(id=2, code="MAIN", name="Main Warehouse")


def request():
    return PrepareSalesOrderConfirmationRequest(sales_order_id=24, warehouse_id=2)


def patch_prepare(monkeypatch, order=None):
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
        "validate_order_confirmation",
        lambda db, order_id, data: (
            order or sales_order(),
            warehouse(),
            Decimal("20.00"),
            Decimal("78.00"),
            False,
        ),
    )


def pending_action(*, owner=1, status="pending", expired=False):
    return SimpleNamespace(
        id=61,
        user_id=owner,
        conversation_id=3,
        action_type="confirm_sales_order",
        payload={"sales_order_id": 24, "warehouse_id": 2},
        summary={"total_amount": "58.00"},
        status=status,
        expires_at=datetime.now(UTC) + timedelta(minutes=-1 if expired else 10),
        executed_at=None,
        sales_order_id=None,
        failure_category=None,
    )


def test_authorized_preparation_creates_pending_without_confirming(monkeypatch):
    db = FakeSession()
    order = sales_order()
    patch_prepare(monkeypatch, order)
    confirm_calls = []
    monkeypatch.setattr(actions, "confirm_order", lambda *args, **kwargs: confirm_calls.append(1))

    result = actions.prepare_confirm_sales_order(
        db, user=user(), conversation_id=3, request=request()
    )

    pending = next(value for value in db.added if isinstance(value, AgentPendingAction))
    assert confirm_calls == []
    assert order.status == "draft"
    assert pending.payload == {"sales_order_id": 24, "warehouse_id": 2}
    assert result["summary"]["sales_order"]["number"] == "SO-2026-0024"
    assert result["summary"]["current_status"] == "draft"
    assert "prepare_confirm_sales_order" not in {tool.name for tool in READ_ONLY_TOOLS}
    assert {tool.name for tool in get_write_tools_for_user(user(), 3)} == {
        "prepare_confirm_sales_order"
    }


def test_unauthorized_preparation_and_revoked_confirmation(monkeypatch):
    db = FakeSession()
    with pytest.raises(ForbiddenError, match="cannot perform"):
        actions.prepare_confirm_sales_order(
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
            db, action_id=61, user=user(authorized=False), ip_address=None
        )


@pytest.mark.parametrize("status", ["confirmed", "cancelled", "delivered"])
def test_non_draft_order_cannot_be_prepared(monkeypatch, status):
    db = FakeSession()
    patch_prepare(monkeypatch)
    monkeypatch.setattr(
        actions,
        "validate_order_confirmation",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SalesOrderStateError("Only draft sales orders can be confirmed.")
        ),
    )

    with pytest.raises(SalesOrderStateError, match="Only draft"):
        actions.prepare_confirm_sales_order(
            db, user=user(), conversation_id=3, request=request()
        )

    assert not any(isinstance(value, AgentPendingAction) for value in db.added)


def test_successful_confirmation_revalidates_executes_once_and_audits(monkeypatch):
    db = FakeSession()
    action = pending_action()
    calls = []
    audits = []
    monkeypatch.setattr(
        actions.repository,
        "get_pending_action_for_update",
        lambda db, action_id, user_id: action if user_id == action.user_id else None,
    )

    def fake_confirm(db, order_id, data, **kwargs):
        calls.append((order_id, data.warehouse_id, kwargs))
        order = sales_order("confirmed")
        order.warehouse_id = data.warehouse_id
        return order

    monkeypatch.setattr(actions, "confirm_order", fake_confirm)
    monkeypatch.setattr(actions, "add_audit_log", lambda db, **kwargs: audits.append(kwargs))

    result = actions.confirm_pending_action(db, action_id=61, user=user(), ip_address=None)

    assert calls == [(24, 2, {"actor_id": 1, "ip_address": None, "commit": False})]
    assert action.status == "executed"
    assert action.sales_order_id == 24
    assert result["sales_order_number"] == "SO-2026-0024"
    assert audits[0]["action"] == "agent_confirm_sales_order"
    assert audits[0]["new_values"]["old_status"] == "draft"
    assert audits[0]["new_values"]["new_status"] == "confirmed"

    with pytest.raises(ConflictError, match="already been completed"):
        actions.confirm_pending_action(db, action_id=61, user=user(), ip_address=None)
    assert len(calls) == 1


def test_state_changed_between_prepare_and_confirmation_fails(monkeypatch):
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
        "confirm_order",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SalesOrderStateError("Only draft sales orders can be confirmed.")
        ),
    )
    monkeypatch.setattr(actions, "add_audit_log", lambda db, **kwargs: audits.append(kwargs))

    with pytest.raises(SalesOrderStateError, match="Only draft"):
        actions.confirm_pending_action(db, action_id=61, user=user(), ip_address=None)

    assert db.rollbacks == 1
    assert action.status == "failed"
    assert audits[0]["new_values"]["success"] is False


def test_cross_user_and_expired_confirmation_are_blocked(monkeypatch):
    db = FakeSession()
    action = pending_action(expired=True)
    monkeypatch.setattr(
        actions.repository,
        "get_pending_action_for_update",
        lambda db, action_id, user_id: action if user_id == action.user_id else None,
    )
    with pytest.raises(NotFoundError):
        actions.confirm_pending_action(db, action_id=61, user=user(2), ip_address=None)
    with pytest.raises(ConflictError, match="expired"):
        actions.confirm_pending_action(db, action_id=61, user=user(1), ip_address=None)
    assert action.status == "expired"


def test_confirmation_service_failure_rolls_back_without_false_success(monkeypatch):
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
        "confirm_order",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("confirm failed")),
    )
    monkeypatch.setattr(actions, "add_audit_log", lambda db, **kwargs: audits.append(kwargs))

    with pytest.raises(RuntimeError, match="confirm failed"):
        actions.confirm_pending_action(db, action_id=61, user=user(), ip_address=None)

    assert db.rollbacks == 1
    assert action.status == "failed"
    assert action.sales_order_id is None
    assert audits[0]["new_values"]["success"] is False
