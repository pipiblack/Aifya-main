"""Service layer for supplier invoicing.

Handles supplier CRUD (over the existing ``suppliers`` table) and the full
supplier invoice lifecycle: create draft → approve (posts AP entries to the
GL) → pay (posts bank disbursement) or cancel.

GL account codes follow the default Chart of Accounts seeded for each
facility in ``services/finance/seed_data.py``:

  * 2010 — Accounts Payable - Suppliers      (CR on approval, DR on payment)
  * 2110 — VAT Input (Receivable)            (DR on approval if VAT > 0)
  * 2300 — Withholding Tax Payable           (CR on approval if WHT > 0)
  * 1020 — Bank Account                       (CR on payment)

The audit spec mentions different codes (5007/2001/1002/2031); we map those
intents onto the codes the seeded CoA actually contains. The line-level
``account_code`` (5xxx) is what the user picks per expense line.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.models.inventory import Supplier
from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceLine
from app.schemas.supplier_invoice import (
    SupplierExtCreate,
    SupplierInvoiceCreate,
    SupplierInvoiceLineResponse,
    SupplierInvoicePaymentRequest,
    SupplierInvoiceResponse,
    SupplierInvoiceUpdate,
    SupplierUpdate,
)
from app.services.finance import post_compound_transaction

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# GL account codes used by the AP workflow (must match seeded CoA)
AP_ACCOUNT = "2010"  # Accounts Payable - Suppliers
VAT_INPUT_ACCOUNT = "2110"  # VAT Input (Receivable)
WHT_ACCOUNT = "2300"  # Withholding Tax Payable
BANK_ACCOUNT = "1020"  # Bank Account


class SupplierInvoiceError(Exception):
    """Generic supplier-invoice domain error."""


class SupplierInvoiceService:
    """Service for supplier and supplier-invoice operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Supplier CRUD ─────────────────────────────────────────────────────

    async def list_suppliers(
        self,
        facility_id: uuid.UUID,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Supplier], int]:
        """List active suppliers (paginated, optional name search).

        @param facility_id: Facility scope
        @param search: Optional case-insensitive name substring
        @param page: 1-indexed page
        @param page_size: Items per page
        @returns Tuple of (items, total)
        """
        base = select(Supplier).where(
            Supplier.facility_id == facility_id,
            Supplier.is_deleted == False,  # noqa: E712
        )
        if search:
            base = base.where(Supplier.name.ilike(f"%{search}%"))

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        items_q = base.order_by(Supplier.name.asc()).limit(page_size).offset((page - 1) * page_size)
        items = list((await self.db.execute(items_q)).scalars().all())
        return items, int(total)

    async def get_supplier(
        self, supplier_id: uuid.UUID, facility_id: uuid.UUID
    ) -> Supplier | None:
        """Fetch a single supplier scoped to facility."""
        result = await self.db.execute(
            select(Supplier).where(
                Supplier.id == supplier_id,
                Supplier.facility_id == facility_id,
                Supplier.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def create_supplier(
        self,
        data: SupplierExtCreate,
        facility_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> Supplier:
        """Create a new supplier."""
        # auto-generate supplier_code: SUP-XXXXXX
        code = f"SUP-{uuid.uuid4().hex[:6].upper()}"
        supplier = Supplier(
            facility_id=facility_id,
            name=data.name,
            supplier_code=code,
            contact_person=data.contact_person,
            phone=data.phone,
            email=data.email,
            address=data.address,
            kra_pin=data.kra_pin,
            bank_account=data.bank_account,
            payment_terms=data.payment_terms,
            category=data.category,
            notes=data.notes,
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        self.db.add(supplier)
        await self.db.flush()
        return supplier

    async def update_supplier(
        self,
        supplier_id: uuid.UUID,
        data: SupplierUpdate,
        facility_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> Supplier | None:
        """Patch supplier fields."""
        supplier = await self.get_supplier(supplier_id, facility_id)
        if supplier is None:
            return None

        patch = data.model_dump(exclude_unset=True)
        for k, v in patch.items():
            setattr(supplier, k, v)
        supplier.updated_by = user_id
        await self.db.flush()
        return supplier

    # ── Invoice helpers ───────────────────────────────────────────────────

    @staticmethod
    def _generate_reference() -> str:
        """Produce a unique SI reference (SI-YYYYMMDD-XXXX)."""
        today = datetime.utcnow().strftime("%Y%m%d")
        return f"SI-{today}-{uuid.uuid4().hex[:6].upper()}"

    @staticmethod
    def _to_response(
        invoice: SupplierInvoice,
        lines: list[SupplierInvoiceLine],
        supplier_name: str | None,
    ) -> SupplierInvoiceResponse:
        return SupplierInvoiceResponse(
            id=invoice.id,
            supplier_id=invoice.supplier_id,
            supplier_name=supplier_name,
            invoice_number=invoice.invoice_number,
            our_reference=invoice.our_reference,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            subtotal=invoice.subtotal,
            vat_amount=invoice.vat_amount,
            wht_amount=invoice.wht_amount,
            total=invoice.total,
            paid_amount=invoice.paid_amount,
            balance=max(0, invoice.total - invoice.paid_amount),
            status=invoice.status,
            notes=invoice.notes,
            attachment_url=invoice.attachment_url,
            approved_by=invoice.approved_by,
            approved_at=invoice.approved_at,
            paid_at=invoice.paid_at,
            cancelled_at=invoice.cancelled_at,
            gl_transaction_id=invoice.gl_transaction_id,
            gl_payment_transaction_id=invoice.gl_payment_transaction_id,
            lines=[SupplierInvoiceLineResponse.model_validate(line) for line in lines],
            created_at=invoice.created_at,
        )

    # ── Supplier-invoice CRUD ─────────────────────────────────────────────

    async def list_invoices(
        self,
        facility_id: uuid.UUID,
        status_filter: str | None = None,
        supplier_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """List supplier invoices with supplier_name joined in."""
        base = (
            select(SupplierInvoice, Supplier.name.label("supplier_name"))
            .join(Supplier, SupplierInvoice.supplier_id == Supplier.id)
            .where(
                SupplierInvoice.facility_id == facility_id,
                SupplierInvoice.is_deleted == False,  # noqa: E712
            )
        )
        if status_filter:
            base = base.where(SupplierInvoice.status == status_filter)
        if supplier_id is not None:
            base = base.where(SupplierInvoice.supplier_id == supplier_id)

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        items_q = (
            base.order_by(SupplierInvoice.invoice_date.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = (await self.db.execute(items_q)).all()
        items: list[dict] = []
        for invoice, supplier_name in rows:
            items.append(
                {
                    "id": invoice.id,
                    "our_reference": invoice.our_reference,
                    "invoice_number": invoice.invoice_number,
                    "supplier_id": invoice.supplier_id,
                    "supplier_name": supplier_name,
                    "invoice_date": invoice.invoice_date,
                    "due_date": invoice.due_date,
                    "total": invoice.total,
                    "paid_amount": invoice.paid_amount,
                    "balance": max(0, invoice.total - invoice.paid_amount),
                    "status": invoice.status,
                }
            )
        return items, int(total)

    async def create_invoice(
        self,
        data: SupplierInvoiceCreate,
        facility_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> SupplierInvoiceResponse:
        """Create a draft supplier invoice with line items."""
        # Validate the supplier exists for this facility
        supplier = await self.get_supplier(data.supplier_id, facility_id)
        if supplier is None:
            raise SupplierInvoiceError("Supplier not found for this facility")

        subtotal = sum(line.quantity * line.unit_price for line in data.lines)
        total = subtotal + data.vat_amount - data.wht_amount

        invoice = SupplierInvoice(
            facility_id=facility_id,
            supplier_id=data.supplier_id,
            invoice_number=data.invoice_number,
            our_reference=self._generate_reference(),
            invoice_date=data.invoice_date,
            due_date=data.due_date,
            subtotal=subtotal,
            vat_amount=data.vat_amount,
            wht_amount=data.wht_amount,
            total=total,
            status="draft",
            notes=data.notes,
            attachment_url=data.attachment_url,
            created_by=user_id,
            updated_by=user_id,
        )
        self.db.add(invoice)
        await self.db.flush()

        line_rows: list[SupplierInvoiceLine] = []
        for line in data.lines:
            line_row = SupplierInvoiceLine(
                facility_id=facility_id,
                supplier_invoice_id=invoice.id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.quantity * line.unit_price,
                account_code=line.account_code,
                department_id=line.department_id,
                created_by=user_id,
                updated_by=user_id,
            )
            self.db.add(line_row)
            line_rows.append(line_row)

        await self.db.flush()
        return self._to_response(invoice, line_rows, supplier.name)

    async def get_invoice(
        self, invoice_id: uuid.UUID, facility_id: uuid.UUID
    ) -> SupplierInvoiceResponse | None:
        """Fetch a supplier invoice with its lines."""
        result = await self.db.execute(
            select(SupplierInvoice).where(
                SupplierInvoice.id == invoice_id,
                SupplierInvoice.facility_id == facility_id,
                SupplierInvoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            return None

        lines_result = await self.db.execute(
            select(SupplierInvoiceLine).where(
                SupplierInvoiceLine.supplier_invoice_id == invoice.id,
                SupplierInvoiceLine.facility_id == facility_id,
                SupplierInvoiceLine.is_deleted == False,  # noqa: E712
            )
        )
        lines = list(lines_result.scalars().all())

        supplier = await self.get_supplier(invoice.supplier_id, facility_id)
        supplier_name = supplier.name if supplier else None
        return self._to_response(invoice, lines, supplier_name)

    async def update_invoice(
        self,
        invoice_id: uuid.UUID,
        data: SupplierInvoiceUpdate,
        facility_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> SupplierInvoiceResponse | None:
        """Patch a draft supplier invoice (only draft status mutable)."""
        result = await self.db.execute(
            select(SupplierInvoice).where(
                SupplierInvoice.id == invoice_id,
                SupplierInvoice.facility_id == facility_id,
                SupplierInvoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            return None
        if invoice.status != "draft":
            raise SupplierInvoiceError(
                f"Cannot edit supplier invoice in status '{invoice.status}'"
            )

        patch = data.model_dump(exclude_unset=True)
        for k, v in patch.items():
            setattr(invoice, k, v)
        # Recompute total in case VAT/WHT changed
        invoice.total = invoice.subtotal + invoice.vat_amount - invoice.wht_amount
        invoice.updated_by = user_id
        await self.db.flush()

        return await self.get_invoice(invoice_id, facility_id)

    # ── Approve / Pay / Cancel ───────────────────────────────────────────

    async def approve_invoice(
        self,
        invoice_id: uuid.UUID,
        facility_id: uuid.UUID,
        user_id: uuid.UUID | None,
        idempotency_key: str | None = None,
    ) -> SupplierInvoiceResponse:
        """Approve a supplier invoice and post it to the GL.

        Posting (KES cents converted to Decimal):
          * DR Expense account(s) for each line (per ``account_code``)
          * DR VAT Input (2110) — if vat_amount > 0
          * CR Withholding Tax Payable (2300) — if wht_amount > 0
          * CR Accounts Payable (2010) — for the net amount (total - wht_amount)
            since WHT is withheld from the supplier and remitted to KRA, so
            the actual payable is reduced by the WHT.
        """
        result = await self.db.execute(
            select(SupplierInvoice).where(
                SupplierInvoice.id == invoice_id,
                SupplierInvoice.facility_id == facility_id,
                SupplierInvoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            raise SupplierInvoiceError("Supplier invoice not found")
        if invoice.status not in ("draft", "received"):
            raise SupplierInvoiceError(
                f"Cannot approve invoice in status '{invoice.status}'"
            )

        lines_result = await self.db.execute(
            select(SupplierInvoiceLine).where(
                SupplierInvoiceLine.supplier_invoice_id == invoice.id,
                SupplierInvoiceLine.facility_id == facility_id,
                SupplierInvoiceLine.is_deleted == False,  # noqa: E712
            )
        )
        lines = list(lines_result.scalars().all())
        if not lines:
            raise SupplierInvoiceError("Cannot approve an invoice with no lines")

        # Build GL entries — convert KES cents to KES decimal
        entries: list[dict] = []
        cents_to_decimal = lambda c: (Decimal(c) / Decimal(100))  # noqa: E731

        for line in lines:
            entries.append(
                {
                    "account_code": line.account_code,
                    "debit": cents_to_decimal(line.line_total),
                    "credit": Decimal(0),
                    "department_id": line.department_id,
                }
            )
        if invoice.vat_amount > 0:
            entries.append(
                {
                    "account_code": VAT_INPUT_ACCOUNT,
                    "debit": cents_to_decimal(invoice.vat_amount),
                    "credit": Decimal(0),
                }
            )
        if invoice.wht_amount > 0:
            entries.append(
                {
                    "account_code": WHT_ACCOUNT,
                    "debit": Decimal(0),
                    "credit": cents_to_decimal(invoice.wht_amount),
                }
            )
        # AP receives net of WHT (since WHT is remitted separately to KRA)
        ap_net = invoice.total  # = subtotal + vat - wht  (already accounts for it)
        entries.append(
            {
                "account_code": AP_ACCOUNT,
                "debit": Decimal(0),
                "credit": cents_to_decimal(ap_net),
            }
        )

        txn = await post_compound_transaction(
            db=self.db,
            facility_id=facility_id,
            entries=entries,
            metadata={
                "date": invoice.invoice_date,
                "event_type": "supplier_invoice_approved",
                "reference_type": "supplier_invoice",
                "reference_id": invoice.id,
                "description": f"Supplier invoice {invoice.our_reference} approved",
            },
            idempotency_key=idempotency_key,
            user_id=user_id,
        )

        invoice.status = "approved"
        invoice.approved_by = user_id
        invoice.approved_at = datetime.utcnow()
        invoice.gl_transaction_id = txn.id
        invoice.updated_by = user_id
        await self.db.flush()

        return await self.get_invoice(invoice_id, facility_id) or self._to_response(
            invoice, lines, None
        )

    async def pay_invoice(
        self,
        invoice_id: uuid.UUID,
        payment: SupplierInvoicePaymentRequest,
        facility_id: uuid.UUID,
        user_id: uuid.UUID | None,
        idempotency_key: str | None = None,
    ) -> SupplierInvoiceResponse:
        """Record a payment against an approved supplier invoice.

        Posts: DR Accounts Payable (2010) / CR Bank (1020).
        Sets status to ``paid`` when the full balance is cleared.
        """
        result = await self.db.execute(
            select(SupplierInvoice).where(
                SupplierInvoice.id == invoice_id,
                SupplierInvoice.facility_id == facility_id,
                SupplierInvoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            raise SupplierInvoiceError("Supplier invoice not found")
        if invoice.status != "approved":
            raise SupplierInvoiceError(
                f"Cannot pay invoice in status '{invoice.status}' (must be approved)"
            )

        outstanding = invoice.total - invoice.paid_amount
        if outstanding <= 0:
            raise SupplierInvoiceError("Invoice already fully paid")
        if payment.amount > outstanding:
            raise SupplierInvoiceError(
                f"Payment {payment.amount} exceeds outstanding balance {outstanding}"
            )

        post_date = payment.payment_date or date_type.today()
        entries: list[dict] = [
            {
                "account_code": AP_ACCOUNT,
                "debit": Decimal(payment.amount) / Decimal(100),
                "credit": Decimal(0),
            },
            {
                "account_code": BANK_ACCOUNT,
                "debit": Decimal(0),
                "credit": Decimal(payment.amount) / Decimal(100),
            },
        ]
        txn = await post_compound_transaction(
            db=self.db,
            facility_id=facility_id,
            entries=entries,
            metadata={
                "date": post_date,
                "event_type": "supplier_invoice_paid",
                "reference_type": "supplier_invoice",
                "reference_id": invoice.id,
                "description": (
                    f"Payment for supplier invoice {invoice.our_reference} "
                    f"via {payment.payment_method}"
                ),
            },
            idempotency_key=idempotency_key,
            user_id=user_id,
        )

        invoice.paid_amount += payment.amount
        invoice.gl_payment_transaction_id = txn.id
        if invoice.paid_amount >= invoice.total:
            invoice.status = "paid"
            invoice.paid_at = datetime.utcnow()
        invoice.updated_by = user_id
        await self.db.flush()

        refreshed = await self.get_invoice(invoice_id, facility_id)
        return refreshed if refreshed is not None else self._to_response(invoice, [], None)

    async def cancel_invoice(
        self,
        invoice_id: uuid.UUID,
        facility_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> SupplierInvoiceResponse:
        """Cancel a supplier invoice. Only draft invoices may be cancelled."""
        result = await self.db.execute(
            select(SupplierInvoice).where(
                SupplierInvoice.id == invoice_id,
                SupplierInvoice.facility_id == facility_id,
                SupplierInvoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            raise SupplierInvoiceError("Supplier invoice not found")
        if invoice.status != "draft":
            raise SupplierInvoiceError(
                f"Cannot cancel invoice in status '{invoice.status}' (must be draft)"
            )

        invoice.status = "cancelled"
        invoice.cancelled_at = datetime.utcnow()
        invoice.updated_by = user_id
        await self.db.flush()

        refreshed = await self.get_invoice(invoice_id, facility_id)
        return refreshed if refreshed is not None else self._to_response(invoice, [], None)


__all__ = ["SupplierInvoiceService", "SupplierInvoiceError"]
