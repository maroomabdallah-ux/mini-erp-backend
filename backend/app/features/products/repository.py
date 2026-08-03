from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.features.products.models import Category, Product


def get_category(db: Session, category_id: int) -> Category | None:
    return cast(Category | None, db.get(Category, category_id))


def get_category_by_name(db: Session, name: str) -> Category | None:
    return cast(
        Category | None,
        db.scalar(select(Category).where(func.lower(Category.name) == name.lower())),
    )


def list_categories(db: Session, *, include_inactive: bool = False) -> list[Category]:
    statement = select(Category)
    if not include_inactive:
        statement = statement.where(Category.is_active.is_(True))
    return list(db.scalars(statement.order_by(Category.name)).all())


def category_has_active_children(db: Session, category_id: int) -> bool:
    return bool(
        db.scalar(
            select(func.count(Category.id)).where(
                Category.parent_id == category_id, Category.is_active.is_(True)
            )
        )
    )


def category_has_active_products(db: Session, category_id: int) -> bool:
    return bool(
        db.scalar(
            select(func.count(Product.id)).where(
                Product.category_id == category_id, Product.is_active.is_(True)
            )
        )
    )


def get_product(db: Session, product_id: int) -> Product | None:
    return cast(
        Product | None,
        db.scalar(
            select(Product)
            .options(selectinload(Product.category))
            .where(Product.id == product_id)
        ),
    )


def get_product_by_sku(db: Session, sku: str) -> Product | None:
    return cast(Product | None, db.scalar(select(Product).where(Product.sku == sku)))


def get_product_by_barcode(db: Session, barcode: str) -> Product | None:
    return cast(
        Product | None, db.scalar(select(Product).where(Product.barcode == barcode))
    )


def _product_filters(statement, *, search, category_id, is_active):
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(Product.name).like(term),
                func.lower(Product.sku).like(term),
                func.lower(Product.barcode).like(term),
            )
        )
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    if is_active is not None:
        statement = statement.where(Product.is_active.is_(is_active))
    return statement


def list_products(
    db: Session,
    *,
    offset: int,
    limit: int,
    search: str | None,
    category_id: int | None,
    is_active: bool | None,
) -> list[Product]:
    statement = _product_filters(
        select(Product).options(selectinload(Product.category)),
        search=search,
        category_id=category_id,
        is_active=is_active,
    )
    return list(
        db.scalars(statement.order_by(Product.name).offset(offset).limit(limit)).all()
    )


def count_products(
    db: Session,
    *,
    search: str | None,
    category_id: int | None,
    is_active: bool | None,
) -> int:
    statement = _product_filters(
        select(func.count(Product.id)),
        search=search,
        category_id=category_id,
        is_active=is_active,
    )
    return int(db.scalar(statement) or 0)
