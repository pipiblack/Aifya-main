import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module, require_patient_capacity
from app.database import get_db
from app.schemas.event import EventResponse, TimelineResponse
from app.schemas.insurance import (
    PatientInsuranceCreate,
    PatientInsuranceListResponse,
    PatientInsuranceResponse,
    PatientInsuranceUpdate,
)
from app.schemas.patient import (
    PatientCreate,
    PatientListResponse,
    PatientResponse,
    PatientUpdate,
)
from app.services.event_service import EventService
from app.services.insurance_service import InsuranceService
from app.services.patient_service import PatientService

router = APIRouter(dependencies=[Depends(require_module("patients"))])

# Admin-level roles allowed to edit patient records (per audit 2026-05-14).
PATIENT_EDIT_ROLES = ("admin", "facility_admin", "records_admin")


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_patient_capacity())],
)
async def register_patient(
    data: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    x_idempotency_key: str | None = Header(None),
) -> PatientResponse:
    """
    Register a new patient.

    @param data: Patient registration data (validated by Pydantic)
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @param x_idempotency_key: Optional idempotency key for safe retries
    @returns Created patient
    """
    service = PatientService(db)
    patient = await service.register_patient(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
        idempotency_key=x_idempotency_key,
    )
    return PatientResponse.model_validate(patient)


@router.get("", response_model=PatientListResponse)
async def list_patients(
    q: str | None = Query(None, description="Search by name, ID, phone, or MRN"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PatientListResponse:
    """
    Search and list patients with pagination.

    @param q: Optional search query
    @param page: Page number (1-based)
    @param page_size: Number of results per page
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Paginated list of patients
    """
    service = PatientService(db)
    patients, total = await service.search_patients(
        facility_id=current_user.facility_id,
        query=q,
        page=page,
        page_size=page_size,
    )
    return PatientListResponse(
        items=[PatientResponse.model_validate(p) for p in patients],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PatientResponse:
    """
    Get a single patient by ID.

    @param patient_id: Patient UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Patient details
    """
    service = PatientService(db)
    patient = await service.get_patient(patient_id, current_user.facility_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return PatientResponse.model_validate(patient)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: uuid.UUID,
    data: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*PATIENT_EDIT_ROLES)),
    x_idempotency_key: str | None = Header(None),
) -> PatientResponse:
    """
    Update patient demographics. Restricted to admin-level roles
    (admin, facility_admin, records_admin) per the 2026-05-14 audit.

    Every edit is logged to the immutable event store via the
    `PatientUpdated` event — this is the audit trail.

    @param patient_id: Patient UUID
    @param data: Fields to update
    @param db: Database session
    @param current_user: Authenticated admin from JWT (RBAC enforced)
    @param x_idempotency_key: Optional idempotency key
    @returns Updated patient
    """
    service = PatientService(db)
    patient = await service.update_patient(
        patient_id=patient_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
        idempotency_key=x_idempotency_key,
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    return PatientResponse.model_validate(patient)


@router.get("/{patient_id}/timeline", response_model=TimelineResponse)
async def get_patient_timeline(
    patient_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TimelineResponse:
    """
    Get the event timeline for a patient.

    @param patient_id: Patient UUID
    @param limit: Max events to return
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Event timeline
    """
    event_service = EventService(db)
    events, total = await event_service.get_patient_timeline(
        patient_id=patient_id,
        facility_id=current_user.facility_id,
        limit=limit,
    )
    return TimelineResponse(
        items=[EventResponse.model_validate(e) for e in events],
        total=total,
    )


# ── Multi-insurance endpoints (audit 2026-05-14) ─────────────────────────────


@router.get(
    "/{patient_id}/insurances",
    response_model=PatientInsuranceListResponse,
)
async def list_patient_insurances(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PatientInsuranceListResponse:
    """
    List all insurance entries for a patient. A patient may hold multiple
    insurance memberships (e.g. SHA + a private insurer). Exactly one entry
    is marked primary.

    @param patient_id: Patient UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Insurance entries, primary first
    """
    service = InsuranceService(db)
    items = await service.list_patient_insurances(
        patient_id=patient_id,
        facility_id=current_user.facility_id,
    )
    return PatientInsuranceListResponse(items=items, total=len(items))


@router.post(
    "/{patient_id}/insurances",
    response_model=PatientInsuranceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_patient_insurance(
    patient_id: uuid.UUID,
    data: PatientInsuranceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    x_idempotency_key: str | None = Header(None),  # noqa: ARG001
) -> PatientInsuranceResponse:
    """
    Add a new insurance entry to a patient. If `is_primary=true` (or the
    patient has no primary yet), the entry is set as primary and any prior
    primary is demoted. The patient's legacy insurance columns are kept in
    sync with the primary entry.

    @param patient_id: Patient UUID
    @param data: Insurance entry data
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @param x_idempotency_key: Optional idempotency key
    @returns Newly created insurance entry
    """
    service = InsuranceService(db)
    try:
        entry = await service.add_patient_insurance(
            patient_id=patient_id,
            data=data,
            facility_id=current_user.facility_id,
            created_by=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    items = await service.list_patient_insurances(
        patient_id=patient_id, facility_id=current_user.facility_id
    )
    for item in items:
        if item.id == entry.id:
            return item
    # Fallback (shouldn't hit) — synthesise response without scheme join
    return PatientInsuranceResponse(
        id=entry.id,
        patient_id=entry.patient_id,
        scheme_id=entry.scheme_id,
        member_number=entry.member_number,
        principal_name=entry.principal_name,
        relationship=entry.relationship,
        valid_from=entry.valid_from,
        valid_to=entry.valid_to,
        is_active=entry.is_active,
        is_primary=entry.is_primary,
        notes=entry.notes,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.patch(
    "/{patient_id}/insurances/{insurance_id}",
    response_model=PatientInsuranceResponse,
)
async def update_patient_insurance(
    patient_id: uuid.UUID,
    insurance_id: uuid.UUID,
    data: PatientInsuranceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PatientInsuranceResponse:
    """
    Edit an existing insurance entry.

    @param patient_id: Patient UUID
    @param insurance_id: Insurance entry UUID
    @param data: Fields to update
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Updated entry
    """
    service = InsuranceService(db)
    try:
        entry = await service.update_patient_insurance(
            insurance_id=insurance_id,
            patient_id=patient_id,
            data=data,
            facility_id=current_user.facility_id,
            updated_by=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insurance entry not found",
        )

    items = await service.list_patient_insurances(
        patient_id=patient_id, facility_id=current_user.facility_id
    )
    for item in items:
        if item.id == entry.id:
            return item
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Insurance entry not found",
    )


@router.delete(
    "/{patient_id}/insurances/{insurance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_patient_insurance(
    patient_id: uuid.UUID,
    insurance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """
    Soft-delete a patient's insurance entry. If the entry was primary, the
    oldest remaining active entry is promoted to primary automatically.

    @param patient_id: Patient UUID
    @param insurance_id: Insurance entry UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    """
    service = InsuranceService(db)
    deleted = await service.delete_patient_insurance(
        insurance_id=insurance_id,
        patient_id=patient_id,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insurance entry not found",
        )


@router.post(
    "/{patient_id}/insurances/{insurance_id}/set-primary",
    response_model=PatientInsuranceResponse,
)
async def set_primary_patient_insurance(
    patient_id: uuid.UUID,
    insurance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    x_idempotency_key: str | None = Header(None),  # noqa: ARG001
) -> PatientInsuranceResponse:
    """
    Promote an insurance entry to primary, demoting any other primary.
    The patient's legacy insurance columns are re-synced.

    @param patient_id: Patient UUID
    @param insurance_id: Insurance entry UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @param x_idempotency_key: Optional idempotency key
    @returns Updated primary entry
    """
    service = InsuranceService(db)
    entry = await service.set_primary_insurance(
        insurance_id=insurance_id,
        patient_id=patient_id,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insurance entry not found",
        )

    items = await service.list_patient_insurances(
        patient_id=patient_id, facility_id=current_user.facility_id
    )
    for item in items:
        if item.id == entry.id:
            return item
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Insurance entry not found",
    )
