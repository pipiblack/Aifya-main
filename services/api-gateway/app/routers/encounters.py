import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.diagnosis import DiagnosisCreate, DiagnosisResponse
from app.schemas.encounter import (
    EncounterCreate,
    EncounterResponse,
    EncounterUpdate,
    QueueResponse,
)
from app.schemas.lab import LabOrderCreate, LabOrderResponse
from app.schemas.prescription import (
    DrugInteractionAlert,
    PrescriptionCreate,
    PrescriptionResponse,
    PrescriptionWithInteractions,
)
from app.schemas.vital import VitalSignCreate, VitalSignResponse
from app.services.diagnosis_service import DiagnosisService
from app.services.encounter_service import EncounterService
from app.services.lab_service import LabService
from app.services.prescription_service import PrescriptionService
from app.services.vitals_service import VitalsService

router = APIRouter(dependencies=[Depends(require_module("encounters"))])


# ── Encounter CRUD ─────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=EncounterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_encounter(
    data: EncounterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    x_idempotency_key: str | None = Header(None),
) -> EncounterResponse:
    """
    Create a new encounter and add patient to OPD queue.

    @param data: Encounter creation data
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @param x_idempotency_key: Optional idempotency key
    @returns Created encounter
    """
    service = EncounterService(db)
    encounter = await service.create_encounter(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
        idempotency_key=x_idempotency_key,
    )
    return EncounterResponse.model_validate(encounter)


@router.get("/queue", response_model=QueueResponse)
async def get_opd_queue(
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern=r"^(waiting|in_consultation|completed|admitted|discharged|cancelled)$",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> QueueResponse:
    """
    Get the OPD queue ordered by triage priority then queue number.

    @param status_filter: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Queue of encounters
    """
    service = EncounterService(db)
    encounters = await service.get_opd_queue(
        facility_id=current_user.facility_id,
        status_filter=status_filter,
    )
    return QueueResponse(
        items=[EncounterResponse.model_validate(e) for e in encounters],
        total=len(encounters),
    )


@router.post("/queue/call-next", response_model=EncounterResponse)
async def call_next_patient(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "admin", "facility_admin")
    ),
) -> EncounterResponse:
    """
    Call the next patient in the OPD queue (highest priority waiting).

    @param db: Database session
    @param current_user: Authenticated doctor
    @returns Next encounter or 404 if queue empty
    """
    service = EncounterService(db)
    encounter = await service.call_next(
        facility_id=current_user.facility_id,
        doctor_id=current_user.user_id,
    )
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No patients waiting in queue",
        )
    return EncounterResponse.model_validate(encounter)


@router.get("/{encounter_id}", response_model=EncounterResponse)
async def get_encounter(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EncounterResponse:
    """
    Get a single encounter by ID.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Encounter details
    """
    service = EncounterService(db)
    encounter = await service.get_encounter(
        encounter_id, current_user.facility_id
    )
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found",
        )
    return EncounterResponse.model_validate(encounter)


@router.patch("/{encounter_id}", response_model=EncounterResponse)
async def update_encounter(
    encounter_id: uuid.UUID,
    data: EncounterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EncounterResponse:
    """
    Update encounter (status, triage, disposition, etc.).

    @param encounter_id: Encounter UUID
    @param data: Fields to update
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Updated encounter
    """
    service = EncounterService(db)
    encounter = await service.update_encounter(
        encounter_id=encounter_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found",
        )
    return EncounterResponse.model_validate(encounter)


# ── Vitals ─────────────────────────────────────────────────────────────────


@router.post(
    "/{encounter_id}/vitals",
    response_model=VitalSignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_vitals(
    encounter_id: uuid.UUID,
    data: VitalSignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> VitalSignResponse:
    """
    Record vital signs for an encounter. Critical values trigger alerts.

    @param encounter_id: Encounter UUID (path)
    @param data: Vital signs data
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Recorded vital signs with critical alerts if any
    """
    if data.encounter_id != encounter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter ID in path and body must match",
        )
    service = VitalsService(db)
    vital = await service.record_vitals(
        data=data,
        facility_id=current_user.facility_id,
        recorded_by=current_user.user_id,
    )
    return VitalSignResponse.model_validate(vital)


@router.get(
    "/{encounter_id}/vitals",
    response_model=list[VitalSignResponse],
)
async def get_encounter_vitals(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[VitalSignResponse]:
    """
    Get all vital sign recordings for an encounter.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of vital sign recordings
    """
    service = VitalsService(db)
    vitals = await service.get_encounter_vitals(
        encounter_id, current_user.facility_id
    )
    return [VitalSignResponse.model_validate(v) for v in vitals]


# ── Diagnoses ──────────────────────────────────────────────────────────────


@router.post(
    "/{encounter_id}/diagnoses",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_diagnosis(
    encounter_id: uuid.UUID,
    data: DiagnosisCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "admin", "facility_admin")
    ),
) -> DiagnosisResponse:
    """
    Add a diagnosis (ICD-10) to an encounter.

    @param encounter_id: Encounter UUID (path)
    @param data: Diagnosis data with ICD-10 code
    @param db: Database session
    @param current_user: Authenticated doctor
    @returns Created diagnosis
    """
    if data.encounter_id != encounter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter ID in path and body must match",
        )
    service = DiagnosisService(db)
    diagnosis = await service.add_diagnosis(
        data=data,
        facility_id=current_user.facility_id,
        diagnosed_by=current_user.user_id,
    )
    return DiagnosisResponse.model_validate(diagnosis)


@router.get(
    "/{encounter_id}/diagnoses",
    response_model=list[DiagnosisResponse],
)
async def get_encounter_diagnoses(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DiagnosisResponse]:
    """
    Get all diagnoses for an encounter.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of diagnoses
    """
    service = DiagnosisService(db)
    diagnoses = await service.get_encounter_diagnoses(
        encounter_id, current_user.facility_id
    )
    return [DiagnosisResponse.model_validate(d) for d in diagnoses]


# ── Prescriptions ──────────────────────────────────────────────────────────


@router.post(
    "/{encounter_id}/prescriptions",
    response_model=PrescriptionWithInteractions,
    status_code=status.HTTP_201_CREATED,
)
async def create_prescription(
    encounter_id: uuid.UUID,
    data: PrescriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "admin", "facility_admin")
    ),
) -> PrescriptionWithInteractions:
    """
    Create a prescription with drug interaction checking.
    Blocks on critical interactions per CLAUDE.md: Clinical Safety.

    @param encounter_id: Encounter UUID (path)
    @param data: Prescription data
    @param db: Database session
    @param current_user: Authenticated doctor
    @returns Prescription with interaction check results
    """
    if data.encounter_id != encounter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter ID in path and body must match",
        )
    service = PrescriptionService(db)
    prescription, interactions, blocked = await service.create_prescription(
        data=data,
        facility_id=current_user.facility_id,
        prescriber_id=current_user.user_id,
    )
    mapped_interactions = [
        DrugInteractionAlert(
            severity=i.get("severity", "moderate"),
            interacting_drug=(
                ", ".join(i.get("affected_items", []))
                if i.get("affected_items")
                else i.get("interacting_drug", "")
            ),
            description=i.get("message", i.get("description", "")),
        )
        for i in interactions
    ]
    return PrescriptionWithInteractions(
        prescription=PrescriptionResponse.model_validate(prescription),
        interactions=mapped_interactions,
        blocked=blocked,
    )


@router.get(
    "/{encounter_id}/prescriptions",
    response_model=list[PrescriptionResponse],
)
async def get_encounter_prescriptions(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PrescriptionResponse]:
    """
    Get all prescriptions for an encounter.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of prescriptions
    """
    service = PrescriptionService(db)
    prescriptions = await service.get_encounter_prescriptions(
        encounter_id, current_user.facility_id
    )
    return [PrescriptionResponse.model_validate(p) for p in prescriptions]


# ── Lab Orders ─────────────────────────────────────────────────────────────


@router.post(
    "/{encounter_id}/lab-orders",
    response_model=LabOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lab_order(
    encounter_id: uuid.UUID,
    data: LabOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("doctor", "admin", "facility_admin")
    ),
) -> LabOrderResponse:
    """
    Create a lab order with one or more tests.

    @param encounter_id: Encounter UUID (path)
    @param data: Lab order data with tests
    @param db: Database session
    @param current_user: Authenticated doctor
    @returns Created lab order
    """
    if data.encounter_id != encounter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter ID in path and body must match",
        )
    service = LabService(db)
    order = await service.create_order(
        data=data,
        facility_id=current_user.facility_id,
        ordered_by=current_user.user_id,
    )
    return LabOrderResponse.model_validate(order)


@router.get(
    "/{encounter_id}/lab-orders",
    response_model=list[LabOrderResponse],
)
async def get_encounter_lab_orders(
    encounter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[LabOrderResponse]:
    """
    Get all lab orders for an encounter.

    @param encounter_id: Encounter UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of lab orders
    """
    service = LabService(db)
    orders = await service.get_encounter_orders(
        encounter_id, current_user.facility_id
    )
    return [LabOrderResponse.model_validate(o) for o in orders]
