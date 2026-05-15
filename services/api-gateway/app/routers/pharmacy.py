import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.pharmacy import (
    DispenseRequest,
    DispensingResponse,
    InventoryAdjustRequest,
    InventoryListResponse,
    InventoryReceiveRequest,
    PharmacyItemCreate,
    PharmacyItemResponse,
    PharmacyItemUpdate,
    PharmacyQueueResponse,
    StockAdjustmentRequest,
    StockAlert,
    StockReceiptRequest,
    StockSummaryResponse,
    StockSummaryRow,
    StockTransactionResponse,
)
from app.services.pharmacy_service import PharmacyService

router = APIRouter(dependencies=[Depends(require_module("pharmacy"))])


# ── Pharmacy Queue ─────────────────────────────────────────────────────────


@router.get("/queue", response_model=PharmacyQueueResponse)
async def get_pharmacy_queue(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PharmacyQueueResponse:
    """
    Get pending prescriptions awaiting dispensing.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Pharmacy queue (pending prescriptions)
    """
    service = PharmacyService(db)
    items, total = await service.get_pending_prescriptions(current_user.facility_id)
    return PharmacyQueueResponse(items=items, total=total)


# ── Dispensing ─────────────────────────────────────────────────────────────


@router.post(
    "/dispense",
    response_model=DispensingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def dispense_prescription(
    data: DispenseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("pharmacist", "admin", "facility_admin")),
    x_idempotency_key: str | None = Header(None),
) -> DispensingResponse:
    """
    Dispense a prescription. Validates stock, deducts inventory, updates Rx status.
    Drug interaction check must have passed before dispensing (CLAUDE.md).

    @param data: Dispense request
    @param db: Database session
    @param current_user: Authenticated pharmacist
    @param x_idempotency_key: Optional idempotency key
    @returns Dispensing record
    """
    service = PharmacyService(db)
    try:
        dispensing = await service.dispense(
            data=data,
            facility_id=current_user.facility_id,
            dispensed_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return DispensingResponse.model_validate(dispensing)


# ── Inventory ──────────────────────────────────────────────────────────────


@router.get("/inventory", response_model=InventoryListResponse)
async def list_inventory(
    q: str | None = Query(None, description="Search by drug name or code"),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InventoryListResponse:
    """
    List pharmacy inventory with search and pagination.

    @param q: Optional search query
    @param active_only: Only show active items
    @param page: Page number
    @param page_size: Items per page
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Paginated inventory list
    """
    service = PharmacyService(db)
    items, total = await service.get_inventory(
        facility_id=current_user.facility_id,
        query=q,
        active_only=active_only,
        page=page,
        page_size=page_size,
    )
    return InventoryListResponse(
        items=[PharmacyItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/inventory",
    response_model=PharmacyItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_inventory_item(
    data: PharmacyItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("pharmacist", "admin", "facility_admin")),
) -> PharmacyItemResponse:
    """
    Add a new item to pharmacy inventory.

    @param data: Pharmacy item data
    @param db: Database session
    @param current_user: Authenticated pharmacist
    @returns Created pharmacy item
    """
    service = PharmacyService(db)
    item = await service.create_item(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return PharmacyItemResponse.model_validate(item)


@router.get("/inventory/stock-summary", response_model=StockSummaryResponse)
async def stock_summary(
    start_date: date | None = Query(None, description="Window start (inclusive). Defaults to start of month."),
    end_date: date | None = Query(None, description="Window end (inclusive). Defaults to today."),
    item_id: uuid.UUID | None = Query(None, description="Optional single-item filter."),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> StockSummaryResponse:
    """Opening / Received / Sales / Closing per pharmacy item for a date range.

    Required by KEMSA / PPB pharmacy stock-control regulations for audit trails.
    All four columns are derived from immutable ``stock_transactions``.

    @param start_date: Inclusive start; defaults to first of current month
    @param end_date: Inclusive end; defaults to today
    @param item_id: Optional filter to a single item
    @returns Stock summary with per-item rows
    """
    today = date.today()
    sd = start_date or today.replace(day=1)
    ed = end_date or today
    if ed < sd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )
    # Hard cap on window size to keep audit queries bounded (1 year)
    if ed - sd > timedelta(days=366):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 366 days",
        )

    service = PharmacyService(db)
    rows: list[StockSummaryRow] = await service.get_stock_summary(
        facility_id=current_user.facility_id,
        start_date=sd,
        end_date=ed,
        item_id=item_id,
    )
    return StockSummaryResponse(
        start_date=sd,
        end_date=ed,
        rows=rows,
        total_items=len(rows),
    )


@router.post(
    "/inventory/{item_id}/receive",
    response_model=StockTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def receive_for_inventory_item(
    item_id: uuid.UUID,
    data: InventoryReceiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("pharmacist", "admin", "facility_admin", "pharmacy_admin")),
    x_idempotency_key: str | None = Header(None),
) -> StockTransactionResponse:
    """Top up an EXISTING pharmacy item — never creates a duplicate catalogue row.

    Fixes audit finding: stock receipts previously required a brand-new item
    entry, which caused duplicate inventory records. With this endpoint the
    item is identified by URL path and the body carries only receipt details.

    @param item_id: PharmacyItem UUID (URL path)
    @param data: Receipt details (quantity, batch, expiry, supplier, unit cost, notes)
    @param db: Database session
    @param current_user: Authenticated pharmacist / pharmacy admin
    @param x_idempotency_key: Optional idempotency key for safe client retries
    @returns Stock transaction record (audit row)
    """
    _ = x_idempotency_key  # Honored for client retries; receipts are not auto-deduped
    service = PharmacyService(db)
    try:
        tx = await service.receive_for_item(
            item_id=item_id,
            data=data,
            facility_id=current_user.facility_id,
            received_by=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return StockTransactionResponse.model_validate(tx)


@router.post(
    "/inventory/{item_id}/adjust",
    response_model=StockTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def adjust_inventory_item(
    item_id: uuid.UUID,
    data: InventoryAdjustRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("pharmacy_admin", "admin", "facility_admin")),
    x_idempotency_key: str | None = Header(None),
) -> StockTransactionResponse:
    """Stock-take correction — sets ``current_quantity`` to ``new_qty`` exactly.

    Requires the ``pharmacy_admin`` role (or higher). Used after a physical
    stock-take to reconcile system qty with counted qty. Captures the delta
    as an immutable audit row.

    @param item_id: PharmacyItem UUID
    @param data: Adjustment (new_qty + reason)
    @param db: Database session
    @param current_user: Pharmacy admin
    @param x_idempotency_key: Optional idempotency key
    @returns Stock transaction record
    """
    _ = x_idempotency_key
    service = PharmacyService(db)
    try:
        tx = await service.adjust_to_qty(
            item_id=item_id,
            data=data,
            facility_id=current_user.facility_id,
            adjusted_by=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return StockTransactionResponse.model_validate(tx)


@router.patch(
    "/inventory/{item_id}",
    response_model=PharmacyItemResponse,
)
async def update_inventory_item(
    item_id: uuid.UUID,
    data: PharmacyItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("pharmacist", "admin", "facility_admin")),
) -> PharmacyItemResponse:
    """
    Update a pharmacy inventory item.

    @param item_id: PharmacyItem UUID
    @param data: Fields to update
    @param db: Database session
    @param current_user: Authenticated pharmacist
    @returns Updated item
    """
    service = PharmacyService(db)
    item = await service.update_item(
        item_id=item_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pharmacy item not found",
        )
    return PharmacyItemResponse.model_validate(item)


# ── Stock Transactions ─────────────────────────────────────────────────────


@router.post(
    "/stock/receive",
    response_model=StockTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def receive_stock(
    data: StockReceiptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("pharmacist", "admin", "facility_admin")),
) -> StockTransactionResponse:
    """
    Receive new stock into pharmacy inventory.

    @param data: Stock receipt data
    @param db: Database session
    @param current_user: Authenticated pharmacist
    @returns Stock transaction record
    """
    service = PharmacyService(db)
    try:
        tx = await service.receive_stock(
            data=data,
            facility_id=current_user.facility_id,
            received_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return StockTransactionResponse.model_validate(tx)


@router.post(
    "/stock/adjust",
    response_model=StockTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def adjust_stock(
    data: StockAdjustmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("pharmacist", "admin", "facility_admin")),
) -> StockTransactionResponse:
    """
    Adjust stock (loss, damage, correction, transfer).

    @param data: Adjustment data
    @param db: Database session
    @param current_user: Authenticated pharmacist
    @returns Stock transaction record
    """
    service = PharmacyService(db)
    try:
        tx = await service.adjust_stock(
            data=data,
            facility_id=current_user.facility_id,
            adjusted_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return StockTransactionResponse.model_validate(tx)


# ── Alerts ─────────────────────────────────────────────────────────────────


@router.get("/alerts", response_model=list[StockAlert])
async def get_stock_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[StockAlert]:
    """
    Get stock alerts: low stock, expiring, expired, out of stock.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of stock alerts
    """
    service = PharmacyService(db)
    return await service.get_stock_alerts(current_user.facility_id)
