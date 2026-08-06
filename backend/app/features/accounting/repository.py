from datetime import date
from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.features.accounting.models import Account, JournalEntry, JournalEntryLine, SupplierPayment


def get_account(db: Session, account_id: int) -> Account | None:
    return cast(Account | None, db.get(Account, account_id))


def get_account_by_code(db: Session, code: str) -> Account | None:
    return cast(Account | None, db.scalar(select(Account).where(Account.code == code)))


def list_accounts(db: Session, *, active_only: bool = False) -> list[Account]:
    statement = select(Account)
    if active_only:
        statement = statement.where(Account.is_active.is_(True))
    return list(db.scalars(statement.order_by(Account.code)).all())


def get_entry_by_source(db: Session, source_type: str, source_id: int) -> JournalEntry | None:
    return cast(
        JournalEntry | None,
        db.scalar(
            select(JournalEntry).where(
                JournalEntry.source_type == source_type, JournalEntry.source_id == source_id
            )
        ),
    )


def get_entry(db: Session, entry_id: int) -> JournalEntry | None:
    return cast(
        JournalEntry | None,
        db.scalar(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account))
            .where(JournalEntry.id == entry_id)
        ),
    )


def _entry_filters(
    statement,
    *,
    search: str | None,
    date_from: date | None,
    date_to: date | None,
    account_id: int | None,
    source_type: str | None,
):
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(JournalEntry.number).like(term),
                func.lower(JournalEntry.description).like(term),
            )
        )
    if date_from:
        statement = statement.where(JournalEntry.entry_date >= date_from)
    if date_to:
        statement = statement.where(JournalEntry.entry_date <= date_to)
    if source_type:
        statement = statement.where(JournalEntry.source_type == source_type)
    if account_id:
        statement = statement.where(
            JournalEntry.id.in_(
                select(JournalEntryLine.journal_entry_id).where(
                    JournalEntryLine.account_id == account_id
                )
            )
        )
    return statement


def list_entries(
    db: Session,
    *,
    offset: int,
    limit: int,
    search: str | None,
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: int | None = None,
    source_type: str | None = None,
) -> list[JournalEntry]:
    statement = select(JournalEntry).options(
        selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account)
    )
    statement = _entry_filters(
        statement,
        search=search,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        source_type=source_type,
    )
    return list(
        db.scalars(
            statement.order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def count_entries(
    db: Session,
    *,
    search: str | None,
    date_from: date | None = None,
    date_to: date | None = None,
    account_id: int | None = None,
    source_type: str | None = None,
) -> int:
    statement = _entry_filters(
        select(func.count(JournalEntry.id)),
        search=search,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        source_type=source_type,
    )
    return int(db.scalar(statement) or 0)


def list_supplier_payments(db: Session, supplier_id: int | None = None) -> list[SupplierPayment]:
    statement = select(SupplierPayment)
    if supplier_id:
        statement = statement.where(SupplierPayment.supplier_id == supplier_id)
    return list(
        db.scalars(
            statement.order_by(SupplierPayment.payment_date.desc(), SupplierPayment.id.desc())
        ).all()
    )
