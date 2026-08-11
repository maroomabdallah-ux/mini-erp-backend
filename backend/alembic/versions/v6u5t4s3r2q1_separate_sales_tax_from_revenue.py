"""Separate sales tax from revenue in posted invoice journals.

Revision ID: v6u5t4s3r2q1
Revises: u5t4s3r2q1p0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v6u5t4s3r2q1"
down_revision: str | None = "u5t4s3r2q1p0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO accounts (code, name, type, is_active, is_system)
        SELECT '2100', 'Sales Tax Payable', 'liability', true, true
        WHERE NOT EXISTS (SELECT 1 FROM accounts WHERE code = '2100')
        """
    )
    op.execute(
        """
        UPDATE journal_entry_lines AS revenue_line
        SET credit = revenue_line.credit - invoices.tax_amount
        FROM journal_entries, invoices, accounts
        WHERE revenue_line.journal_entry_id = journal_entries.id
          AND revenue_line.account_id = accounts.id
          AND accounts.code = '4000'
          AND journal_entries.source_type = 'sales_invoice'
          AND journal_entries.source_id = invoices.id
          AND invoices.tax_amount > 0
          AND revenue_line.credit >= invoices.tax_amount
          AND NOT EXISTS (
              SELECT 1
              FROM journal_entry_lines tax_line
              JOIN accounts tax_account ON tax_account.id = tax_line.account_id
              WHERE tax_line.journal_entry_id = journal_entries.id
                AND tax_account.code = '2100'
          )
        """
    )
    op.execute(
        """
        INSERT INTO journal_entry_lines
            (journal_entry_id, account_id, debit, credit, memo)
        SELECT journal_entries.id, tax_account.id, 0, invoices.tax_amount, invoices.number
        FROM journal_entries
        JOIN invoices ON invoices.id = journal_entries.source_id
        CROSS JOIN accounts AS tax_account
        WHERE journal_entries.source_type = 'sales_invoice'
          AND tax_account.code = '2100'
          AND invoices.tax_amount > 0
          AND NOT EXISTS (
              SELECT 1
              FROM journal_entry_lines tax_line
              WHERE tax_line.journal_entry_id = journal_entries.id
                AND tax_line.account_id = tax_account.id
          )
        """
    )
    op.execute(
        """
        UPDATE journal_entry_lines AS revenue_line
        SET debit = revenue_line.debit - invoices.tax_amount
        FROM journal_entries, invoices, accounts
        WHERE revenue_line.journal_entry_id = journal_entries.id
          AND revenue_line.account_id = accounts.id
          AND accounts.code = '4000'
          AND journal_entries.source_type = 'credit_note'
          AND journal_entries.source_id = invoices.id
          AND invoices.tax_amount > 0
          AND revenue_line.debit >= invoices.tax_amount
          AND NOT EXISTS (
              SELECT 1
              FROM journal_entry_lines tax_line
              JOIN accounts tax_account ON tax_account.id = tax_line.account_id
              WHERE tax_line.journal_entry_id = journal_entries.id
                AND tax_account.code = '2100'
          )
        """
    )
    op.execute(
        """
        INSERT INTO journal_entry_lines
            (journal_entry_id, account_id, debit, credit, memo)
        SELECT journal_entries.id, tax_account.id, invoices.tax_amount, 0, invoices.number
        FROM journal_entries
        JOIN invoices ON invoices.id = journal_entries.source_id
        CROSS JOIN accounts AS tax_account
        WHERE journal_entries.source_type = 'credit_note'
          AND tax_account.code = '2100'
          AND invoices.tax_amount > 0
          AND NOT EXISTS (
              SELECT 1
              FROM journal_entry_lines tax_line
              WHERE tax_line.journal_entry_id = journal_entries.id
                AND tax_line.account_id = tax_account.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE journal_entry_lines AS revenue_line
        SET credit = revenue_line.credit + tax_line.credit
        FROM journal_entries, journal_entry_lines AS tax_line, accounts AS revenue_account,
             accounts AS tax_account
        WHERE revenue_line.journal_entry_id = journal_entries.id
          AND revenue_line.account_id = revenue_account.id
          AND revenue_account.code = '4000'
          AND tax_line.journal_entry_id = journal_entries.id
          AND tax_line.account_id = tax_account.id
          AND tax_account.code = '2100'
          AND journal_entries.source_type = 'sales_invoice'
        """
    )
    op.execute(
        """
        UPDATE journal_entry_lines AS revenue_line
        SET debit = revenue_line.debit + tax_line.debit
        FROM journal_entries, journal_entry_lines AS tax_line, accounts AS revenue_account,
             accounts AS tax_account
        WHERE revenue_line.journal_entry_id = journal_entries.id
          AND revenue_line.account_id = revenue_account.id
          AND revenue_account.code = '4000'
          AND tax_line.journal_entry_id = journal_entries.id
          AND tax_line.account_id = tax_account.id
          AND tax_account.code = '2100'
          AND journal_entries.source_type = 'credit_note'
        """
    )
    op.execute(
        """
        DELETE FROM journal_entry_lines
        WHERE account_id = (SELECT id FROM accounts WHERE code = '2100')
          AND journal_entry_id IN (
              SELECT id FROM journal_entries
              WHERE source_type IN ('sales_invoice', 'credit_note')
          )
        """
    )
    op.execute("DELETE FROM accounts WHERE code = '2100' AND is_system = true")

