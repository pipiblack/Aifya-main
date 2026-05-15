import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.patient import Patient
from app.models.pharmacy import Dispensing, PharmacyItem, StockTransaction
from app.models.prescription import Prescription
from app.schemas.pharmacy import (
    DispenseRequest,
    InventoryAdjustRequest,
    InventoryReceiveRequest,
    PharmacyItemCreate,
    PharmacyItemUpdate,
    PharmacyQueueItem,
    StockAdjustmentRequest,
    StockAlert,
    StockReceiptRequest,
    StockSummaryRow,
)

logger = logging.getLogger(__name__)


class PharmacyService:
    """
    Service layer for pharmacy operations: inventory, dispensing, stock management.
    Drug interaction checks MUST have passed before dispensing (CLAUDE.md).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Pharmacy Queue ────────────────────────────────────────────────────

    async def get_pending_prescriptions(self, facility_id: uuid.UUID) -> tuple[list[PharmacyQueueItem], int]:
        """
        Get prescriptions pending dispensing (the pharmacy queue).
        Ordered by creation time (FIFO).

        @param facility_id: Facility UUID
        @returns Tuple of (queue items, total count)
        """
        stmt = (
            select(Prescription, Patient)
            .join(Patient, Prescription.patient_id == Patient.id)
            .where(
                Prescription.facility_id == facility_id,
                Prescription.status.in_(["pending", "partially_dispensed"]),
                Prescription.is_deleted == False,  # noqa: E712
            )
            .order_by(Prescription.created_at.asc())
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        items: list[PharmacyQueueItem] = []
        for rx, patient in rows:
            items.append(
                PharmacyQueueItem(
                    prescription_id=rx.id,
                    encounter_id=rx.encounter_id,
                    patient_id=rx.patient_id,
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    patient_mrn=patient.mrn,
                    drug_name=rx.drug_name,
                    generic_name=rx.generic_name,
                    is_keml=rx.is_keml,
                    dosage=rx.dosage,
                    route=rx.route,
                    frequency=rx.frequency,
                    duration_days=rx.duration_days,
                    quantity=rx.quantity,
                    instructions=rx.instructions,
                    prescriber_id=rx.prescriber_id,
                    status=rx.status,
                    created_at=rx.created_at,
                )
            )

        return items, len(items)

    # ── Dispensing ────────────────────────────────────────────────────────

    async def dispense(
        self,
        data: DispenseRequest,
        facility_id: uuid.UUID,
        dispensed_by: uuid.UUID,
    ) -> Dispensing:
        """
        Dispense a prescription. Validates stock, deducts inventory,
        updates prescription status.

        @param data: Dispense request data
        @param facility_id: Facility UUID
        @param dispensed_by: Pharmacist staff UUID
        @returns Dispensing record
        @raises ValueError: If prescription not found, already dispensed, or stock insufficient
        """
        # Fetch prescription
        rx_result = await self.db.execute(
            select(Prescription).where(
                Prescription.id == data.prescription_id,
                Prescription.facility_id == facility_id,
                Prescription.is_deleted == False,  # noqa: E712
            )
        )
        rx = rx_result.scalar_one_or_none()
        if not rx:
            raise ValueError("Prescription not found")
        if rx.status not in ("pending", "partially_dispensed"):
            raise ValueError(f"Prescription cannot be dispensed (status: {rx.status})")

        # Check stock if pharmacy item linked
        pharmacy_item: PharmacyItem | None = None
        unit_price: int | None = None
        if data.pharmacy_item_id:
            item_result = await self.db.execute(
                select(PharmacyItem)
                .where(
                    PharmacyItem.id == data.pharmacy_item_id,
                    PharmacyItem.facility_id == facility_id,
                    PharmacyItem.is_deleted == False,  # noqa: E712
                )
                .with_for_update()
            )
            pharmacy_item = item_result.scalar_one_or_none()
            if not pharmacy_item:
                raise ValueError("Pharmacy item not found")
            if pharmacy_item.current_quantity < data.quantity_dispensed:
                raise ValueError(
                    f"Insufficient stock: {pharmacy_item.current_quantity} available, "
                    f"{data.quantity_dispensed} requested"
                )
            # Check expiry — cannot dispense expired drugs
            if pharmacy_item.expiry_date and pharmacy_item.expiry_date < date.today():
                raise ValueError("Cannot dispense expired medication")
            unit_price = pharmacy_item.selling_price_cents

        total_price = unit_price * data.quantity_dispensed if unit_price else None

        # Create dispensing record
        dispensing = Dispensing(
            facility_id=facility_id,
            prescription_id=data.prescription_id,
            patient_id=data.patient_id,
            pharmacy_item_id=data.pharmacy_item_id,
            dispensed_by=dispensed_by,
            drug_name=rx.drug_name,
            quantity_requested=rx.quantity or data.quantity_dispensed,
            quantity_dispensed=data.quantity_dispensed,
            substitution_drug=data.substitution_drug,
            substitution_reason=data.substitution_reason,
            dosage_instructions=data.dosage_instructions,
            counseling_done=data.counseling_done,
            counseling_notes=data.counseling_notes,
            unit_price_cents=unit_price,
            total_price_cents=total_price,
            payment_status="pending",
            payment_method=data.payment_method,
            created_by=dispensed_by,
            updated_by=dispensed_by,
        )

        self.db.add(dispensing)
        await self.db.flush()
        await self.db.refresh(dispensing)

        # Deduct stock
        if pharmacy_item:
            qty_before = pharmacy_item.current_quantity
            pharmacy_item.current_quantity -= data.quantity_dispensed
            qty_after = pharmacy_item.current_quantity

            stock_tx = StockTransaction(
                facility_id=facility_id,
                pharmacy_item_id=pharmacy_item.id,
                dispensing_id=dispensing.id,
                transaction_type="dispensing",
                quantity_change=-data.quantity_dispensed,
                quantity_before=qty_before,
                quantity_after=qty_after,
                unit_cost_cents=unit_price,
                created_by=dispensed_by,
                updated_by=dispensed_by,
            )
            self.db.add(stock_tx)

        # Update prescription status
        rx.dispensed_by = dispensed_by
        rx.dispensed_at = datetime.now(UTC)
        rx.dispensed_quantity = (rx.dispensed_quantity or 0) + data.quantity_dispensed
        rx.unit_cost_cents = unit_price
        rx.total_cost_cents = total_price

        if rx.quantity and rx.dispensed_quantity < rx.quantity:
            rx.status = "partially_dispensed"
        else:
            rx.status = "dispensed"

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="prescription",
            stream_id=data.patient_id,
            event_type="PrescriptionDispensed",
            event_data={
                "prescription_id": str(data.prescription_id),
                "drug_name": rx.drug_name,
                "quantity_dispensed": data.quantity_dispensed,
                "substitution": data.substitution_drug,
                "counseling_done": data.counseling_done,
            },
            version=1,
            created_by=dispensed_by,
        )
        self.db.add(event)

        return dispensing

    # ── Inventory Management ──────────────────────────────────────────────

    async def create_item(
        self,
        data: PharmacyItemCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> PharmacyItem:
        """
        Add a new item to pharmacy inventory.

        @param data: Pharmacy item data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created pharmacy item
        """
        item = PharmacyItem(
            facility_id=facility_id,
            created_by=created_by,
            updated_by=created_by,
            **data.model_dump(),
        )

        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)

        # Initial stock receipt transaction
        if data.current_quantity > 0:
            stock_tx = StockTransaction(
                facility_id=facility_id,
                pharmacy_item_id=item.id,
                transaction_type="receipt",
                quantity_change=data.current_quantity,
                quantity_before=0,
                quantity_after=data.current_quantity,
                batch_number=data.batch_number,
                expiry_date=data.expiry_date,
                unit_cost_cents=data.buying_price_cents,
                reason="Initial stock entry",
                created_by=created_by,
                updated_by=created_by,
            )
            self.db.add(stock_tx)

        return item

    async def update_item(
        self,
        item_id: uuid.UUID,
        data: PharmacyItemUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> PharmacyItem | None:
        """
        Update a pharmacy inventory item.

        @param item_id: PharmacyItem UUID
        @param data: Fields to update
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated item or None
        """
        result = await self.db.execute(
            select(PharmacyItem).where(
                PharmacyItem.id == item_id,
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        item.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def get_inventory(
        self,
        facility_id: uuid.UUID,
        query: str | None = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[PharmacyItem], int]:
        """
        List pharmacy inventory with search and pagination.

        @param facility_id: Facility UUID
        @param query: Optional search by drug name or code
        @param active_only: Only show active items
        @param page: Page number
        @param page_size: Items per page
        @returns Tuple of (items, total count)
        """
        stmt = select(PharmacyItem).where(
            PharmacyItem.facility_id == facility_id,
            PharmacyItem.is_deleted == False,  # noqa: E712
        )

        if active_only:
            stmt = stmt.where(PharmacyItem.is_active == True)  # noqa: E712

        if query:
            search = f"%{query}%"
            stmt = stmt.where(
                PharmacyItem.drug_name.ilike(search)
                | PharmacyItem.drug_code.ilike(search)
                | PharmacyItem.generic_name.ilike(search)
            )

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Paginate
        stmt = stmt.order_by(PharmacyItem.drug_name.asc()).offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def receive_stock(
        self,
        data: StockReceiptRequest,
        facility_id: uuid.UUID,
        received_by: uuid.UUID,
    ) -> StockTransaction:
        """
        Receive new stock into inventory.

        @param data: Stock receipt data
        @param facility_id: Facility UUID
        @param received_by: Staff UUID
        @returns Stock transaction record
        """
        result = await self.db.execute(
            select(PharmacyItem).where(
                PharmacyItem.id == data.pharmacy_item_id,
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError("Pharmacy item not found")

        qty_before = item.current_quantity
        item.current_quantity += data.quantity
        qty_after = item.current_quantity

        # Update batch/expiry if provided
        if data.batch_number:
            item.batch_number = data.batch_number
        if data.expiry_date:
            item.expiry_date = data.expiry_date

        tx = StockTransaction(
            facility_id=facility_id,
            pharmacy_item_id=data.pharmacy_item_id,
            transaction_type="receipt",
            quantity_change=data.quantity,
            quantity_before=qty_before,
            quantity_after=qty_after,
            reference_number=data.reference_number,
            reason=data.reason,
            unit_cost_cents=data.unit_cost_cents,
            batch_number=data.batch_number,
            expiry_date=data.expiry_date,
            created_by=received_by,
            updated_by=received_by,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(tx)
        return tx

    async def adjust_stock(
        self,
        data: StockAdjustmentRequest,
        facility_id: uuid.UUID,
        adjusted_by: uuid.UUID,
    ) -> StockTransaction:
        """
        Adjust stock quantity (loss, damage, correction, transfer).

        @param data: Adjustment data
        @param facility_id: Facility UUID
        @param adjusted_by: Staff UUID
        @returns Stock transaction record
        """
        result = await self.db.execute(
            select(PharmacyItem).where(
                PharmacyItem.id == data.pharmacy_item_id,
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError("Pharmacy item not found")

        qty_before = item.current_quantity
        new_qty = qty_before + data.quantity_change
        if new_qty < 0:
            raise ValueError(f"Adjustment would result in negative stock ({new_qty})")

        item.current_quantity = new_qty

        tx = StockTransaction(
            facility_id=facility_id,
            pharmacy_item_id=data.pharmacy_item_id,
            transaction_type="adjustment",
            quantity_change=data.quantity_change,
            quantity_before=qty_before,
            quantity_after=new_qty,
            reference_number=data.reference_number,
            reason=data.reason,
            created_by=adjusted_by,
            updated_by=adjusted_by,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(tx)
        return tx

    async def get_stock_alerts(self, facility_id: uuid.UUID) -> list[StockAlert]:
        """
        Get stock alerts: low stock, expiring soon (30 days), expired, out of stock.

        @param facility_id: Facility UUID
        @returns List of stock alerts
        """
        result = await self.db.execute(
            select(PharmacyItem).where(
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_active == True,  # noqa: E712
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
        )
        items = list(result.scalars().all())
        today = date.today()
        thirty_days = today + timedelta(days=30)

        alerts: list[StockAlert] = []
        for item in items:
            if item.current_quantity == 0:
                alerts.append(
                    StockAlert(
                        item_id=item.id,
                        drug_name=item.drug_name,
                        drug_code=item.drug_code,
                        current_quantity=item.current_quantity,
                        reorder_level=item.reorder_level,
                        expiry_date=item.expiry_date,
                        alert_type="out_of_stock",
                    )
                )
            elif item.current_quantity <= item.reorder_level:
                alerts.append(
                    StockAlert(
                        item_id=item.id,
                        drug_name=item.drug_name,
                        drug_code=item.drug_code,
                        current_quantity=item.current_quantity,
                        reorder_level=item.reorder_level,
                        expiry_date=item.expiry_date,
                        alert_type="low_stock",
                    )
                )

            if item.expiry_date:
                if item.expiry_date < today:
                    alerts.append(
                        StockAlert(
                            item_id=item.id,
                            drug_name=item.drug_name,
                            drug_code=item.drug_code,
                            current_quantity=item.current_quantity,
                            reorder_level=item.reorder_level,
                            expiry_date=item.expiry_date,
                            alert_type="expired",
                        )
                    )
                elif item.expiry_date <= thirty_days:
                    alerts.append(
                        StockAlert(
                            item_id=item.id,
                            drug_name=item.drug_name,
                            drug_code=item.drug_code,
                            current_quantity=item.current_quantity,
                            reorder_level=item.reorder_level,
                            expiry_date=item.expiry_date,
                            alert_type="expiring_soon",
                        )
                    )

        return alerts

    # ── Top-up on existing item (audit fix #1) ─────────────────────────────

    async def receive_for_item(
        self,
        item_id: uuid.UUID,
        data: InventoryReceiveRequest,
        facility_id: uuid.UUID,
        received_by: uuid.UUID,
    ) -> StockTransaction:
        """Top up an EXISTING pharmacy item — never creates a new catalogue row.

        Increments ``pharmacy_items.stock_qty`` (``current_quantity``) by the
        received quantity, writes an immutable ``stock_transactions`` row, and
        attempts to post the GRN to the Finance GL via ``inventory_purchase``
        when ``unit_cost`` is provided. The GL posting is best-effort — if
        Finance is unavailable or no posting rule exists, we log a warning and
        continue (the audit trail is still complete).

        @param item_id: PharmacyItem UUID (URL path parameter)
        @param data: Receive request data (quantity, batch, expiry, etc.)
        @param facility_id: Facility UUID for multi-tenant isolation
        @param received_by: Staff UUID performing the receipt
        @returns Stock transaction record
        @raises ValueError: If the item does not exist in this facility
        """
        result = await self.db.execute(
            select(PharmacyItem)
            .where(
                PharmacyItem.id == item_id,
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
            .with_for_update()
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError("Pharmacy item not found in this facility")

        qty_before = item.current_quantity
        item.current_quantity = qty_before + data.quantity
        qty_after = item.current_quantity

        if data.batch_no:
            item.batch_number = data.batch_no
        if data.expiry_date:
            item.expiry_date = data.expiry_date
        if data.supplier:
            item.supplier = data.supplier

        # Decimal cost → integer cents for the audit row; never lose precision.
        unit_cost_cents: int | None = None
        if data.unit_cost is not None:
            unit_cost_cents = int(
                (Decimal(data.unit_cost) * Decimal(100)).quantize(Decimal("1"))
            )
            if item.buying_price_cents is None:
                item.buying_price_cents = unit_cost_cents

        tx = StockTransaction(
            facility_id=facility_id,
            pharmacy_item_id=item.id,
            transaction_type="receive",
            quantity_change=data.quantity,
            quantity_before=qty_before,
            quantity_after=qty_after,
            reference_number=data.reference_number,
            reason=data.notes,
            unit_cost_cents=unit_cost_cents,
            batch_number=data.batch_no,
            expiry_date=data.expiry_date,
            created_by=received_by,
            updated_by=received_by,
        )
        self.db.add(tx)

        # Emit event for the audit log
        event = EventBase(
            facility_id=facility_id,
            stream_type="pharmacy_item",
            stream_id=item.id,
            event_type="StockReceived",
            event_data={
                "pharmacy_item_id": str(item.id),
                "quantity": data.quantity,
                "batch_no": data.batch_no,
                "expiry_date": data.expiry_date.isoformat() if data.expiry_date else None,
                "supplier": data.supplier,
                "unit_cost_cents": unit_cost_cents,
                "notes": data.notes,
            },
            version=1,
            created_by=received_by,
        )
        self.db.add(event)

        await self.db.flush()
        await self.db.refresh(tx)

        # Best-effort GL posting — never block the receipt on Finance.
        if data.unit_cost is not None and data.unit_cost > 0:
            try:
                from app.services.finance.posting_engine import post_transaction

                total_amount = Decimal(data.unit_cost) * Decimal(data.quantity)
                await post_transaction(
                    db=self.db,
                    facility_id=facility_id,
                    event_type="inventory_purchase",
                    amount=total_amount,
                    metadata={
                        "date": date.today(),
                        "reference_type": "stock_transaction",
                        "reference_id": tx.id,
                        "description": (
                            f"Stock receipt — {item.drug_name} x{data.quantity}"
                            + (f" (batch {data.batch_no})" if data.batch_no else "")
                        ),
                    },
                    idempotency_key=f"stock-receive-{tx.id}",
                    user_id=received_by,
                )
            except Exception as exc:  # noqa: BLE001 — best-effort
                logger.warning(
                    "Finance GL posting skipped for stock receipt %s: %s",
                    tx.id,
                    exc,
                )

        return tx

    async def adjust_to_qty(
        self,
        item_id: uuid.UUID,
        data: InventoryAdjustRequest,
        facility_id: uuid.UUID,
        adjusted_by: uuid.UUID,
    ) -> StockTransaction:
        """Stock-take correction — set ``current_quantity`` to ``new_qty`` exactly.

        Used after a physical stock-take to reconcile system qty to counted qty.
        Writes an immutable adjustment ``stock_transaction`` capturing the delta.

        @param item_id: PharmacyItem UUID
        @param data: Adjustment request (new_qty + reason)
        @param facility_id: Facility UUID
        @param adjusted_by: Staff UUID
        @returns Stock transaction record
        @raises ValueError: If item not found
        """
        result = await self.db.execute(
            select(PharmacyItem)
            .where(
                PharmacyItem.id == item_id,
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
            .with_for_update()
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError("Pharmacy item not found in this facility")

        qty_before = item.current_quantity
        delta = data.new_qty - qty_before
        item.current_quantity = data.new_qty

        tx = StockTransaction(
            facility_id=facility_id,
            pharmacy_item_id=item.id,
            transaction_type="adjustment",
            quantity_change=delta,
            quantity_before=qty_before,
            quantity_after=data.new_qty,
            reason=data.reason,
            created_by=adjusted_by,
            updated_by=adjusted_by,
        )
        self.db.add(tx)

        event = EventBase(
            facility_id=facility_id,
            stream_type="pharmacy_item",
            stream_id=item.id,
            event_type="StockAdjusted",
            event_data={
                "pharmacy_item_id": str(item.id),
                "qty_before": qty_before,
                "qty_after": data.new_qty,
                "delta": delta,
                "reason": data.reason,
            },
            version=1,
            created_by=adjusted_by,
        )
        self.db.add(event)

        await self.db.flush()
        await self.db.refresh(tx)
        return tx

    # ── Stock Summary (audit fix #2) ───────────────────────────────────────

    async def get_stock_summary(
        self,
        facility_id: uuid.UUID,
        start_date: date,
        end_date: date,
        item_id: uuid.UUID | None = None,
    ) -> list[StockSummaryRow]:
        """Per-item Opening / Received / Sales / Closing for a date range.

        Pure SQL aggregation against ``stock_transactions`` joined on
        ``pharmacy_items``. Required by KEMSA / PPB pharmacy stock control
        regulations for audit trails.

        - opening_stock = sum(qty_change) for tx_date < start_date
        - received_stock = sum(qty_change) for receipts in [start_date, end_date]
        - sales_stock = abs(sum(qty_change)) for dispensings in window
        - closing_stock = opening + received - sales

        @param facility_id: Facility UUID
        @param start_date: Window start (inclusive)
        @param end_date: Window end (inclusive)
        @param item_id: Optional filter to a single item
        @returns List of summary rows
        """
        # Build per-window aggregates using conditional sums so we get all four
        # numbers in a single query — much faster than per-item round-trips.
        opening_expr = func.sum(
            case(
                (
                    func.date(StockTransaction.created_at) < start_date,
                    StockTransaction.quantity_change,
                ),
                else_=0,
            )
        )
        received_expr = func.sum(
            case(
                (
                    (StockTransaction.transaction_type.in_(["receive", "receipt"]))
                    & (func.date(StockTransaction.created_at) >= start_date)
                    & (func.date(StockTransaction.created_at) <= end_date),
                    StockTransaction.quantity_change,
                ),
                else_=0,
            )
        )
        sales_expr = func.sum(
            case(
                (
                    (StockTransaction.transaction_type == "dispensing")
                    & (func.date(StockTransaction.created_at) >= start_date)
                    & (func.date(StockTransaction.created_at) <= end_date),
                    -StockTransaction.quantity_change,  # dispensings are negative
                ),
                else_=0,
            )
        )

        stmt = (
            select(
                PharmacyItem.id,
                PharmacyItem.drug_code,
                PharmacyItem.drug_name,
                PharmacyItem.unit_of_measure,
                PharmacyItem.current_quantity,
                opening_expr.label("opening_stock"),
                received_expr.label("received_stock"),
                sales_expr.label("sales_stock"),
            )
            .outerjoin(
                StockTransaction,
                (StockTransaction.pharmacy_item_id == PharmacyItem.id)
                & (StockTransaction.facility_id == facility_id)
                & (StockTransaction.is_deleted == False),  # noqa: E712
            )
            .where(
                PharmacyItem.facility_id == facility_id,
                PharmacyItem.is_deleted == False,  # noqa: E712
            )
            .group_by(
                PharmacyItem.id,
                PharmacyItem.drug_code,
                PharmacyItem.drug_name,
                PharmacyItem.unit_of_measure,
                PharmacyItem.current_quantity,
            )
            .order_by(PharmacyItem.drug_name.asc())
        )
        if item_id is not None:
            stmt = stmt.where(PharmacyItem.id == item_id)

        rows = (await self.db.execute(stmt)).all()

        summary: list[StockSummaryRow] = []
        for r in rows:
            opening = int(r.opening_stock or 0)
            received = int(r.received_stock or 0)
            sales = int(r.sales_stock or 0)
            summary.append(
                StockSummaryRow(
                    item_id=r.id,
                    item_name=r.drug_name,
                    drug_code=r.drug_code,
                    unit=r.unit_of_measure,
                    opening_stock=opening,
                    received_stock=received,
                    sales_stock=sales,
                    closing_stock=opening + received - sales,
                    current_stock=int(r.current_quantity or 0),
                )
            )
        return summary
