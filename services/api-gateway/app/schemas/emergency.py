import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EmergencyVisitCreate(BaseModel):
    """Schema for registering an emergency visit."""

    patient_id: uuid.UUID
    arrival_mode: str = Field(
        default="walk_in",
        pattern=r"^(walk_in|ambulance|referral|police|other)$",
    )
    brought_by: str | None = Field(None, max_length=200)
    chief_complaint: str = Field(..., max_length=2000)
    is_trauma: bool = False
    allergies_noted: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=2000)


class TriageRequest(BaseModel):
    """Schema for triaging an emergency patient."""

    triage_category: str = Field(
        ...,
        pattern=r"^(emergency|urgent|standard|non_urgent|dead)$",
    )
    triage_score: int | None = Field(None, ge=0, le=17)
    triage_vitals: dict | None = None
    treatment_area: str | None = Field(
        None,
        pattern=r"^(resus|acute|sub_acute|fast_track|observation|paediatric)$",
    )
    notes: str | None = Field(None, max_length=1000)


class AssignDoctorRequest(BaseModel):
    """Schema for assigning a doctor to an emergency visit."""

    doctor_id: uuid.UUID


class DispositionRequest(BaseModel):
    """Schema for recording disposition."""

    disposition: str = Field(
        ...,
        pattern=r"^(discharge|admit|transfer|deceased|left_ama)$",
    )
    disposition_notes: str | None = Field(None, max_length=2000)
    admitted_to_ward_id: uuid.UUID | None = None


class EmergencyVisitResponse(BaseModel):
    """Schema for emergency visit API responses."""

    id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None
    visit_number: str
    arrival_time: datetime
    arrival_mode: str
    brought_by: str | None
    chief_complaint: str
    triage_category: str
    triage_color: str
    triage_score: int | None
    triage_time: datetime | None
    triage_vitals: dict | None
    assigned_doctor_id: uuid.UUID | None
    treatment_area: str | None
    treatment_started_at: datetime | None
    status: str
    disposition: str | None
    disposition_time: datetime | None
    disposition_notes: str | None
    is_trauma: bool
    is_resuscitation: bool
    allergies_noted: str | None
    interventions: dict | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EmergencyListItem(BaseModel):
    """Emergency visit in queue list with patient name."""

    id: uuid.UUID
    visit_number: str
    patient_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None = None
    arrival_time: datetime
    arrival_mode: str
    chief_complaint: str
    triage_category: str
    triage_color: str
    triage_score: int | None
    treatment_area: str | None
    assigned_doctor_name: str | None = None
    status: str
    is_trauma: bool
    is_resuscitation: bool

    model_config = {"from_attributes": True}


class EmergencyListResponse(BaseModel):
    """Emergency queue response."""

    items: list[EmergencyListItem]
    total: int


class EmergencySummary(BaseModel):
    """Emergency department summary stats."""

    total_today: int = 0
    awaiting_triage: int = 0
    in_treatment: int = 0
    in_observation: int = 0
    critical_red: int = 0
    urgent_orange: int = 0
    discharged_today: int = 0
    admitted_today: int = 0
    trauma_cases: int = 0
