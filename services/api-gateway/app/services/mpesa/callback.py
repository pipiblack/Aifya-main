"""
M-Pesa STK Push callback handler.
Processes the JSON Safaricom POSTs to our CallBackURL after the customer
completes (or cancels) an STK Push prompt. Updates `mpesa_stk_requests`
and, on success, posts a Payment against the linked invoice.

This module is the bridge between the raw Daraja callback (parsed by
DarajaClient.parse_stk_callback) and our domain.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from structlog import get_logger

from app.services.mpesa.daraja import DarajaClient, STKCallbackData
from app.services.mpesa.stk_push import StkPushService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def handle_stk_callback(
    db: AsyncSession,
    body: dict,
) -> dict:
    """
    Handle a parsed M-Pesa STK Push callback body.

    Steps:
    1. Parse the Safaricom JSON envelope
    2. Update the matching mpesa_stk_requests row
    3. On success, post a Payment to the linked invoice and update its status

    @param db: Async database session
    @param body: Raw JSON body posted by Safaricom
    @returns Acknowledgement dict that we return to Safaricom
    """
    callback = DarajaClient.parse_stk_callback(body)

    logger.info(
        "stk_callback_handled",
        checkout_request_id=callback.checkout_request_id,
        result_code=callback.result_code,
        receipt=callback.mpesa_receipt,
    )

    # 1) Update the stored request row (idempotent)
    service = StkPushService(db)
    row = await service.mark_completed(
        checkout_request_id=callback.checkout_request_id,
        result_code=callback.result_code,
        result_desc=callback.result_desc,
        mpesa_receipt=callback.mpesa_receipt,
        transaction_date=callback.transaction_date,
    )

    # 2) On success with a linked invoice, record the Payment
    if row is not None and callback.result_code == 0 and callback.mpesa_receipt and row.invoice_id is not None:
        await _record_invoice_payment(db, row, callback)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}


async def _record_invoice_payment(
    db: AsyncSession,
    row,  # type: ignore[no-untyped-def]
    callback: STKCallbackData,
) -> None:
    """
    Post the M-Pesa receipt as a Payment against the linked Invoice and
    advance the invoice's paid_amount_cents/status.

    @param db: Async database session
    @param row: The stored MpesaStkRequest row that triggered the payment
    @param callback: Parsed callback data from Safaricom
    """
    from app.models.billing import Invoice, Payment

    try:
        result = await db.execute(
            select(Invoice).where(
                Invoice.id == row.invoice_id,
                Invoice.is_deleted == False,  # noqa: E712
            )
        )
        invoice = result.scalar_one_or_none()
        if invoice is None:
            logger.warning(
                "stk_callback_invoice_missing",
                invoice_id=str(row.invoice_id),
                receipt=callback.mpesa_receipt,
            )
            return

        amount_cents = int(Decimal(callback.amount or 0) * 100)
        payment = Payment(
            invoice_id=invoice.id,
            facility_id=invoice.facility_id,
            patient_id=invoice.patient_id,
            amount_cents=amount_cents,
            payment_method="mpesa",
            mpesa_transaction_id=callback.mpesa_receipt,
            reference_number=callback.mpesa_receipt,
            notes=f"M-Pesa STK from {callback.phone_number}",
        )
        db.add(payment)

        invoice.paid_amount_cents = (invoice.paid_amount_cents or 0) + amount_cents
        if invoice.paid_amount_cents >= invoice.total_amount_cents:
            invoice.status = "paid"
        elif invoice.paid_amount_cents > 0:
            invoice.status = "partially_paid"

        await db.flush()
        logger.info(
            "stk_invoice_payment_recorded",
            invoice_id=str(invoice.id),
            amount_cents=amount_cents,
            receipt=callback.mpesa_receipt,
        )
    except Exception as exc:
        logger.error(
            "stk_invoice_payment_error",
            error=str(exc),
            receipt=callback.mpesa_receipt,
        )
        # Don't re-raise — Safaricom must always get a 200 ack
