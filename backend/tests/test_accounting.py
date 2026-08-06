from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.features.accounting.models import Account, JournalEntry, JournalEntryLine
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    with SessionLocal() as db:
        entries = list(
            db.scalars(
                select(JournalEntry).where(JournalEntry.description.like("Test accounting %"))
            ).all()
        )
        if entries:
            ids = [entry.id for entry in entries]
            db.execute(delete(JournalEntryLine).where(JournalEntryLine.journal_entry_id.in_(ids)))
            db.execute(delete(JournalEntry).where(JournalEntry.id.in_(ids)))
        db.execute(delete(Account).where(Account.code.like("TAC-%")))
        db.commit()


def headers(login: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"login": login, "password": "Passw0rd!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_chart_of_accounts_and_balanced_manual_entry() -> None:
    accountant = headers("accountant")
    suffix = uuid4().hex[:6]
    accounts = client.get("/accounts", headers=accountant)
    assert accounts.status_code == 200
    cash = next(item for item in accounts.json() if item["code"] == "1000")
    created = client.post(
        "/accounts",
        headers=accountant,
        json={"code": f"TAC-{suffix}", "name": f"Test clearing {suffix}", "type": "asset"},
    )
    assert created.status_code == 201
    entry = client.post(
        "/journal-entries",
        headers=accountant,
        json={
            "entry_date": str(date.today()),
            "description": f"Test accounting {suffix}",
            "lines": [
                {"account_id": created.json()["id"], "debit": "25.00", "credit": "0"},
                {"account_id": cash["id"], "debit": "0", "credit": "25.00"},
            ],
        },
    )
    assert entry.status_code == 201
    assert entry.json()["source_reference"] == "Manual journal entry"
    assert sum(float(line["debit"]) for line in entry.json()["lines"]) == 25
    filtered = client.get(
        f"/journal-entries?account_id={created.json()['id']}", headers=accountant
    )
    assert filtered.status_code == 200 and filtered.json()["total"] == 1
    dashboard = client.get("/accounting/dashboard", headers=accountant)
    assert dashboard.status_code == 200
    assert "accounts_receivable" in dashboard.json()
    protected = client.put(
        f"/accounts/{cash['id']}",
        headers=accountant,
        json={"code": "1000", "name": "Cash", "type": "expense"},
    )
    assert protected.status_code == 422
    invalid = client.post(
        "/journal-entries",
        headers=accountant,
        json={
            "entry_date": str(date.today()),
            "description": f"Test accounting invalid {suffix}",
            "lines": [
                {"account_id": created.json()["id"], "debit": "20", "credit": "0"},
                {"account_id": cash["id"], "debit": "0", "credit": "10"},
            ],
        },
    )
    assert invalid.status_code == 422


def test_credit_policy_is_configurable() -> None:
    accountant = headers("accountant")
    updated = client.put(
        "/system-settings/sales",
        headers=accountant,
        json={"credit_limit_behavior": "warn"},
    )
    assert updated.status_code == 200
    assert updated.json()["credit_limit_behavior"] == "warn"
    client.put(
        "/system-settings/sales",
        headers=accountant,
        json={"credit_limit_behavior": "block"},
    )
