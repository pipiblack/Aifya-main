"""Supplier invoicing module.

Revision ID: 008
Revises: 007
Create Date: 2026-05-15

Adds supplier-invoicing tables (``supplier_invoices`` and
``supplier_invoice_lines``) and extends the existing ``suppliers`` table
with ``bank_account``. Supplier invoices are the AP counterpart to
patient (customer) invoices and post to the GL on approval.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def _audit_cols() -> list[sa.Column]:
    """Audit columns shared across multi-tenant tables."""
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", UUID(as_uuid=True)),
        sa.Column("updated_by", UUID(as_uuid=True)),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    ]


def upgrade() -> None:
    """Create supplier-invoicing tables and add bank_account to suppliers."""
    # Extend suppliers — additive, nullable, fully backward compatible
    op.add_column("suppliers", sa.Column("bank_account", sa.String(100), nullable=True))

    # ── supplier_invoices ──────────────────────────────────────────────
    op.create_table(
        "supplier_invoices",
        *_audit_cols(),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("invoice_number", sa.String(80), nullable=False),
        sa.Column("our_reference", sa.String(50), nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("subtotal", sa.Integer, nullable=False, server_default="0"),
        sa.Column("vat_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("wht_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("attachment_url", sa.String(500), nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gl_transaction_id", UUID(as_uuid=True), nullable=True),
        sa.Column("gl_payment_transaction_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_supplier_invoices_facility_status",
        "supplier_invoices",
        ["facility_id", "status"],
    )
    op.create_index(
        "ix_supplier_invoices_supplier",
        "supplier_invoices",
        ["facility_id", "supplier_id"],
    )
    op.create_index(
        "ix_supplier_invoices_due",
        "supplier_invoices",
        ["facility_id", "due_date"],
    )

    # ── supplier_invoice_lines ────────────────────────────────────────
    op.create_table(
        "supplier_invoice_lines",
        *_audit_cols(),
        sa.Column(
            "supplier_invoice_id",
            UUID(as_uuid=True),
            sa.ForeignKey("supplier_invoices.id"),
            nullable=False,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Integer, nullable=False, server_default="0"),
        sa.Column("line_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("account_code", sa.String(20), nullable=False),
        sa.Column("department_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_supplier_invoice_lines_invoice",
        "supplier_invoice_lines",
        ["facility_id", "supplier_invoice_id"],
    )


def downgrade() -> None:
    """Drop supplier-invoicing tables and the suppliers.bank_account column."""
    op.drop_index("ix_supplier_invoice_lines_invoice", table_name="supplier_invoice_lines")
    op.drop_table("supplier_invoice_lines")
    op.drop_index("ix_supplier_invoices_due", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_supplier", table_name="supplier_invoices")
    op.drop_index("ix_supplier_invoices_facility_status", table_name="supplier_invoices")
    op.drop_table("supplier_invoices")
    op.drop_column("suppliers", "bank_account")
