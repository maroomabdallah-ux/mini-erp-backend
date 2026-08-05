from decimal import Decimal

from sqlalchemy.orm import Session

from app.features.audit.service import add_audit_log
from app.features.customers import repository
from app.features.customers.exceptions import CustomerDeactivationError, CustomerNotFoundError
from app.features.customers.models import Customer
from app.features.customers.schemas import CustomerCreate, CustomerUpdate


def _get(db: Session, customer_id: int) -> Customer:
    customer = repository.get_customer(db, customer_id)
    if customer is None:
        raise CustomerNotFoundError(customer_id)
    return customer


def _values(customer: Customer) -> dict:
    return {
        "code": customer.code,
        "name": customer.name,
        "contact_person": customer.contact_person,
        "email": customer.email,
        "phone": customer.phone,
        "address": customer.address,
        "city": customer.city,
        "tax_number": customer.tax_number,
        "credit_limit": f"{customer.credit_limit:.2f}",
        "is_active": customer.is_active,
    }


def list_customers(
    db: Session,
    *,
    page: int,
    size: int,
    search: str | None,
    is_active: bool | None,
    city: str | None,
) -> dict:
    return {
        "items": repository.list_customers(
            db,
            offset=(page - 1) * size,
            limit=size,
            search=search,
            is_active=is_active,
            city=city,
        ),
        "page": page,
        "size": size,
        "total": repository.count_customers(
            db, search=search, is_active=is_active, city=city
        ),
    }


def get_customer(db: Session, customer_id: int) -> Customer:
    return _get(db, customer_id)


def create_customer(
    db: Session, data: CustomerCreate, *, actor_id: int, ip_address: str | None
) -> Customer:
    customer = Customer(code="PENDING", **data.model_dump())
    db.add(customer)
    db.flush()
    customer.code = f"CUS-{customer.id:05d}"
    add_audit_log(
        db,
        user_id=actor_id,
        action="create",
        table_name="customers",
        record_id=customer.id,
        ip_address=ip_address,
        new_values=_values(customer),
    )
    db.commit()
    return _get(db, customer.id)


def update_customer(
    db: Session, customer_id: int, data: CustomerUpdate, *, actor_id: int, ip_address: str | None
) -> Customer:
    customer = _get(db, customer_id)
    old = _values(customer)
    for field in data.model_fields_set:
        value = getattr(data, field)
        if field == "credit_limit" and value is None:
            value = Decimal("0.00")
        setattr(customer, field, value)
    add_audit_log(
        db,
        user_id=actor_id,
        action="update",
        table_name="customers",
        record_id=customer.id,
        ip_address=ip_address,
        old_values=old,
        new_values=_values(customer),
    )
    db.commit()
    return _get(db, customer.id)


def deactivate_customer(
    db: Session, customer_id: int, *, actor_id: int, ip_address: str | None
) -> Customer:
    customer = _get(db, customer_id)
    if not customer.is_active:
        raise CustomerDeactivationError(f"Customer with id {customer_id} is already inactive.")
    customer.is_active = False
    add_audit_log(
        db,
        user_id=actor_id,
        action="deactivate",
        table_name="customers",
        record_id=customer.id,
        ip_address=ip_address,
        old_values={"is_active": True},
        new_values={"is_active": False},
    )
    db.commit()
    return _get(db, customer.id)
