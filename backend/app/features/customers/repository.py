from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.features.customers.models import Customer


def get_customer(db: Session, customer_id: int) -> Customer | None:
    return cast(Customer | None, db.get(Customer, customer_id))


def _filters(statement, *, search: str | None, is_active: bool | None, city: str | None):
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Customer.code).like(term),
                func.lower(Customer.name).like(term),
                func.lower(Customer.contact_person).like(term),
                func.lower(Customer.email).like(term),
                func.lower(Customer.phone).like(term),
                func.lower(Customer.tax_number).like(term),
            )
        )
    if is_active is not None:
        statement = statement.where(Customer.is_active.is_(is_active))
    if city:
        statement = statement.where(func.lower(Customer.city) == city.strip().lower())
    return statement


def list_customers(
    db: Session,
    *,
    offset: int,
    limit: int,
    search: str | None,
    is_active: bool | None,
    city: str | None,
) -> list[Customer]:
    statement = _filters(select(Customer), search=search, is_active=is_active, city=city)
    return list(db.scalars(statement.order_by(Customer.name).offset(offset).limit(limit)).all())


def count_customers(
    db: Session, *, search: str | None, is_active: bool | None, city: str | None
) -> int:
    statement = _filters(
        select(func.count(Customer.id)), search=search, is_active=is_active, city=city
    )
    return int(db.scalar(statement) or 0)


def list_cities(db: Session) -> list[str]:
    return list(
        db.scalars(
            select(Customer.city)
            .where(Customer.city.is_not(None))
            .distinct()
            .order_by(Customer.city)
        ).all()
    )
