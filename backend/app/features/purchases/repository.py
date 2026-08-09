from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.features.purchases.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
)
from app.features.suppliers.models import Supplier


def _order_options(statement):
    return statement.options(
        selectinload(PurchaseOrder.supplier),
        selectinload(PurchaseOrder.warehouse),
        selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.product),
        selectinload(PurchaseOrder.receipts).selectinload(GoodsReceipt.warehouse),
        selectinload(PurchaseOrder.receipts)
        .selectinload(GoodsReceipt.items)
        .selectinload(GoodsReceiptItem.product),
    )


def get_purchase_order(db: Session, purchase_order_id: int) -> PurchaseOrder | None:
    return cast(
        PurchaseOrder | None,
        db.scalar(
            _order_options(select(PurchaseOrder)).where(PurchaseOrder.id == purchase_order_id)
        ),
    )


def get_purchase_order_for_update(db: Session, purchase_order_id: int) -> PurchaseOrder | None:
    return cast(
        PurchaseOrder | None,
        db.scalar(
            _order_options(select(PurchaseOrder))
            .where(PurchaseOrder.id == purchase_order_id)
            .with_for_update()
        ),
    )


def _filters(statement, *, search, status, supplier_id, created_by):
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.join(PurchaseOrder.supplier).where(
            or_(
                func.lower(PurchaseOrder.number).like(term),
                func.lower(Supplier.name).like(term),
            )
        )
    if status is not None:
        statement = statement.where(PurchaseOrder.status == status)
    if supplier_id is not None:
        statement = statement.where(PurchaseOrder.supplier_id == supplier_id)
    if created_by is not None:
        statement = statement.where(PurchaseOrder.created_by == created_by)
    return statement


def list_purchase_orders(
    db: Session,
    *,
    offset: int,
    limit: int,
    search: str | None,
    status: str | None,
    supplier_id: int | None,
    created_by: int | None,
) -> list[PurchaseOrder]:
    statement = _filters(
        _order_options(select(PurchaseOrder)),
        search=search,
        status=status,
        supplier_id=supplier_id,
        created_by=created_by,
    )
    return list(
        db.scalars(
            statement.order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def count_purchase_orders(
    db: Session,
    *,
    search: str | None,
    status: str | None,
    supplier_id: int | None,
    created_by: int | None,
) -> int:
    statement = _filters(
        select(func.count(PurchaseOrder.id)),
        search=search,
        status=status,
        supplier_id=supplier_id,
        created_by=created_by,
    )
    return int(db.scalar(statement) or 0)


def get_goods_receipt(db: Session, receipt_id: int) -> GoodsReceipt | None:
    return cast(
        GoodsReceipt | None,
        db.scalar(
            select(GoodsReceipt)
            .options(
                selectinload(GoodsReceipt.warehouse),
                selectinload(GoodsReceipt.items).selectinload(GoodsReceiptItem.product),
            )
            .where(GoodsReceipt.id == receipt_id)
        ),
    )


def list_goods_receipts(db: Session, *, offset: int, limit: int) -> list[GoodsReceipt]:
    return list(
        db.scalars(
            select(GoodsReceipt)
            .options(
                selectinload(GoodsReceipt.warehouse),
                selectinload(GoodsReceipt.items).selectinload(GoodsReceiptItem.product),
            )
            .order_by(GoodsReceipt.received_at.desc(), GoodsReceipt.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def count_goods_receipts(db: Session) -> int:
    return int(db.scalar(select(func.count(GoodsReceipt.id))) or 0)
