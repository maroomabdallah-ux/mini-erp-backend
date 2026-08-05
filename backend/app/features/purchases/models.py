from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("number", name="uq_purchase_orders_number"),
        CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', "
            "'rejected', 'cancelled', 'received')",
            name="ck_purchase_orders_status",
        ),
        CheckConstraint("total_amount >= 0", name="ck_purchase_orders_total_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), index=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default="0"
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    supplier = relationship("Supplier")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderItem.id",
    )
    receipt: Mapped["GoodsReceipt | None"] = relationship(
        back_populates="purchase_order", uselist=False
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "product_id", name="uq_purchase_order_product"),
        CheckConstraint("quantity > 0", name="ck_purchase_order_items_quantity_positive"),
        CheckConstraint("unit_cost >= 0", name="ck_purchase_order_items_cost_nonnegative"),
        CheckConstraint("line_total >= 0", name="ck_purchase_order_items_total_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")
    product = relationship("Product")


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    __table_args__ = (
        UniqueConstraint("number", name="uq_goods_receipts_number"),
        UniqueConstraint(
            "purchase_order_id", name="uq_goods_receipts_purchase_order_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), index=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"), index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    received_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="receipt")
    warehouse = relationship("Warehouse")
    items: Mapped[list["GoodsReceiptItem"]] = relationship(
        back_populates="goods_receipt", cascade="all, delete-orphan"
    )


class GoodsReceiptItem(Base):
    __tablename__ = "goods_receipt_items"
    __table_args__ = (
        UniqueConstraint("goods_receipt_id", "product_id", name="uq_goods_receipt_product"),
        CheckConstraint("quantity > 0", name="ck_goods_receipt_items_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    goods_receipt_id: Mapped[int] = mapped_column(
        ForeignKey("goods_receipts.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)

    goods_receipt: Mapped[GoodsReceipt] = relationship(back_populates="items")
    product = relationship("Product")
