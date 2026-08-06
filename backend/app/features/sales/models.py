from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

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
from app.features.customers.models import Customer
from app.features.products.models import Product
from app.features.quotations.models import Quotation
from app.features.warehouses.models import Warehouse

if TYPE_CHECKING:
    from app.features.billing.models import Invoice


class SalesOrder(Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint("number", name="uq_sales_orders_number"),
        UniqueConstraint("quotation_id", name="uq_sales_orders_quotation_id"),
        CheckConstraint(
            "status IN ('draft','confirmed','delivered','cancelled')", name="ck_sales_orders_status"
        ),
        CheckConstraint("total_amount >= 0", name="ck_sales_orders_total_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), index=True)
    quotation_id: Mapped[int | None] = mapped_column(
        ForeignKey("quotations.id", ondelete="RESTRICT"), index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    warehouse_id: Mapped[int | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    credit_warning: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    quotation: Mapped[Quotation | None] = relationship(back_populates="sales_order")
    customer: Mapped[Customer] = relationship()
    warehouse: Mapped[Warehouse | None] = relationship()
    items: Mapped[list["SalesOrderItem"]] = relationship(
        back_populates="sales_order", cascade="all, delete-orphan", order_by="SalesOrderItem.id"
    )
    delivery: Mapped["SalesDelivery | None"] = relationship(
        back_populates="sales_order", uselist=False
    )
    invoice: Mapped["Invoice | None"] = relationship(back_populates="sales_order", uselist=False)


class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"
    __table_args__ = (
        UniqueConstraint("sales_order_id", "product_id", name="uq_sales_order_product"),
        CheckConstraint("quantity > 0", name="ck_sales_order_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_sales_order_items_price_nonnegative"),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_sales_order_items_discount_percent",
        ),
        CheckConstraint("line_total >= 0", name="ck_sales_order_items_total_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    sales_order_id: Mapped[int] = mapped_column(
        ForeignKey("sales_orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), server_default="0"
    )
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    sales_order: Mapped[SalesOrder] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class SalesDelivery(Base):
    __tablename__ = "sales_deliveries"
    __table_args__ = (
        UniqueConstraint("number", name="uq_sales_deliveries_number"),
        UniqueConstraint("sales_order_id", name="uq_sales_deliveries_order_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), index=True)
    sales_order_id: Mapped[int] = mapped_column(
        ForeignKey("sales_orders.id", ondelete="RESTRICT"), index=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    delivered_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    sales_order: Mapped[SalesOrder] = relationship(back_populates="delivery")
    warehouse: Mapped[Warehouse] = relationship()
    items: Mapped[list["SalesDeliveryItem"]] = relationship(
        cascade="all, delete-orphan", order_by="SalesDeliveryItem.id"
    )


class SalesDeliveryItem(Base):
    __tablename__ = "sales_delivery_items"
    __table_args__ = (
        UniqueConstraint("sales_delivery_id", "product_id", name="uq_sales_delivery_product"),
        CheckConstraint("quantity > 0", name="ck_sales_delivery_items_quantity_positive"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    sales_delivery_id: Mapped[int] = mapped_column(
        ForeignKey("sales_deliveries.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    product: Mapped[Product] = relationship()
