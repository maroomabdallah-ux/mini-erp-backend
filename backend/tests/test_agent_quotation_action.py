from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.agent import actions
from app.agent.action_schemas import PrepareQuotationRequest
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
        value.id = value.id or 41
        value.status = value.status or "pending"


def user(user_id=1, authorized=True):
    permissions = [SimpleNamespace(code="quotations.manage")] if authorized else []
    role = SimpleNamespace(is_active=True, permissions=permissions)
    return SimpleNamespace(id=user_id, roles=[role])


def request(product_id=12):
    return PrepareQuotationRequest.model_validate(
        {
            "customer_id": 8,
            "valid_until": str(date.today() + timedelta(days=14)),
            "tax_percent": "16.00",
            "items": [{"product_id": product_id, "quantity": 5}],
        }
    )


def product(product_id=12):
    return SimpleNamespace(
        id=product_id,
        sku=f"SKU-{product_id}",
        name="Widget",
        sale_price=Decimal("10.00"),
    )


def preview():
    return SimpleNamespace(
        items=[SimpleNamespace(line_total=Decimal("50.00"))],
        subtotal=Decimal("50.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("8.00"),
        total_amount=Decimal("58.00"),
    )


def patch_prepare_dependencies(monkeypatch, existing=None):
    monkeypatch.setattr(
        actions.repository,
        "get_conversation",
        lambda db, conversation_id, user_id: SimpleNamespace(id=conversation_id),
    )
    monkeypatch.setattr(
        actions.repository,
        "list_pending_actions_for_update",
        lambda *args, **kwargs: existing or [],
    )
    monkeypatch.setattr(
        actions,
        "get_customer",
        lambda db, customer_id: SimpleNamespace(id=customer_id, code="CUS-8", name="Customer"),
    )
    monkeypatch.setattr(actions, "get_product", lambda db, product_id: product(product_id))
    monkeypatch.setattr(actions, "preview_quotation", lambda db, data: preview())


def test_authorized_prepare_creates_only_pending_action_with_erp_totals(monkeypatch):
    db = FakeSession()
    patch_prepare_dependencies(monkeypatch)
    create_calls = []
    monkeypatch.setattr(actions, "create_quotation", lambda *args, **kwargs: create_calls.append(1))

    result = actions.prepare_create_quotation(
        db, user=user(), conversation_id=3, request=request()
    )

    pending = next(value for value in db.added if isinstance(value, AgentPendingAction))
    assert create_calls == []
    assert pending.payload["items"][0]["unit_price"] == "10.00"
    assert result["action_id"] == 41
    assert result["summary"]["total_amount"] == "58.00"
    assert result["summary"]["confirmation_required"] is True


def test_unauthorized_user_cannot_prepare_or_confirm(monkeypatch):
    db = FakeSession()
    action = pending_action()
    monkeypatch.setattr(
        actions.repository,
        "get_pending_action_for_update",
        lambda *args, **kwargs: action,
    )
    with pytest.raises(ForbiddenError, match="cannot perform"):
        actions.prepare_create_quotation(
            db, user=user(authorized=False), conversation_id=3, request=request()
        )
    with pytest.raises(ForbiddenError, match="cannot perform"):
        actions.confirm_pending_action(
            db, action_id=1, user=user(authorized=False), ip_address=None
        )
    assert get_write_tools_for_user(user(authorized=False), conversation_id=3) == []
    assert "prepare_create_quotation" not in {tool.name for tool in READ_ONLY_TOOLS}


def pending_action(*, status="pending", owner=1, expired=False):
    return SimpleNamespace(
        id=41,
        user_id=owner,
        conversation_id=3,
        action_type="create_quotation",
        payload=request().model_dump(mode="json")
        | {
            "items": [
                {
                    "product_id": 12,
                    "quantity": 5,
                    "unit_price": "10.00",
                    "discount_percent": "0.00",
                }
            ]
        },
        summary={"total_amount": "58.00"},
        status=status,
        expires_at=datetime.now(UTC) + timedelta(minutes=-1 if expired else 10),
        executed_at=None,
        quotation_id=None,
        failure_category=None,
    )


def quotation():
    return SimpleNamespace(
        id=77,
        number="QT-20260826-TEST",
        customer_id=8,
        total_amount=Decimal("58.00"),
    )


def test_confirmation_executes_stored_payload_once_and_audits(monkeypatch):
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
        return quotation()

    monkeypatch.setattr(actions, "create_quotation", fake_create)
    monkeypatch.setattr(actions, "add_audit_log", lambda db, **kwargs: audits.append(kwargs))

    result = actions.confirm_pending_action(db, action_id=41, user=user(), ip_address="127.0.0.1")

    assert captured["data"].items[0].product_id == 12
    assert captured["data"].items[0].unit_price == Decimal("10.00")
    assert captured["kwargs"]["commit"] is False
    assert action.status == "executed"
    assert action.quotation_id == 77
    assert result["quotation_id"] == 77
    assert audits[0]["new_values"]["pending_action_id"] == 41
    assert audits[0]["new_values"]["success"] is True

    with pytest.raises(ConflictError, match="already been completed"):
        actions.confirm_pending_action(db, action_id=41, user=user(), ip_address=None)


def test_cross_user_and_expired_actions_cannot_execute(monkeypatch):
    db = FakeSession()
    action = pending_action(expired=True)
    monkeypatch.setattr(
        actions.repository,
        "get_pending_action_for_update",
        lambda db, action_id, user_id: action if user_id == action.user_id else None,
    )
    with pytest.raises(NotFoundError):
        actions.confirm_pending_action(db, action_id=41, user=user(2), ip_address=None)
    with pytest.raises(ConflictError, match="expired"):
        actions.confirm_pending_action(db, action_id=41, user=user(1), ip_address=None)
    assert action.status == "expired"


def test_confirmation_ignores_changed_request_and_uses_stored_payload(monkeypatch):
    db = FakeSession()
    action = pending_action()
    captured = {}
    monkeypatch.setattr(
        actions.repository,
        "get_pending_action_for_update",
        lambda *args, **kwargs: action,
    )
    def fake_create(db, data, **kwargs):
        captured["data"] = data
        return quotation()

    monkeypatch.setattr(actions, "create_quotation", fake_create)
    monkeypatch.setattr(actions, "add_audit_log", lambda *args, **kwargs: None)

    actions.confirm_pending_action(db, action_id=41, user=user(), ip_address=None)

    assert captured["data"].customer_id == 8
    assert captured["data"].items[0].quantity == 5


def test_failed_service_rolls_back_marks_failed_and_audits(monkeypatch):
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
        "create_quotation",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("service failed")),
    )
    monkeypatch.setattr(actions, "add_audit_log", lambda db, **kwargs: audits.append(kwargs))

    with pytest.raises(RuntimeError, match="service failed"):
        actions.confirm_pending_action(db, action_id=41, user=user(), ip_address=None)

    assert db.rollbacks == 1
    assert action.status == "failed"
    assert action.failure_category == "RuntimeError"
    assert audits[0]["new_values"]["success"] is False


def test_reprepare_reuses_identical_pending_action(monkeypatch):
    db = FakeSession()
    existing = pending_action()
    patch_prepare_dependencies(monkeypatch, existing=[existing])

    result = actions.prepare_create_quotation(
        db, user=user(), conversation_id=3, request=request()
    )

    assert result["action_id"] == 41
    assert not any(isinstance(value, AgentPendingAction) for value in db.added)


def test_owner_can_cancel_pending_action(monkeypatch):
    db = FakeSession()
    action = pending_action()
    monkeypatch.setattr(
        actions.repository,
        "get_pending_action_for_update",
        lambda db, action_id, user_id: action if user_id == action.user_id else None,
    )

    result = actions.cancel_pending_action(db, action_id=41, user=user())

    assert result == {"action_id": 41, "status": "cancelled"}
    assert action.status == "cancelled"
