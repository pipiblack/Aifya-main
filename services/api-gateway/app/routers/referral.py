import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.referral import (
    ReferralCreate,
    ReferralListResponse,
    ReferralResponse,
    ReferralSummary,
    ReferralUpdateStatus,
)
from app.services.referral_service import ReferralService

router = APIRouter(dependencies=[Depends(require_module("referrals"))])


@router.get("/summary", response_model=ReferralSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReferralSummary:
    """
    Get referral summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Referral summary
    """
    service = ReferralService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


@router.get("", response_model=ReferralListResponse)
async def list_referrals(
    direction: str | None = Query(None, description="Filter by direction"),
    ref_status: str | None = Query(None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReferralListResponse:
    """
    Get referrals.

    @param direction: Optional direction filter
    @param ref_status: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Referral list
    """
    service = ReferralService(db)
    items = await service.get_referrals(
        facility_id=current_user.facility_id,
        direction=direction,
        status=ref_status,
    )
    return ReferralListResponse(items=items, total=len(items))


@router.post("", response_model=ReferralResponse, status_code=status.HTTP_201_CREATED)
async def create_referral(
    data: ReferralCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor")
    ),
) -> ReferralResponse:
    """
    Create a referral.

    @param data: Referral data
    @param db: Database session
    @param current_user: Authenticated doctor/admin
    @returns Created referral
    """
    service = ReferralService(db)
    referral = await service.create_referral(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return ReferralResponse.model_validate(referral)


@router.get("/{referral_id}", response_model=ReferralResponse)
async def get_referral(
    referral_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReferralResponse:
    """
    Get a single referral.

    @param referral_id: Referral UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Referral details
    """
    service = ReferralService(db)
    referral = await service.get_referral(referral_id, current_user.facility_id)
    if not referral:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")
    return ReferralResponse.model_validate(referral)


@router.post("/{referral_id}/status", response_model=ReferralResponse)
async def update_referral_status(
    referral_id: uuid.UUID,
    data: ReferralUpdateStatus,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor")
    ),
) -> ReferralResponse:
    """
    Update referral status.

    @param referral_id: Referral UUID
    @param data: Status update data
    @param db: Database session
    @param current_user: Authenticated doctor/admin
    @returns Updated referral
    """
    service = ReferralService(db)
    referral = await service.update_status(
        referral_id=referral_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if not referral:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral not found")
    return ReferralResponse.model_validate(referral)
