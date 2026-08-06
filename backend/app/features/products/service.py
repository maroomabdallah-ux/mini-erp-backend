import csv
import io
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, BusinessRuleError, ConflictError
from app.features.audit.service import add_audit_log
from app.features.products import repository
from app.features.products.exceptions import (
    CategoryCycleError,
    CategoryNotFoundError,
    DeactivationError,
    DuplicateBarcodeError,
    DuplicateCategoryError,
    DuplicateSkuError,
    ProductNotFoundError,
)
from app.features.products.models import Category, Product
from app.features.products.schemas import (
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductImportError,
    ProductImportResponse,
    ProductUpdate,
)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        constraint = getattr(exc.orig, "diag", None)
        name = getattr(constraint, "constraint_name", "")
        if name == "uq_products_sku":
            raise ConflictError("The product SKU already exists.") from exc
        if name == "uq_products_barcode":
            raise ConflictError("The product barcode already exists.") from exc
        if name == "uq_categories_name":
            raise ConflictError("The category name already exists.") from exc
        raise


def _category_or_error(db: Session, category_id: int) -> Category:
    category = repository.get_category(db, category_id)
    if category is None:
        raise CategoryNotFoundError(category_id)
    return category


def _active_category_or_error(db: Session, category_id: int | None) -> Category | None:
    if category_id is None:
        return None
    category = _category_or_error(db, category_id)
    if not category.is_active:
        raise DeactivationError("An inactive category cannot be assigned to a product.")
    return category


def _product_or_error(db: Session, product_id: int) -> Product:
    product = repository.get_product(db, product_id)
    if product is None:
        raise ProductNotFoundError(product_id)
    return product


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def list_categories(db: Session, *, include_inactive: bool = False) -> list[Category]:
    return repository.list_categories(db, include_inactive=include_inactive)


def create_category(
    db: Session,
    data: CategoryCreate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Category:
    if repository.get_category_by_name(db, data.name):
        raise DuplicateCategoryError(data.name)
    _active_category_or_error(db, data.parent_id)
    category = Category(name=data.name, parent_id=data.parent_id)
    db.add(category)
    db.flush()
    add_audit_log(
        db,
        user_id=actor_id,
        action="create",
        table_name="categories",
        record_id=category.id,
        ip_address=ip_address,
        new_values={"name": category.name, "parent_id": category.parent_id},
    )
    _commit(db)
    return _category_or_error(db, category.id)


def _ensure_no_category_cycle(db: Session, category_id: int, parent: Category | None) -> None:
    current = parent
    while current is not None:
        if current.id == category_id:
            raise CategoryCycleError()
        current = repository.get_category(db, current.parent_id) if current.parent_id else None


def update_category(
    db: Session,
    category_id: int,
    data: CategoryUpdate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Category:
    category = _category_or_error(db, category_id)
    old_values = {"name": category.name, "parent_id": category.parent_id}
    if data.name is not None and data.name.lower() != category.name.lower():
        if repository.get_category_by_name(db, data.name):
            raise DuplicateCategoryError(data.name)
        category.name = data.name
    if "parent_id" in data.model_fields_set:
        parent = _active_category_or_error(db, data.parent_id)
        _ensure_no_category_cycle(db, category.id, parent)
        category.parent_id = parent.id if parent else None
    add_audit_log(
        db,
        user_id=actor_id,
        action="update",
        table_name="categories",
        record_id=category.id,
        ip_address=ip_address,
        old_values=old_values,
        new_values={"name": category.name, "parent_id": category.parent_id},
    )
    _commit(db)
    return _category_or_error(db, category.id)


def deactivate_category(
    db: Session, category_id: int, *, actor_id: int, ip_address: str | None
) -> Category:
    category = _category_or_error(db, category_id)
    if not category.is_active:
        raise DeactivationError(f"Category with id {category_id} is already inactive.")
    if repository.category_has_active_children(db, category_id):
        raise DeactivationError("Deactivate child categories first.")
    if repository.category_has_active_products(db, category_id):
        raise DeactivationError("A category with active products cannot be deactivated.")
    category.is_active = False
    add_audit_log(
        db,
        user_id=actor_id,
        action="deactivate",
        table_name="categories",
        record_id=category.id,
        ip_address=ip_address,
        old_values={"is_active": True},
        new_values={"is_active": False},
    )
    _commit(db)
    return _category_or_error(db, category.id)


def list_products(
    db: Session,
    *,
    page: int,
    size: int,
    search: str | None,
    category_id: int | None,
    is_active: bool | None,
) -> dict:
    return {
        "items": repository.list_products(
            db,
            offset=(page - 1) * size,
            limit=size,
            search=search,
            category_id=category_id,
            is_active=is_active,
        ),
        "page": page,
        "size": size,
        "total": repository.count_products(
            db, search=search, category_id=category_id, is_active=is_active
        ),
    }


def get_product(db: Session, product_id: int) -> Product:
    return _product_or_error(db, product_id)


def _ensure_product_values_available(
    db: Session,
    *,
    sku: str,
    barcode: str | None,
    current_product_id: int | None = None,
) -> None:
    sku_product = repository.get_product_by_sku(db, sku)
    if sku_product is not None and sku_product.id != current_product_id:
        raise DuplicateSkuError(sku)
    if barcode:
        barcode_product = repository.get_product_by_barcode(db, barcode)
        if barcode_product is not None and barcode_product.id != current_product_id:
            raise DuplicateBarcodeError(barcode)


def _product_values(product: Product) -> dict:
    return {
        "sku": product.sku,
        "name": product.name,
        "barcode": product.barcode,
        "category_id": product.category_id,
        "cost_price": _money(product.cost_price),
        "sale_price": _money(product.sale_price),
        "min_stock_level": _money(product.min_stock_level),
        "is_active": product.is_active,
    }


def create_product(
    db: Session,
    data: ProductCreate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Product:
    _ensure_product_values_available(db, sku=data.sku, barcode=data.barcode)
    _active_category_or_error(db, data.category_id)
    product = Product(
        sku=data.sku,
        name=data.name,
        barcode=data.barcode,
        category_id=data.category_id,
        cost_price=data.cost_price,
        sale_price=data.sale_price,
        min_stock_level=data.min_stock_level,
    )
    db.add(product)
    db.flush()
    add_audit_log(
        db,
        user_id=actor_id,
        action="create",
        table_name="products",
        record_id=product.id,
        ip_address=ip_address,
        new_values=_product_values(product),
    )
    _commit(db)
    return _product_or_error(db, product.id)


def update_product(
    db: Session,
    product_id: int,
    data: ProductUpdate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Product:
    product = _product_or_error(db, product_id)
    old_values = _product_values(product)
    next_sku = data.sku if data.sku is not None else product.sku
    next_barcode = data.barcode if "barcode" in data.model_fields_set else product.barcode
    _ensure_product_values_available(
        db, sku=next_sku, barcode=next_barcode, current_product_id=product.id
    )
    for field in ("sku", "name", "cost_price", "sale_price", "min_stock_level"):
        value = getattr(data, field)
        if value is not None:
            setattr(product, field, value)
    if "barcode" in data.model_fields_set:
        product.barcode = data.barcode
    if "category_id" in data.model_fields_set:
        _active_category_or_error(db, data.category_id)
        product.category_id = data.category_id
    add_audit_log(
        db,
        user_id=actor_id,
        action="update",
        table_name="products",
        record_id=product.id,
        ip_address=ip_address,
        old_values=old_values,
        new_values=_product_values(product),
    )
    _commit(db)
    return _product_or_error(db, product.id)


def deactivate_product(
    db: Session, product_id: int, *, actor_id: int, ip_address: str | None
) -> Product:
    product = _product_or_error(db, product_id)
    if not product.is_active:
        raise DeactivationError(f"Product with id {product_id} is already inactive.")
    product.is_active = False
    add_audit_log(
        db,
        user_id=actor_id,
        action="deactivate",
        table_name="products",
        record_id=product.id,
        ip_address=ip_address,
        old_values={"is_active": True},
        new_values={"is_active": False},
    )
    _commit(db)
    return _product_or_error(db, product.id)


def import_products(
    db: Session,
    content: bytes,
    *,
    actor_id: int,
    ip_address: str | None,
) -> ProductImportResponse:
    if len(content) > 5 * 1024 * 1024:
        raise BusinessRuleError("The CSV file cannot exceed 5 MB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise BusinessRuleError("The CSV file must be UTF-8 encoded.") from exc

    reader = csv.DictReader(io.StringIO(text))
    required = {"sku", "name"}
    if not reader.fieldnames or not required <= set(reader.fieldnames):
        raise BusinessRuleError("CSV headers must include sku and name.")

    allowed = {
        "sku",
        "name",
        "barcode",
        "category_id",
        "cost_price",
        "sale_price",
        "min_stock_level",
    }
    errors: list[ProductImportError] = []
    created_count = 0
    for row_number, raw_row in enumerate(reader, start=2):
        values = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in raw_row.items()
            if key in allowed
        }
        for optional in (
            "barcode",
            "category_id",
            "cost_price",
            "sale_price",
            "min_stock_level",
        ):
            if values.get(optional) == "":
                values.pop(optional, None)
        try:
            data = ProductCreate.model_validate(values)
            create_product(db, data, actor_id=actor_id, ip_address=ip_address)
            created_count += 1
        except ValidationError as exc:
            field_errors = {
                ".".join(str(part) for part in error["loc"]): error["msg"] for error in exc.errors()
            }
            errors.append(ProductImportError(row=row_number, field_errors=field_errors))
        except AppError as exc:
            errors.append(
                ProductImportError(
                    row=row_number,
                    field_errors=exc.field_errors or {"row": exc.detail},
                )
            )
    return ProductImportResponse(
        created_count=created_count,
        error_count=len(errors),
        errors=errors,
    )
