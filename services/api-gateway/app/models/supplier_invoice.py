"""
Supplier Invoicing models.

Supplier (AP) invoices are distinct from customer (patient) invoices.
A supplier invoice is received from a vendor for goods or services delivered
to the facility and posts to the GL as AP / VAT Input / Expense.

The ``Supplier`` model itself lives in ``app.models.inventory`` so it can be
reused by purchase orders and supplier invoicing without duplication.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class SupplierInvoice(AuditMixin, Base):
    """Invoice received from a supplier (Accounts Payable).

    All monetary amounts stored in KES cents (integer).
    Status flow: draft → received → approved → paid (terminal) or cancelled.
    """

    __tablename__ = "supplier_invoices"
    __table_args__ = (
        Index("ix_supplier_invoices_facility_status", "facility_id", "status"),
        Index("ix_supplier_invoices_supplier", "facility_id", "supplier_id"),
        Index("ix_supplier_invoices_due", "facility_id", "due_date"),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False
    )
    # Supplier-supplied invoice reference (their number)
    invoice_number: Mapped[str] = mapped_column(String(80), nullable=False)
    # System-generated reference (SI-YYYYMMDD-XXXX)
    our_reference: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)

    # Monetary fields — KES cents
    subtotal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vat_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wht_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    paid_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft | received | approved | paid | cancelled
    notes: Mapped[str | None] = mapped_column(Text)
    attachment_url: Mapped[str | None] = mapped_column(String(500))

    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # GL link — populated when ``approve`` posts the AP entry
    gl_transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # GL link — populated when ``pay`` posts the bank-disbursement entry
    gl_payment_transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class SupplierInvoiceLine(AuditMixin, Base):
    """Line item on a supplier invoice.

    ``account_code`` identifies which GL expense account to debit
    (e.g. 5010 Cost of Goods Sold, 5030 Operating Expenses).
    """

    __tablename__ = "supplier_invoice_lines"
    __table_args__ = (
        Index("ix_supplier_invoice_lines_invoice", "facility_id", "supplier_invoice_id"),
    )

    supplier_invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_invoices.id"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # KES cents
    line_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # KES cents
    account_code: Mapped[str] = mapped_column(String(20), nullable=False)  # GL expense account
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


__all__ = ["SupplierInvoice", "SupplierInvoiceLine"]
