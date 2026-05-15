"""Supplier invoicing router (Accounts Payable side of billing).

All endpoints are scoped to the caller's facility_id (extracted from the JWT).
Approve & pay actions post double-entry transactions to the GL via
``app.services.finance.post_compound_transaction``.
"""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.supplier_invoice import (
    SupplierExtCreate,
    SupplierExtListResponse,
    SupplierExtResponse,
    SupplierInvoiceCreate,
    SupplierInvoiceListItem,
    SupplierInvoiceListResponse,
    SupplierInvoicePaymentRequest,
    SupplierInvoiceResponse,
    SupplierInvoiceUpdate,
    SupplierUpdate,
)
from app.services.supplier_invoice_service import (
    SupplierInvoiceError,
    SupplierInvoiceService,
)

router = APIRouter(dependencies=[Depends(require_module("billing"))])


# ── Supplier CRUD ────────────────────────────────────────────────────────────


@router.get("/suppliers", response_model=SupplierExtListResponse)
async def list_suppliers(
    search: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupplierExtListResponse:
    """List suppliers (paginated, optional name search)."""
    service = SupplierInvoiceService(db)
    items, total = await service.list_suppliers(
        facility_id=current_user.facility_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return SupplierExtListResponse(
        items=[SupplierExtResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/suppliers",
    response_model=SupplierExtResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier(
    data: SupplierExtCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "finance_admin", "procurement")
    ),
) -> SupplierExtResponse:
    """Create a new supplier."""
    service = SupplierInvoiceService(db)
    supplier = await service.create_supplier(
        data=data, facility_id=current_user.facility_id, user_id=current_user.user_id
    )
    return SupplierExtResponse.model_validate(supplier)


@router.get("/suppliers/{supplier_id}", response_model=SupplierExtResponse)
async def get_supplier(
    supplier_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupplierExtResponse:
    """Fetch a single supplier."""
    service = SupplierInvoiceService(db)
    supplier = await service.get_supplier(supplier_id, current_user.facility_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return SupplierExtResponse.model_validate(supplier)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierExtResponse)
async def update_supplier(
    supplier_id: uuid.UUID,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "finance_admin", "procurement")
    ),
) -> SupplierExtResponse:
    """Update an existing supplier."""
    service = SupplierInvoiceService(db)
    supplier = await service.update_supplier(
        supplier_id=supplier_id,
        data=data,
        facility_id=current_user.facility_id,
        user_id=current_user.user_id,
    )
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return SupplierExtResponse.model_validate(supplier)


@router.get("/suppliers/{supplier_id}/invoices", response_model=SupplierInvoiceListResponse)
async def list_invoices_for_supplier(
    supplier_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupplierInvoiceListResponse:
    """List invoices for one supplier."""
    service = SupplierInvoiceService(db)
    items, total = await service.list_invoices(
        facility_id=current_user.facility_id,
        supplier_id=supplier_id,
        page=page,
        page_size=page_size,
    )
    return SupplierInvoiceListResponse(
        items=[SupplierInvoiceListItem.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ── Supplier Invoice CRUD ────────────────────────────────────────────────────


@router.get("/supplier-invoices", response_model=SupplierInvoiceListResponse)
async def list_supplier_invoices(
    status_filter: str | None = Query(None, alias="status"),
    supplier_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupplierInvoiceListResponse:
    """List supplier invoices (paginated, optional status/supplier filter)."""
    service = SupplierInvoiceService(db)
    items, total = await service.list_invoices(
        facility_id=current_user.facility_id,
        status_filter=status_filter,
        supplier_id=supplier_id,
        page=page,
        page_size=page_size,
    )
    return SupplierInvoiceListResponse(
        items=[SupplierInvoiceListItem.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/supplier-invoices",
    response_model=SupplierInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier_invoice(
    data: SupplierInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "finance_admin", "billing_clerk", "procurement")
    ),
    x_idempotency_key: str | None = Header(None),  # noqa: ARG001 - reserved for future idempotency
) -> SupplierInvoiceResponse:
    """Create a new draft supplier invoice with lines."""
    service = SupplierInvoiceService(db)
    try:
        return await service.create_invoice(
            data=data, facility_id=current_user.facility_id, user_id=current_user.user_id
        )
    except SupplierInvoiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/supplier-invoices/{invoice_id}", response_model=SupplierInvoiceResponse)
async def get_supplier_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupplierInvoiceResponse:
    """Fetch a single supplier invoice (with lines)."""
    service = SupplierInvoiceService(db)
    invoice = await service.get_invoice(invoice_id, current_user.facility_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier invoice not found")
    return invoice


@router.patch("/supplier-invoices/{invoice_id}", response_model=SupplierInvoiceResponse)
async def update_supplier_invoice(
    invoice_id: uuid.UUID,
    data: SupplierInvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "finance_admin", "billing_clerk", "procurement")
    ),
) -> SupplierInvoiceResponse:
    """Patch a draft supplier invoice."""
    service = SupplierInvoiceService(db)
    try:
        invoice = await service.update_invoice(
            invoice_id=invoice_id,
            data=data,
            facility_id=current_user.facility_id,
            user_id=current_user.user_id,
        )
    except SupplierInvoiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier invoice not found")
    return invoice


# ── Lifecycle actions ────────────────────────────────────────────────────────


@router.post("/supplier-invoices/{invoice_id}/approve", response_model=SupplierInvoiceResponse)
async def approve_supplier_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("finance_admin", "admin", "facility_admin")),
    x_idempotency_key: str | None = Header(None),
) -> SupplierInvoiceResponse:
    """Approve and post a supplier invoice to the GL (finance_admin only)."""
    service = SupplierInvoiceService(db)
    try:
        return await service.approve_invoice(
            invoice_id=invoice_id,
            facility_id=current_user.facility_id,
            user_id=current_user.user_id,
            idempotency_key=x_idempotency_key,
        )
    except SupplierInvoiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/supplier-invoices/{invoice_id}/pay", response_model=SupplierInvoiceResponse)
async def pay_supplier_invoice(
    invoice_id: uuid.UUID,
    payment: SupplierInvoicePaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("finance_admin", "admin", "facility_admin")),
    x_idempotency_key: str | None = Header(None),
) -> SupplierInvoiceResponse:
    """Record a payment against an approved supplier invoice."""
    service = SupplierInvoiceService(db)
    try:
        return await service.pay_invoice(
            invoice_id=invoice_id,
            payment=payment,
            facility_id=current_user.facility_id,
            user_id=current_user.user_id,
            idempotency_key=x_idempotency_key,
        )
    except SupplierInvoiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/supplier-invoices/{invoice_id}/cancel", response_model=SupplierInvoiceResponse)
async def cancel_supplier_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("finance_admin", "admin", "facility_admin", "billing_clerk")
    ),
) -> SupplierInvoiceResponse:
    """Cancel a draft supplier invoice. Approved invoices cannot be cancelled."""
    service = SupplierInvoiceService(db)
    try:
        return await service.cancel_invoice(
            invoice_id=invoice_id,
            facility_id=current_user.facility_id,
            user_id=current_user.user_id,
        )
    except SupplierInvoiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
