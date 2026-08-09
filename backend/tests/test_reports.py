
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def headers(login: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"login": login, "password": "Passw0rd!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_management_and_financial_reports() -> None:
    admin = headers("admin")
    endpoints = [
        "/reports/dashboard",
        "/reports/profit",
        "/reports/top-products",
        "/reports/inventory-valuation",
        "/reports/receivables-aging",
        "/reports/monthly-sales?months=6",
    ]
    responses = [client.get(endpoint, headers=admin) for endpoint in endpoints]
    assert all(response.status_code == 200 for response in responses)
    assert "gross_profit" in responses[1].json()
    assert "total_value" in responses[3].json()
    assert "total_outstanding" in responses[4].json()
    assert len(responses[5].json()) == 6


def test_report_permissions_and_stock_ledger() -> None:
    accountant = headers("accountant")
    manager = headers("manager")
    assert client.get("/reports/profit", headers=accountant).status_code == 200
    assert client.get("/reports/top-products", headers=accountant).status_code == 403
    assert client.get("/reports/top-products", headers=manager).status_code == 200
    valuation = client.get("/reports/inventory-valuation", headers=accountant)
    assert valuation.status_code == 200
    items = valuation.json()["items"]
    if items:
        ledger = client.get(
            f"/reports/stock-movements?product_id={items[0]['product_id']}",
            headers=accountant,
        )
        assert ledger.status_code == 200
        balances = [row["running_balance"] for row in ledger.json()]
        assert all(isinstance(value, int) for value in balances)
