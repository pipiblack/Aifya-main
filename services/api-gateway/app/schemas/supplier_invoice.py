"""Pydantic v2 schemas for supplier invoicing."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


# ── Supplier (extended) ──────────────────────────────────────────────────────


class SupplierExtCreate(BaseModel):
    """Schema for creating a supplier (extended with bank_account).

    The base ``SupplierCreate`` in ``schemas/inventory.py`` is preserved for
    backward compatibility — this variant adds the bank account field needed
    for supplier invoicing & payments.
    """

    name: str = Field(..., max_length=200)
    contact_person: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=500)
    kra_pin: str | None = Field(None, max_length=20)
    bank_account: str | None = Field(None, max_length=100)
    payment_terms: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=1000)


class SupplierUpdate(BaseModel):
    """Partial-update schema for a supplier."""

    name: str | None = Field(None, max_length=200)
    contact_person: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=500)
    kra_pin: str | None = Field(None, max_length=20)
    bank_account: str | None = Field(None, max_length=100)
    payment_terms: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=50)
    is_active: bool | None = None
    notes: str | None = Field(None, max_length=1000)


class SupplierExtResponse(BaseModel):
    """Supplier response with bank_account included."""

    id: uuid.UUID
    name: str
    supplier_code: str | None
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    kra_pin: str | None
    bank_account: str | None
    payment_terms: str | None
    category: str | None
    rating: int | None
    is_active: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SupplierExtListResponse(BaseModel):
    """Paginated supplier list response."""

    items: list[SupplierExtResponse]
    total: int
    page: int
    page_size: int


# ── Supplier Invoice ─────────────────────────────────────────────────────────


class SupplierInvoiceLineCreate(BaseModel):
    """Line item on a new supplier invoice."""

    description: str = Field(..., min_length=1, max_length=500)
    quantity: int = Field(default=1, ge=1)
    unit_price: int = Field(default=0, ge=0)  # KES cents
    account_code: str = Field(..., min_length=2, max_length=20)
    department_id: uuid.UUID | None = None

    @property
    def line_total(self) -> int:
        return self.quantity * self.unit_price


class SupplierInvoiceCreate(BaseModel):
    """Schema for creating a supplier invoice (always starts as draft)."""

    supplier_id: uuid.UUID
    invoice_number: str = Field(..., min_length=1, max_length=80)
    invoice_date: date
    due_date: date | None = None
    vat_amount: int = Field(default=0, ge=0)
    wht_amount: int = Field(default=0, ge=0)
    notes: str | None = Field(None, max_length=2000)
    attachment_url: str | None = Field(None, max_length=500)
    lines: list[SupplierInvoiceLineCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_amounts(self) -> SupplierInvoiceCreate:
        if self.due_date is not None and self.due_date < self.invoice_date:
            raise ValueError("due_date cannot be earlier than invoice_date")
        return self


class SupplierInvoiceUpdate(BaseModel):
    """Partial update for an unposted (draft) supplier invoice."""

    invoice_number: str | None = Field(None, min_length=1, max_length=80)
    invoice_date: date | None = None
    due_date: date | None = None
    vat_amount: int | None = Field(None, ge=0)
    wht_amount: int | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=2000)
    attachment_url: str | None = Field(None, max_length=500)


class SupplierInvoiceLineResponse(BaseModel):
    """Supplier invoice line response."""

    id: uuid.UUID
    description: str
    quantity: int
    unit_price: int
    line_total: int
    account_code: str
    department_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class SupplierInvoiceResponse(BaseModel):
    """Supplier invoice detail response."""

    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    invoice_number: str
    our_reference: str
    invoice_date: date
    due_date: date | None
    subtotal: int
    vat_amount: int
    wht_amount: int
    total: int
    paid_amount: int
    balance: int = 0
    status: str
    notes: str | None
    attachment_url: str | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    paid_at: datetime | None
    cancelled_at: datetime | None
    gl_transaction_id: uuid.UUID | None
    gl_payment_transaction_id: uuid.UUID | None
    lines: list[SupplierInvoiceLineResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class SupplierInvoiceListItem(BaseModel):
    """Supplier invoice in list view."""

    id: uuid.UUID
    our_reference: str
    invoice_number: str
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    invoice_date: date
    due_date: date | None
    total: int
    paid_amount: int
    balance: int = 0
    status: str

    model_config = {"from_attributes": True}


class SupplierInvoiceListResponse(BaseModel):
    """Paginated supplier invoice list response."""

    items: list[SupplierInvoiceListItem]
    total: int
    page: int
    page_size: int


class SupplierInvoicePaymentRequest(BaseModel):
    """Schema for recording a payment against an approved supplier invoice."""

    amount: int = Field(..., gt=0)  # KES cents
    payment_date: date | None = None
    payment_method: str = Field(default="bank", pattern=r"^(bank|cash|mpesa|cheque)$")
    reference: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=500)
