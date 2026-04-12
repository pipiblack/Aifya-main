import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EncounterCreate(BaseModel):
    """Schema for creating a new encounter."""

    patient_id: uuid.UUID
    encounter_type: str = Field(
        ..., pattern=r"^(opd|ipd|emergency|mch|dental|surgical|follow_up)$"
    )
    department_id: uuid.UUID | None = None
    chief_complaint: str | None = Field(None, max_length=2000)
    triage_category: str | None = Field(
        None, pattern=r"^(emergency|urgent|standard|non_urgent|dead)$"
    )
    priority: int = 0


class EncounterUpdate(BaseModel):
    """Schema for updating an encounter."""

    status: str | None = Field(
        None,
        pattern=r"^(waiting|in_consultation|completed|admitted|discharged|cancelled)$",
    )
    attending_doctor_id: uuid.UUID | None = None
    nurse_id: uuid.UUID | None = None
    chief_complaint: str | None = Field(None, max_length=2000)
    triage_category: str | None = Field(
        None, pattern=r"^(emergency|urgent|standard|non_urgent|dead)$"
    )
    priority: int | None = None
    disposition: str | None = Field(
        None,
        pattern=r"^(discharged|admitted|referred|follow_up|deceased)$",
    )
    discharge_summary: str | None = None


class EncounterResponse(BaseModel):
    """Schema for encounter API responses."""

    id: uuid.UUID
    facility_id: uuid.UUID
    patient_id: uuid.UUID
    encounter_type: str
    encounter_date: datetime
    department_id: uuid.UUID | None
    attending_doctor_id: uuid.UUID | None
    nurse_id: uuid.UUID | None
    queue_number: int | None
    triage_category: str | None
    priority: int
    status: str
    chief_complaint: str | None
    disposition: str | None
    billing_status: str
    trial_participant_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    # Joined fields for display
    patient_name: str | None = None
    patient_mrn: str | None = None

    model_config = {"from_attributes": True}


class QueueResponse(BaseModel):
    """OPD queue list response."""

    items: list[EncounterResponse]
    total: int
