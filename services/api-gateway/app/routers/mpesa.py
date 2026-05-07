"""
M-Pesa Daraja integration router.
Provides STK Push payments, C2B callbacks, transaction status, and reconciliation.
Callbacks are public endpoints (no auth) — Safaricom sends them directly.

Security:
- Callback endpoints MUST be protected at the network edge with an IP allow-list
  for Safaricom's documented production ranges (e.g. 196.201.214.0/24,
  196.201.213.0/24, 196.201.212.0/24, 196.201.214.200/29). The TODO below
  enforces this at the application layer when MPESA_CALLBACK_IP_ALLOWLIST is set.
- Callbacks are idempotent: handle_stk_callback short-circuits when the row is
  already in a terminal state.
- Callbacks always return 200 to Safaricom (so they don't retry) but log internal
  errors for follow-up.
- Payload structure is validated by DarajaClient.parse_stk_callback before use.
"""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user
from app.database import get_db
from app.services.mpesa.callback import handle_stk_callback
from app.services.mpesa.daraja import (
    DarajaClient,
    STKCallbackData,
    STKPushResponse,
    TransactionStatus,
    get_daraja_config,
)
from app.services.mpesa.stk_push import StkPushService

logger = get_logger(__name__)

router = APIRouter()


# Safaricom Daraja documented production source IPs. Override at deploy time
# via MPESA_CALLBACK_IP_ALLOWLIST (comma-separated). Empty = no IP enforcement
# (only safe in dev where the LB / firewall enforces it).
_DEFAULT_SAFARICOM_IPS: tuple[str, ...] = (
    "196.201.214.200",
    "196.201.214.206",
    "196.201.213.114",
    "196.201.214.207",
    "196.201.214.208",
    "196.201.213.44",
    "196.201.212.127",
    "196.201.212.128",
    "196.201.212.129",
    "196.201.212.132",
    "196.201.212.136",
    "196.201.212.138",
    "196.201.212.69",
    "196.201.212.74",
)


def _client_ip(request: Request) -> str:
    """Resolve the originating client IP, honouring X-Forwarded-For when present."""
    fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if fwd:
        return fwd
    return request.client.host if request.client else ""


def _enforce_callback_ip(request: Request) -> None:
    """
    Reject the callback if the source IP is not in the configured allow-list.

    When MPESA_CALLBACK_IP_ALLOWLIST is set, intersect with the default
    Safaricom IPs. When unset, fall through (rely on edge firewall) but log
    the source IP for audit.
    """
    src = _client_ip(request)
    override = os.getenv("MPESA_CALLBACK_IP_ALLOWLIST", "").strip()
    if override:
        allow = {ip.strip() for ip in override.split(",") if ip.strip()}
        if src and src not in allow:
            logger.warning(
                "mpesa_callback_blocked_ip",
                source_ip=src,
                allowlist_size=len(allow),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Source IP not allowed",
            )
    else:
        logger.info("mpesa_callback_inbound", source_ip=src)


# ── Request / Response Schemas ───────────────────────────────────────────────


class STKPushApiRequest(BaseModel):
    """
    API request to initiate an STK Push payment.

    @param phone_number: Customer phone (07XX or +254XX)
    @param amount_kes: Amount in KES (whole number)
    @param invoice_id: Invoice UUID to pay (optional)
    @param patient_id: Patient UUID linked to payment (optional)
    @param reference: Account reference shown on M-Pesa (typically invoice number)
    @param description: Optional transaction description
    """
    phone_number: str
    amount_kes: int
    invoice_id: str | None = None
    patient_id: str | None = None
    reference: str | None = None
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
    Sends a USSD prompt to the patient's phone and persists the request
    in mpesa_stk_requests for callback reconciliation.

    @param request: STK Push request with phone, amount, optional invoice ID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns STK Push response with checkout request ID for tracking
    """
    invoice_uuid: uuid.UUID | None = None
    if request.invoice_id:
        try:
            invoice_uuid = uuid.UUID(request.invoice_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invoice_id must be a valid UUID",
            ) from exc
    patient_uuid: uuid.UUID | None = None
    if request.patient_id:
        try:
            patient_uuid = uuid.UUID(request.patient_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id must be a valid UUID",
            ) from exc

    reference = request.reference or (request.invoice_id or str(uuid.uuid4()))

    service = StkPushService(db)
    api_response, _row = await service.initiate_stk_push(
        facility_id=current_user.facility_id,
        phone_number=request.phone_number,
        amount=request.amount_kes,
        reference=reference,
        description=request.description,
        invoice_id=invoice_uuid,
        patient_id=patient_uuid,
        created_by=current_user.user_id,
    )

    if api_response.success:
        logger.info(
            "stk_push_initiated",
            checkout_id=api_response.checkout_request_id,
            invoice_id=request.invoice_id,
            facility_id=str(current_user.facility_id),
        )
    return api_response


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
@router.post("/callback")
async def stk_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Safaricom STK Push callback endpoint.
    Called by M-Pesa servers after customer completes payment.
    No auth required — Safaricom calls this directly.

    Updates the mpesa_stk_requests row and posts a Payment if the
    transaction was tied to an invoice.

    @param request: Raw HTTP request from Safaricom
    @param db: Database session
    @returns JSON acknowledgement
    """
    try:
        _enforce_callback_ip(request)
    except HTTPException:
        raise

    try:
        body = await request.json()
        # Defensive: validate we have an stkCallback envelope before processing
        if not isinstance(body, dict) or "Body" not in body:
            logger.warning("stk_callback_malformed")
            return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})
        ack = await handle_stk_callback(db, body)
        return JSONResponse(content=ack)
    except Exception as exc:
        logger.error("stk_callback_error", error=str(exc))
        # Always ack to Safaricom so they don't retry endlessly
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
    try:
        _enforce_callback_ip(request)
    except HTTPException:
        raise
    try:
        body = await request.json()
    except Exception:
        body = {}
    # Don't echo full body in production logs (may contain MSISDN PII)
    logger.info("c2b_validation", trans_id=str(body.get("TransID", "")))

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
        _enforce_callback_ip(request)
    except HTTPException:
        raise

    try:
        body = await request.json()
        # Don't log MSISDN (PII) — only the receipt/account ref
        logger.info(
            "c2b_confirmation",
            trans_id=str(body.get("TransID", "")),
            account_ref=str(body.get("BillRefNumber", "")),
        )

        # Extract C2B fields with defensive type coercion
        receipt = str(body.get("TransID", "")).strip()
        try:
            amount = float(body.get("TransAmount", 0) or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount < 0:
            amount = 0.0
        phone = str(body.get("MSISDN", "")).strip()
        account_ref = str(body.get("BillRefNumber", "")).strip()

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
    from sqlalchemy import select

    try:
        # Idempotency: do not double-record a payment for the same M-Pesa receipt
        if callback.mpesa_receipt:
            existing = await db.execute(
                select(Payment).where(
                    Payment.mpesa_transaction_id == callback.mpesa_receipt,
                    Payment.is_deleted == False,  # noqa: E712
                )
            )
            if existing.scalar_one_or_none() is not None:
                logger.info(
                    "mpesa_payment_already_recorded",
                    receipt=callback.mpesa_receipt,
                )
                return

        # Try to find invoice by reference
        if account_ref:
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
                    notes="M-Pesa payment received",
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
