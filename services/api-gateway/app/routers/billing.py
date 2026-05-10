import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.billing import (
    BillingSummary,
    InvoiceCreate,
    InvoiceDetail,
    InvoiceItemResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceWaiveRequest,
    PaymentCreate,
    PaymentResponse,
)
from app.services.billing_service import BillingService

router = APIRouter(dependencies=[Depends(require_module("billing"))])


# ── Dashboard Summary ─────────────────────────────────────────────────────────


@router.get("/summary", response_model=BillingSummary)
async def get_billing_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BillingSummary:
    """
    Get billing dashboard summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Billing summary with counts and totals
    """
    service = BillingService(db)
    return await service.get_summary(current_user.facility_id)


# ── Invoice List ──────────────────────────────────────────────────────────────


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    status_filter: str | None = Query(None, alias="status"),
    patient_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InvoiceListResponse:
    """
    List invoices with optional filtering and pagination.

    @param status_filter: Filter by invoice status
    @param patient_id: Filter by patient
    @param page: Page number
    @param page_size: Items per page
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Paginated invoice list
    """
    service = BillingService(db)
    items, total = await service.get_invoices(
        facility_id=current_user.facility_id,
        status_filter=status_filter,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
    )
    return InvoiceListResponse(items=items, total=total, page=page, page_size=page_size)


# ── Create Invoice ────────────────────────────────────────────────────────────


@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice(
    data: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("billing_clerk", "cashier", "admin", "facility_admin")),
    x_idempotency_key: str | None = Header(None),
) -> InvoiceResponse:
    """
    Create a new invoice with line items.

    @param data: Invoice data with items
    @param db: Database session
    @param current_user: Authenticated billing staff
    @param x_idempotency_key: Optional idempotency key
    @returns Created invoice
    """
    service = BillingService(db)
    invoice = await service.create_invoice(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return InvoiceResponse.model_validate(invoice)


# ── Invoice Detail ────────────────────────────────────────────────────────────


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
async def get_invoice_detail(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InvoiceDetail:
    """
    Get invoice with all line items and patient info.

    @param invoice_id: Invoice UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Full invoice detail
    """
    service = BillingService(db)
    invoice, items, patient_name, patient_mrn = await service.get_invoice_detail(
        invoice_id=invoice_id,
        facility_id=current_user.facility_id,
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return InvoiceDetail(
        invoice=InvoiceResponse.model_validate(invoice),
        items=[InvoiceItemResponse.model_validate(i) for i in items],
        patient_name=patient_name,
        patient_mrn=patient_mrn,
    )


# ── Finalize Invoice ─────────────────────────────────────────────────────────


@router.post(
    "/invoices/{invoice_id}/finalize",
    response_model=InvoiceResponse,
)
async def finalize_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("billing_clerk", "cashier", "admin", "facility_admin")),
) -> InvoiceResponse:
    """
    Finalize a draft invoice (locks for payment collection).

    @param invoice_id: Invoice UUID
    @param db: Database session
    @param current_user: Authenticated billing staff
    @returns Finalized invoice
    """
    service = BillingService(db)
    try:
        invoice = await service.finalize_invoice(
            invoice_id=invoice_id,
            facility_id=current_user.facility_id,
            finalized_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return InvoiceResponse.model_validate(invoice)


# ── Record Payment ────────────────────────────────────────────────────────────


@router.post(
    "/invoices/{invoice_id}/pay",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_payment(
    invoice_id: uuid.UUID,
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("billing_clerk", "cashier", "admin", "facility_admin")),
    x_idempotency_key: str | None = Header(None),
) -> PaymentResponse:
    """
    Record a payment against an invoice. Supports partial payments.

    @param invoice_id: Invoice UUID
    @param data: Payment data
    @param db: Database session
    @param current_user: Authenticated cashier / billing staff
    @param x_idempotency_key: Optional idempotency key
    @returns Created payment record
    """
    service = BillingService(db)
    try:
        payment = await service.record_payment(
            invoice_id=invoice_id,
            data=data,
            facility_id=current_user.facility_id,
            received_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return PaymentResponse.model_validate(payment)


# ── Waive Invoice ─────────────────────────────────────────────────────────────


@router.post(
    "/invoices/{invoice_id}/waive",
    response_model=InvoiceResponse,
)
async def waive_invoice(
    invoice_id: uuid.UUID,
    data: InvoiceWaiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("admin", "facility_admin")),
) -> InvoiceResponse:
    """
    Waive remaining balance on an invoice (exemption/charity).
    Restricted to admin roles.

    @param invoice_id: Invoice UUID
    @param data: Waiver reason
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Updated invoice
    """
    service = BillingService(db)
    invoice = await service.waive_invoice(
        invoice_id=invoice_id,
        facility_id=current_user.facility_id,
        waived_by=current_user.user_id,
        reason=data.reason,
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return InvoiceResponse.model_validate(invoice)
