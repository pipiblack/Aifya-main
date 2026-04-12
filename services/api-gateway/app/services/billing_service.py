import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.billing import Invoice, InvoiceItem, Payment
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.schemas.billing import (
    BillingSummary,
    InvoiceCreate,
    InvoiceListItem,
    PaymentCreate,
)


class BillingService:
    """
    Service for hospital billing: invoice creation, line items,
    payments (Cash/M-Pesa/Insurance/Exemption), and dashboard summaries.
    Money in KES cents per CLAUDE.md.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Invoice Creation ─────────────────────────────────────────────────

    async def create_invoice(
        self,
        data: InvoiceCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> Invoice:
        """
        Create an invoice with line items. Computes subtotal and total.

        @param data: Invoice data with items
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created invoice
        """
        invoice_number = await self._next_invoice_number(facility_id)

        # Compute line item totals
        subtotal = 0
        total_discount = 0
        items_to_add: list[InvoiceItem] = []
        for item_data in data.items:
            line_total = item_data.quantity * item_data.unit_price_cents
            items_to_add.append(
                InvoiceItem(
                    facility_id=facility_id,
                    item_type=item_data.item_type,
                    description=item_data.description,
                    quantity=item_data.quantity,
                    unit_price_cents=item_data.unit_price_cents,
                    total_cents=line_total,
                    discount_cents=item_data.discount_cents,
                    reference_id=item_data.reference_id,
                    reference_type=item_data.reference_type,
                    created_by=created_by,
                    updated_by=created_by,
                )
            )
            subtotal += line_total
            total_discount += item_data.discount_cents

        total = subtotal - total_discount

        invoice = Invoice(
            facility_id=facility_id,
            encounter_id=data.encounter_id,
            patient_id=data.patient_id,
            invoice_number=invoice_number,
            status="draft",
            payment_method=data.payment_method,
            insurance_provider=data.insurance_provider,
            insurance_member_no=data.insurance_member_no,
            subtotal_cents=subtotal,
            discount_cents=total_discount,
            tax_cents=0,
            total_cents=total,
            paid_cents=0,
            balance_cents=total,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )

        self.db.add(invoice)
        await self.db.flush()
        await self.db.refresh(invoice)

        # Attach items to invoice
        for item in items_to_add:
            item.invoice_id = invoice.id
            self.db.add(item)

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="billing",
            stream_id=data.patient_id,
            event_type="InvoiceCreated",
            event_data={
                "invoice_number": invoice_number,
                "total_cents": total,
                "item_count": len(data.items),
            },
            version=1,
            created_by=created_by,
        )
        self.db.add(event)

        return invoice

    # ── Invoice Detail ───────────────────────────────────────────────────

    async def get_invoice_detail(
        self, invoice_id: uuid.UUID, facility_id: uuid.UUID
    ) -> tuple[Invoice | None, list[InvoiceItem], str | None, str | None]:
        """
        Get invoice with all line items and patient info.

        @param invoice_id: Invoice UUID
        @param facility_id: Facility UUID
        @returns Tuple of (invoice, items, patient_name, patient_mrn)
        """
        result = await self.db.execute(
            select(Invoice, Patient)
            .join(Patient, Invoice.patient_id == Patient.id)
            .where(
                Invoice.id == invoice_id,
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
        row = result.first()
        if not row:
            return None, [], None, None

        invoice, patient = row

        items_result = await self.db.execute(
            select(InvoiceItem)
            .where(
                InvoiceItem.invoice_id == invoice_id,
                InvoiceItem.facility_id == facility_id,
                InvoiceItem.is_deleted == False,  # noqa: E712
            )
            .order_by(InvoiceItem.created_at.asc())
        )
        items = list(items_result.scalars().all())

        patient_name = f"{patient.first_name} {patient.last_name}"
        return invoice, items, patient_name, patient.mrn

    # ── Invoice List ─────────────────────────────────────────────────────

    async def get_invoices(
        self,
        facility_id: uuid.UUID,
        status_filter: str | None = None,
        patient_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[InvoiceListItem], int]:
        """
        List invoices with patient info, item counts, and pagination.
        Uses a LEFT JOIN subquery for item counts to avoid N+1 queries.

        @param facility_id: Facility UUID
        @param status_filter: Optional status filter
        @param patient_id: Optional patient filter
        @param page: Page number
        @param page_size: Items per page
        @returns Tuple of (invoice list items, total count)
        """
        # Subquery: item counts per invoice
        item_counts_sq = (
            select(
                InvoiceItem.invoice_id,
                func.count(InvoiceItem.id).label("item_count"),
            )
            .where(InvoiceItem.is_deleted == False)  # noqa: E712
            .group_by(InvoiceItem.invoice_id)
            .subquery()
        )

        base = (
            select(Invoice, Patient)
            .join(Patient, Invoice.patient_id == Patient.id)
            .where(
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )

        if status_filter:
            base = base.where(Invoice.status == status_filter)
        if patient_id:
            base = base.where(Invoice.patient_id == patient_id)

        # Count
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Paginate with item count LEFT JOIN
        stmt = (
            select(
                Invoice,
                Patient,
                func.coalesce(item_counts_sq.c.item_count, 0).label("item_count"),
            )
            .join(Patient, Invoice.patient_id == Patient.id)
            .outerjoin(item_counts_sq, Invoice.id == item_counts_sq.c.invoice_id)
            .where(
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )

        if status_filter:
            stmt = stmt.where(Invoice.status == status_filter)
        if patient_id:
            stmt = stmt.where(Invoice.patient_id == patient_id)

        stmt = stmt.order_by(Invoice.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)

        result = await self.db.execute(stmt)
        rows = result.all()

        items: list[InvoiceListItem] = []
        for invoice, patient, item_count in rows:
            items.append(
                InvoiceListItem(
                    id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    encounter_id=invoice.encounter_id,
                    patient_id=invoice.patient_id,
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    patient_mrn=patient.mrn,
                    status=invoice.status,
                    total_cents=invoice.total_cents,
                    paid_cents=invoice.paid_cents,
                    balance_cents=invoice.balance_cents,
                    payment_method=invoice.payment_method,
                    item_count=item_count,
                    created_at=invoice.created_at,
                )
            )

        return items, total

    # ── Finalize Invoice ─────────────────────────────────────────────────

    async def finalize_invoice(
        self, invoice_id: uuid.UUID, facility_id: uuid.UUID, finalized_by: uuid.UUID
    ) -> Invoice | None:
        """
        Finalize a draft invoice (locks it for payment).

        @param invoice_id: Invoice UUID
        @param facility_id: Facility UUID
        @param finalized_by: Staff UUID
        @returns Finalized invoice or None
        """
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            return None
        if invoice.status != "draft":
            raise ValueError(f"Cannot finalize invoice with status: {invoice.status}")

        invoice.status = "finalized"
        invoice.finalized_at = datetime.now(timezone.utc)
        invoice.finalized_by = finalized_by
        invoice.updated_by = finalized_by

        # Update encounter billing status
        enc_result = await self.db.execute(
            select(Encounter).where(Encounter.id == invoice.encounter_id)
        )
        encounter = enc_result.scalar_one_or_none()
        if encounter:
            encounter.billing_status = "billed"

        await self.db.flush()
        await self.db.refresh(invoice)

        event = EventBase(
            facility_id=facility_id,
            stream_type="billing",
            stream_id=invoice.patient_id,
            event_type="InvoiceFinalized",
            event_data={
                "invoice_number": invoice.invoice_number,
                "total_cents": invoice.total_cents,
            },
            version=1,
            created_by=finalized_by,
        )
        self.db.add(event)

        return invoice

    # ── Record Payment ───────────────────────────────────────────────────

    async def record_payment(
        self,
        invoice_id: uuid.UUID,
        data: PaymentCreate,
        facility_id: uuid.UUID,
        received_by: uuid.UUID,
    ) -> Payment:
        """
        Record a payment against an invoice. Updates balances and status.
        Supports partial payments.

        @param invoice_id: Invoice UUID
        @param data: Payment data
        @param facility_id: Facility UUID
        @param received_by: Staff UUID who received payment
        @returns Created payment
        """
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise ValueError("Invoice not found")
        if invoice.status in ("cancelled", "waived"):
            raise ValueError(f"Cannot pay invoice with status: {invoice.status}")
        if data.amount_cents > invoice.balance_cents:
            raise ValueError(
                f"Payment amount ({data.amount_cents}) exceeds balance ({invoice.balance_cents})"
            )

        payment = Payment(
            facility_id=facility_id,
            invoice_id=invoice_id,
            patient_id=invoice.patient_id,
            amount_cents=data.amount_cents,
            payment_method=data.payment_method,
            reference_number=data.reference_number,
            mpesa_transaction_id=data.mpesa_transaction_id,
            received_by=received_by,
            notes=data.notes,
            created_by=received_by,
            updated_by=received_by,
        )
        self.db.add(payment)

        # Update invoice
        invoice.paid_cents += data.amount_cents
        invoice.balance_cents = invoice.total_cents - invoice.paid_cents
        if invoice.balance_cents <= 0:
            invoice.status = "paid"
            invoice.balance_cents = 0
        elif invoice.paid_cents > 0:
            invoice.status = "partially_paid"
        invoice.updated_by = received_by

        # Update encounter billing status if fully paid
        if invoice.status == "paid":
            enc_result = await self.db.execute(
                select(Encounter).where(Encounter.id == invoice.encounter_id)
            )
            encounter = enc_result.scalar_one_or_none()
            if encounter:
                encounter.billing_status = "paid"

        await self.db.flush()
        await self.db.refresh(payment)

        event = EventBase(
            facility_id=facility_id,
            stream_type="billing",
            stream_id=invoice.patient_id,
            event_type="PaymentReceived",
            event_data={
                "invoice_number": invoice.invoice_number,
                "amount_cents": data.amount_cents,
                "payment_method": data.payment_method,
                "new_balance_cents": invoice.balance_cents,
                "invoice_status": invoice.status,
            },
            version=1,
            created_by=received_by,
        )
        self.db.add(event)

        return payment

    # ── Waive Invoice ────────────────────────────────────────────────────

    async def waive_invoice(
        self,
        invoice_id: uuid.UUID,
        facility_id: uuid.UUID,
        waived_by: uuid.UUID,
        reason: str,
    ) -> Invoice | None:
        """
        Waive remaining balance on an invoice (exemption/charity).

        @param invoice_id: Invoice UUID
        @param facility_id: Facility UUID
        @param waived_by: Staff UUID
        @param reason: Reason for waiver
        @returns Updated invoice or None
        """
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            return None

        invoice.status = "waived"
        invoice.notes = (invoice.notes or "") + f"\nWaiver: {reason}"
        invoice.balance_cents = 0
        invoice.updated_by = waived_by

        # Update encounter
        enc_result = await self.db.execute(
            select(Encounter).where(Encounter.id == invoice.encounter_id)
        )
        encounter = enc_result.scalar_one_or_none()
        if encounter:
            encounter.billing_status = "waived"

        await self.db.flush()
        await self.db.refresh(invoice)

        event = EventBase(
            facility_id=facility_id,
            stream_type="billing",
            stream_id=invoice.patient_id,
            event_type="InvoiceWaived",
            event_data={
                "invoice_number": invoice.invoice_number,
                "reason": reason,
                "waived_amount_cents": invoice.total_cents - invoice.paid_cents,
            },
            version=1,
            created_by=waived_by,
        )
        self.db.add(event)

        return invoice

    # ── Dashboard Summary ────────────────────────────────────────────────

    async def get_summary(self, facility_id: uuid.UUID) -> BillingSummary:
        """
        Get billing dashboard summary stats.

        @param facility_id: Facility UUID
        @returns Billing summary
        """
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.facility_id == facility_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
        invoices = list(result.scalars().all())

        return BillingSummary(
            total_invoices=len(invoices),
            draft_count=sum(1 for i in invoices if i.status == "draft"),
            finalized_count=sum(1 for i in invoices if i.status == "finalized"),
            paid_count=sum(1 for i in invoices if i.status == "paid"),
            partially_paid_count=sum(
                1 for i in invoices if i.status == "partially_paid"
            ),
            total_billed_cents=sum(i.total_cents for i in invoices),
            total_paid_cents=sum(i.paid_cents for i in invoices),
            total_outstanding_cents=sum(
                i.balance_cents
                for i in invoices
                if i.status not in ("cancelled", "waived", "paid")
            ),
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _next_invoice_number(self, facility_id: uuid.UUID) -> str:
        """Generate the next invoice number (INV-YYYYMMDD-XXXX)."""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        prefix = f"INV-{today}-"

        result = await self.db.execute(
            select(func.count())
            .select_from(Invoice)
            .where(
                Invoice.facility_id == facility_id,
                Invoice.invoice_number.like(f"{prefix}%"),
            )
        )
        count = result.scalar_one()
        return f"{prefix}{count + 1:04d}"
