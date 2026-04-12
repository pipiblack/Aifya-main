import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.emergency import (
    AssignDoctorRequest,
    DispositionRequest,
    EmergencyListResponse,
    EmergencySummary,
    EmergencyVisitCreate,
    EmergencyVisitResponse,
    TriageRequest,
)
from app.services.emergency_service import EmergencyService

router = APIRouter(dependencies=[Depends(require_module("emergency"))])


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=EmergencySummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmergencySummary:
    """
    Get emergency department summary stats for today.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Emergency summary
    """
    service = EmergencyService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


# ── Queue ────────────────────────────────────────────────────────────────────


@router.get("/queue", response_model=EmergencyListResponse)
async def get_queue(
    queue_status: str | None = Query(None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmergencyListResponse:
    """
    Get emergency queue ordered by triage priority.

    @param queue_status: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Emergency queue list
    """
    service = EmergencyService(db)
    items = await service.get_queue(
        facility_id=current_user.facility_id,
        status=queue_status,
    )
    return EmergencyListResponse(items=items, total=len(items))


# ── Register ─────────────────────────────────────────────────────────────────


@router.post(
    "/visits",
    response_model=EmergencyVisitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_visit(
    data: EmergencyVisitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor", "nurse", "receptionist")
    ),
) -> EmergencyVisitResponse:
    """
    Register a new emergency visit.

    @param data: Visit registration data
    @param db: Database session
    @param current_user: Authenticated staff
    @returns Created emergency visit
    """
    service = EmergencyService(db)
    visit = await service.register_visit(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return EmergencyVisitResponse.model_validate(visit)


# ── Visit Detail ─────────────────────────────────────────────────────────────


@router.get("/visits/{visit_id}", response_model=EmergencyVisitResponse)
async def get_visit(
    visit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmergencyVisitResponse:
    """
    Get a single emergency visit by ID.

    @param visit_id: Visit UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Emergency visit details
    """
    service = EmergencyService(db)
    visit = await service.get_visit(
        visit_id=visit_id,
        facility_id=current_user.facility_id,
    )
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency visit not found",
        )
    return EmergencyVisitResponse.model_validate(visit)


# ── Triage ───────────────────────────────────────────────────────────────────


@router.post("/visits/{visit_id}/triage", response_model=EmergencyVisitResponse)
async def triage_visit(
    visit_id: uuid.UUID,
    data: TriageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor", "nurse")
    ),
) -> EmergencyVisitResponse:
    """
    Perform SATS triage on an emergency visit.

    @param visit_id: Visit UUID
    @param data: Triage data
    @param db: Database session
    @param current_user: Authenticated clinical staff
    @returns Updated visit
    """
    service = EmergencyService(db)
    visit = await service.triage(
        visit_id=visit_id,
        data=data,
        facility_id=current_user.facility_id,
        triaged_by=current_user.user_id,
    )
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency visit not found",
        )
    return EmergencyVisitResponse.model_validate(visit)


# ── Assign Doctor ────────────────────────────────────────────────────────────


@router.post("/visits/{visit_id}/assign-doctor", response_model=EmergencyVisitResponse)
async def assign_doctor(
    visit_id: uuid.UUID,
    data: AssignDoctorRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor", "nurse")
    ),
) -> EmergencyVisitResponse:
    """
    Assign a doctor to an emergency visit.

    @param visit_id: Visit UUID
    @param data: Doctor assignment data
    @param db: Database session
    @param current_user: Authenticated clinical staff
    @returns Updated visit
    """
    service = EmergencyService(db)
    visit = await service.assign_doctor(
        visit_id=visit_id,
        data=data,
        facility_id=current_user.facility_id,
        assigned_by=current_user.user_id,
    )
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency visit not found",
        )
    return EmergencyVisitResponse.model_validate(visit)


# ── Disposition ──────────────────────────────────────────────────────────────


@router.post("/visits/{visit_id}/disposition", response_model=EmergencyVisitResponse)
async def record_disposition(
    visit_id: uuid.UUID,
    data: DispositionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor")
    ),
) -> EmergencyVisitResponse:
    """
    Record disposition for an emergency visit.

    @param visit_id: Visit UUID
    @param data: Disposition data
    @param db: Database session
    @param current_user: Authenticated doctor/admin
    @returns Updated visit
    """
    service = EmergencyService(db)
    visit = await service.record_disposition(
        visit_id=visit_id,
        data=data,
        facility_id=current_user.facility_id,
        disposed_by=current_user.user_id,
    )
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency visit not found",
        )
    return EmergencyVisitResponse.model_validate(visit)
