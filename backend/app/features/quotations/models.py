from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
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


class Quotation(Base):
    __tablename__ = "quotations"
    __table_args__ = (
        UniqueConstraint("number", name="uq_quotations_number"),
        CheckConstraint(
            "status IN ('draft','sent','accepted','rejected','expired')",
            name="ck_quotations_status",
        ),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_quotations_discount_percent",
        ),
        CheckConstraint(
            "tax_percent >= 0 AND tax_percent <= 100", name="ck_quotations_tax_percent"
        ),
        CheckConstraint("total_amount >= 0", name="ck_quotations_total_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    valid_until: Mapped[date] = mapped_column(Date, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), server_default="0"
    )
    tax_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), server_default="0"
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default="0"
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default="0"
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default="0"
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default="0"
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    customer: Mapped[Customer] = relationship()
    items: Mapped[list["QuotationItem"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan", order_by="QuotationItem.id"
    )


class QuotationItem(Base):
    __tablename__ = "quotation_items"
    __table_args__ = (
        UniqueConstraint("quotation_id", "product_id", name="uq_quotation_product"),
        CheckConstraint("quantity > 0", name="ck_quotation_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_quotation_items_price_nonnegative"),
        CheckConstraint("line_total >= 0", name="ck_quotation_items_total_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    quotation: Mapped[Quotation] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
