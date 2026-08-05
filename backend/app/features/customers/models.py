from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("credit_limit >= 0", name="ck_customers_credit_limit_nonnegative"),
        UniqueConstraint("code", name="uq_customers_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    contact_person: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(30), index=True)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100), index=True)
    tax_number: Mapped[str | None] = mapped_column(String(100), index=True)
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
