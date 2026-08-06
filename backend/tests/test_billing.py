from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.features.audit.model import AuditLog
from app.features.billing.models import Invoice, InvoiceItem, Payment
from app.features.customers.models import Customer
from app.features.products.models import Product
from app.features.quotations.models import Quotation, QuotationItem
from app.features.sales.models import SalesDelivery, SalesDeliveryItem, SalesOrder, SalesOrderItem
from app.features.warehouses.models import Warehouse
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    with SessionLocal() as db:
        invoices = list(
            db.scalars(select(Invoice).where(Invoice.notes.like("Test billing %"))).all()
        )
        invoice_ids = [item.id for item in invoices]
        order_ids = [item.sales_order_id for item in invoices]
        orders = (
            list(db.scalars(select(SalesOrder).where(SalesOrder.id.in_(order_ids))).all())
            if order_ids
            else []
        )
        quote_ids = [item.quotation_id for item in orders]
        customer_ids = [item.customer_id for item in invoices]
        delivery_ids = (
            list(
                db.scalars(
                    select(SalesDelivery.id).where(SalesDelivery.sales_order_id.in_(order_ids))
                ).all()
            )
            if order_ids
            else []
        )
        if invoice_ids:
            payment_ids = list(
                db.scalars(select(Payment.id).where(Payment.invoice_id.in_(invoice_ids))).all()
            )
            if payment_ids:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.table_name == "payments",
                        AuditLog.record_id.in_([str(value) for value in payment_ids]),
                    )
                )
            db.execute(delete(Payment).where(Payment.invoice_id.in_(invoice_ids)))
            db.execute(delete(InvoiceItem).where(InvoiceItem.invoice_id.in_(invoice_ids)))
            db.execute(
                delete(AuditLog).where(
                    AuditLog.table_name == "invoices",
                    AuditLog.record_id.in_([str(value) for value in invoice_ids]),
                )
            )
            db.execute(delete(Invoice).where(Invoice.id.in_(invoice_ids)))
        if delivery_ids:
            db.execute(
                delete(SalesDeliveryItem).where(
                    SalesDeliveryItem.sales_delivery_id.in_(delivery_ids)
                )
            )
            db.execute(delete(SalesDelivery).where(SalesDelivery.id.in_(delivery_ids)))
        if order_ids:
            db.execute(delete(SalesOrderItem).where(SalesOrderItem.sales_order_id.in_(order_ids)))
            db.execute(delete(SalesOrder).where(SalesOrder.id.in_(order_ids)))
        if quote_ids:
            db.execute(delete(QuotationItem).where(QuotationItem.quotation_id.in_(quote_ids)))
            db.execute(delete(Quotation).where(Quotation.id.in_(quote_ids)))
        if customer_ids:
            db.execute(delete(Customer).where(Customer.id.in_(customer_ids)))
        db.commit()


def headers(login: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"login": login, "password": "Passw0rd!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def delivered_order(suffix: str) -> int:
    with SessionLocal() as db:
        product = db.scalar(select(Product).where(Product.is_active.is_(True)).limit(1))
        warehouse = db.scalar(select(Warehouse).where(Warehouse.is_active.is_(True)).limit(1))
        assert product and warehouse
        customer = Customer(
            code=f"TBC-{suffix}",
            name=f"Test Billing Customer {suffix}",
            email=f"billing-{suffix}@example.com",
            is_active=True,
        )
        db.add(customer)
        db.flush()
        quote = Quotation(
            number=f"TQ-{suffix}",
            customer_id=customer.id,
            status="converted",
            valid_until=date.today() + timedelta(days=7),
            notes=f"Test billing {suffix}",
            discount_percent=Decimal("0"),
            tax_percent=Decimal("0"),
            subtotal=Decimal("100"),
            discount_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            total_amount=Decimal("100"),
            created_by=1,
            items=[
                QuotationItem(
                    product_id=product.id,
                    quantity=2,
                    unit_price=Decimal("50"),
                    line_total=Decimal("100"),
                )
            ],
        )
        db.add(quote)
        db.flush()
        order = SalesOrder(
            number=f"TSO-{suffix}",
            quotation_id=quote.id,
            customer_id=customer.id,
            status="delivered",
            notes=f"Test billing {suffix}",
            subtotal=Decimal("100"),
            discount_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            total_amount=Decimal("100"),
            created_by=1,
            items=[
                SalesOrderItem(
                    product_id=product.id,
                    quantity=2,
                    unit_price=Decimal("50"),
                    line_total=Decimal("100"),
                )
            ],
        )
        db.add(order)
        db.flush()
        db.add(
            SalesDelivery(
                number=f"TSD-{suffix}",
                sales_order_id=order.id,
                warehouse_id=warehouse.id,
                delivered_by=1,
                items=[SalesDeliveryItem(product_id=product.id, quantity=2)],
            )
        )
        db.commit()
        return order.id


def test_invoice_issue_partial_and_full_payment_with_reversal() -> None:
    suffix = uuid4().hex[:8]
    order_id = delivered_order(suffix)
    sales = headers("sales")
    accountant = headers("accountant")
    created = client.post(
        "/invoices",
        headers=sales,
        json={"sales_order_id": order_id, "notes": f"Test billing {suffix}"},
    )
    assert created.status_code == 201
    invoice = created.json()
    assert invoice["status"] == "draft" and invoice["balance_due"] == "100.00"
    assert (
        client.post("/invoices", headers=sales, json={"sales_order_id": order_id}).status_code
        == 409
    )
    issued = client.post(f"/invoices/{invoice['id']}/issue", headers=sales)
    assert issued.status_code == 200 and issued.json()["status"] == "issued"
    partial = client.post(
        f"/invoices/{invoice['id']}/payments",
        headers=accountant,
        json={
            "amount": "35.00",
            "payment_date": str(date.today()),
            "method": "bank_transfer",
            "reference": "BANK-TEST",
        },
    )
    assert partial.status_code == 201
    assert partial.json()["status"] == "partially_paid" and partial.json()["balance_due"] == "65.00"
    timeline = client.get(
        f"/invoices/{invoice['id']}/accounting-timeline", headers=accountant
    )
    assert timeline.status_code == 200
    assert {event["key"] for event in timeline.json()} >= {
        "invoice_created",
        "invoice_journal",
        f"payment_{partial.json()['payments'][0]['id']}",
    }
    assert (
        client.post(
            f"/invoices/{invoice['id']}/payments",
            headers=accountant,
            json={"amount": "66.00", "payment_date": str(date.today()), "method": "cash"},
        ).status_code
        == 422
    )
    paid = client.post(
        f"/invoices/{invoice['id']}/payments",
        headers=accountant,
        json={"amount": "65.00", "payment_date": str(date.today()), "method": "cash"},
    )
    assert paid.status_code == 201 and paid.json()["status"] == "paid"
    payment_id = paid.json()["payments"][-1]["id"]
    reversed_invoice = client.post(
        f"/payments/{payment_id}/reverse",
        headers=accountant,
        json={"reason": "Incorrect cash receipt"},
    )
    assert reversed_invoice.status_code == 200
    assert (
        reversed_invoice.json()["status"] == "partially_paid"
        and reversed_invoice.json()["balance_due"] == "65.00"
    )


def test_billing_rbac_and_cancellation() -> None:
    suffix = uuid4().hex[:8]
    order_id = delivered_order(suffix)
    sales = headers("sales")
    accountant = headers("accountant")
    manager = headers("manager")
    warehouse = headers("warehouse")
    invoice = client.post(
        "/invoices",
        headers=sales,
        json={"sales_order_id": order_id, "notes": f"Test billing {suffix}"},
    ).json()
    assert client.get("/invoices", headers=manager).status_code == 200
    assert client.get("/invoices", headers=warehouse).status_code == 403
    assert client.post(f"/invoices/{invoice['id']}/issue", headers=accountant).status_code == 403
    assert client.post(f"/invoices/{invoice['id']}/issue", headers=sales).status_code == 200
    cancelled = client.post(
        f"/invoices/{invoice['id']}/cancel",
        headers=accountant,
        json={"reason": f"Test billing reversal {suffix}"},
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    listed = client.get(f"/invoices?search=TBC-{suffix}", headers=accountant).json()["items"]
    credit_note = next(item for item in listed if item["document_type"] == "credit_note")
    assert credit_note["reversed_invoice_id"] == invoice["id"]
    assert credit_note["status"] == "issued"
