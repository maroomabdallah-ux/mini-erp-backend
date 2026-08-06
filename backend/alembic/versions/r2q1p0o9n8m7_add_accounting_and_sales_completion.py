"""Add accounting and complete sales billing.

Revision ID: r2q1p0o9n8m7
Revises: q1p0o9n8m7k6
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "r2q1p0o9n8m7"
down_revision: str | None = "q1p0o9n8m7k6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("sales_orders", "quotation_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("sales_orders", sa.Column("credit_warning", sa.String(500), nullable=True))
    op.alter_column("invoices", "sales_order_id", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "invoices",
        sa.Column("document_type", sa.String(20), nullable=False, server_default="invoice"),
    )
    op.add_column("invoices", sa.Column("reversed_invoice_id", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_invoices_document_type",
        "invoices",
        "document_type IN ('invoice','credit_note')",
    )
    op.create_foreign_key(
        "fk_invoices_reversed_invoice_id",
        "invoices",
        "invoices",
        ["reversed_invoice_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_invoices_document_type", "invoices", ["document_type"])
    op.create_index("ix_invoices_reversed_invoice_id", "invoices", ["reversed_invoice_id"])

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "type IN ('asset','liability','equity','revenue','expense')",
            name="ck_accounts_type",
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code", name="uq_accounts_code"),
    )
    op.create_index("ix_accounts_code", "accounts", ["code"])
    op.create_index("ix_accounts_name", "accounts", ["name"])
    op.create_index("ix_accounts_type", "accounts", ["type"])
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("number", name="uq_journal_entries_number"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_journal_source"),
    )
    for column in ("number", "entry_date", "source_type", "source_id"):
        op.create_index(f"ix_journal_entries_{column}", "journal_entries", [column])
    op.create_table(
        "journal_entry_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("journal_entry_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("memo", sa.String(255), nullable=True),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_lines_nonnegative"),
        sa.CheckConstraint(
            "(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)",
            name="ck_journal_lines_one_side",
        ),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_journal_entry_lines_journal_entry_id", "journal_entry_lines", ["journal_entry_id"])
    op.create_table(
        "supplier_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(30), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("reversed_by", sa.Integer(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_supplier_payments_amount_positive"),
        sa.CheckConstraint("status IN ('posted','reversed')", name="ck_supplier_payments_status"),
        sa.CheckConstraint("method IN ('cash','bank_transfer','card','cheque')", name="ck_supplier_payments_method"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("number", name="uq_supplier_payments_number"),
    )
    op.create_index("ix_supplier_payments_number", "supplier_payments", ["number"])
    op.create_index("ix_supplier_payments_payment_date", "supplier_payments", ["payment_date"])
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("supplier_payments")
    op.drop_table("journal_entry_lines")
    op.drop_table("journal_entries")
    op.drop_table("accounts")
    op.drop_index("ix_invoices_reversed_invoice_id", table_name="invoices")
    op.drop_index("ix_invoices_document_type", table_name="invoices")
    op.drop_constraint("fk_invoices_reversed_invoice_id", "invoices", type_="foreignkey")
    op.drop_constraint("ck_invoices_document_type", "invoices", type_="check")
    op.drop_column("invoices", "reversed_invoice_id")
    op.drop_column("invoices", "document_type")
    op.alter_column("invoices", "sales_order_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("sales_orders", "quotation_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("sales_orders", "credit_warning")
