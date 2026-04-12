"""
M-Pesa Daraja integration router.
Provides STK Push payments, C2B callbacks, transaction status, and reconciliation.
Callbacks are public endpoints (no auth) — Safaricom sends them directly.
"""

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user
from app.database import get_db
from app.services.mpesa.daraja import (
    DarajaClient,
    STKCallbackData,
    STKPushRequest,
    STKPushResponse,
    TransactionStatus,
    get_daraja_config,
)

logger = get_logger(__name__)

router = APIRouter()


# ── Request / Response Schemas ───────────────────────────────────────────────


class STKPushApiRequest(BaseModel):
    """
    API request to initiate an STK Push payment.

    @param phone_number: Customer phone (07XX or +254XX)
    @param amount_kes: Amount in KES (whole number)
    @param invoice_id: Invoice UUID to pay
    @param description: Optional transaction description
    """
    phone_number: str
    amount_kes: int
    invoice_id: str
    description: str = "Hospital Payment"


class MPesaStatusResponse(BaseModel):
    """
    M-Pesa configuration status.

    @param configured: Whether Daraja credentials are set
    @param environment: sandbox or production
    @param shortcode: Configured business shortcode
    """
    configured: bool
    environment: str = ""
    shortcode: str = ""


# ── STK Push Endpoint ────────────────────────────────────────────────────────


@router.post("/stk-push", response_model=STKPushResponse)
async def initiate_stk_push(
    request: STKPushApiRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> STKPushResponse:
    """
    Initiate M-Pesa STK Push (Lipa Na M-Pesa Online) to collect payment.
    Sends a USSD prompt to the patient's phone.

    @param request: STK Push request with phone, amount, invoice ID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns STK Push response with checkout request ID for tracking
    """
    config = get_daraja_config()
    if not config:
        return STKPushResponse(error="M-Pesa not configured. Set MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET, MPESA_SHORTCODE.")

    client = DarajaClient(config)
    result = await client.stk_push(
        STKPushRequest(
            phone_number=request.phone_number,
            amount=request.amount_kes,
            account_reference=request.invoice_id[:12],
            description=request.description,
        )
    )

    if result.success:
        logger.info(
            "stk_push_initiated",
            checkout_id=result.checkout_request_id,
            invoice_id=request.invoice_id,
            facility_id=str(current_user.facility_id),
        )

    return result


# ── STK Push Status Query ────────────────────────────────────────────────────


@router.get("/stk-status/{checkout_request_id}")
async def query_stk_status(
    checkout_request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> TransactionStatus:
    """
    Query the status of an STK Push transaction.

    @param checkout_request_id: Checkout request ID from STK Push response
    @param current_user: Authenticated user from JWT
    @returns Transaction status with result code
    """
    config = get_daraja_config()
    if not config:
        return TransactionStatus(result_code=-1, result_desc="M-Pesa not configured")

    client = DarajaClient(config)
    return await client.stk_query(checkout_request_id)


# ── STK Callback (Public — No Auth) ─────────────────────────────────────────


@router.post("/callback/stk")
async def stk_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Safaricom STK Push callback endpoint.
    Called by M-Pesa servers after customer completes payment.
    No auth required — Safaricom calls this directly.

    @param request: Raw HTTP request from Safaricom
    @param db: Database session
    @returns JSON acknowledgement
    """
    try:
        body = await request.json()
        callback_data = DarajaClient.parse_stk_callback(body)

        logger.info(
            "stk_callback_received",
            checkout_id=callback_data.checkout_request_id,
            result_code=callback_data.result_code,
            receipt=callback_data.mpesa_receipt,
        )

        if callback_data.result_code == 0 and callback_data.mpesa_receipt:
            # Payment successful — record in billing
            await _record_mpesa_payment(db, callback_data)

        return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})

    except Exception as exc:
        logger.error("stk_callback_error", error=str(exc))
        return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})


# ── C2B Validation Callback (Public — No Auth) ──────────────────────────────


@router.post("/callback/c2b/validate")
async def c2b_validation(request: Request) -> JSONResponse:
    """
    C2B validation callback — Safaricom asks if we accept this payment.
    Always accept (Completed response type configured during registration).

    @param request: Raw HTTP request from Safaricom
    @returns JSON validation response
    """
    body = await request.json()
    logger.info("c2b_validation", data=body)

    # Accept all payments (validation can be extended for amount/account checks)
    return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})


# ── C2B Confirmation Callback (Public — No Auth) ────────────────────────────


@router.post("/callback/c2b/confirm")
async def c2b_confirmation(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    C2B confirmation callback — customer paid via Paybill/Till.
    Record the payment against the referenced invoice.

    @param request: Raw HTTP request from Safaricom
    @param db: Database session
    @returns JSON confirmation response
    """
    try:
        body = await request.json()
        logger.info("c2b_confirmation", data=body)

        # Extract C2B fields
        receipt = body.get("TransID", "")
        amount = float(body.get("TransAmount", 0))
        phone = body.get("MSISDN", "")
        account_ref = body.get("BillRefNumber", "")

        if receipt and amount > 0:
            callback_data = STKCallbackData(
                merchant_request_id="C2B",
                checkout_request_id=f"C2B-{receipt}",
                result_code=0,
                result_desc="C2B Payment",
                amount=amount,
                mpesa_receipt=receipt,
                phone_number=phone,
            )
            await _record_mpesa_payment(db, callback_data, account_ref=account_ref)

        return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})

    except Exception as exc:
        logger.error("c2b_confirm_error", error=str(exc))
        return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})


# ── M-Pesa Status ───────────────────────────────────────────────────────────


@router.get("/status")
async def mpesa_status(
    current_user: CurrentUser = Depends(get_current_user),
) -> MPesaStatusResponse:
    """
    Check M-Pesa Daraja configuration status.

    @param current_user: Authenticated user from JWT
    @returns Configuration status
    """
    config = get_daraja_config()
    if not config:
        return MPesaStatusResponse(configured=False)

    return MPesaStatusResponse(
        configured=True,
        environment=config.environment,
        shortcode=config.shortcode,
    )


# ── Internal Helpers ─────────────────────────────────────────────────────────


async def _record_mpesa_payment(
    db: AsyncSession,
    callback: STKCallbackData,
    account_ref: str = "",
) -> None:
    """
    Record an M-Pesa payment in the billing system.
    Matches the payment to an invoice by reference number.

    @param db: Database session
    @param callback: Parsed M-Pesa callback data
    @param account_ref: Account reference from C2B (invoice number)
    """
    from app.models.billing import Invoice, Payment

    try:
        # Try to find invoice by reference
        if account_ref:
            from sqlalchemy import select
            result = await db.execute(
                select(Invoice).where(
                    Invoice.invoice_number == account_ref,
                    Invoice.is_deleted == False,  # noqa: E712
                )
            )
            invoice = result.scalar_one_or_none()

            if invoice:
                amount_cents = int((callback.amount or 0) * 100)
                payment = Payment(
                    invoice_id=invoice.id,
                    facility_id=invoice.facility_id,
                    patient_id=invoice.patient_id,
                    amount_cents=amount_cents,
                    payment_method="mpesa",
                    mpesa_transaction_id=callback.mpesa_receipt,
                    reference_number=callback.mpesa_receipt,
                    notes=f"M-Pesa payment from {callback.phone_number}",
                )
                db.add(payment)

                # Update invoice paid amount
                invoice.paid_amount_cents = (invoice.paid_amount_cents or 0) + amount_cents
                if invoice.paid_amount_cents >= invoice.total_amount_cents:
                    invoice.status = "paid"
                elif invoice.paid_amount_cents > 0:
                    invoice.status = "partially_paid"

                await db.commit()
                logger.info(
                    "mpesa_payment_recorded",
                    receipt=callback.mpesa_receipt,
                    invoice=invoice.invoice_number,
                    amount_cents=amount_cents,
                )
                return

        # No matching invoice — log as unmatched for reconciliation
        logger.warning(
            "mpesa_payment_unmatched",
            receipt=callback.mpesa_receipt,
            amount=callback.amount,
            phone=callback.phone_number,
            account_ref=account_ref,
        )

    except Exception as exc:
        logger.error(
            "mpesa_payment_record_error",
            receipt=callback.mpesa_receipt,
            error=str(exc),
        )
        await db.rollback()
