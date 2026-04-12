import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReferralCreate(BaseModel):
    """Schema for creating a referral."""

    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    referral_type: str = Field(default="internal", pattern=r"^(internal|external)$")
    direction: str = Field(default="outgoing", pattern=r"^(outgoing|incoming)$")
    referring_doctor_id: uuid.UUID | None = None
    referring_department_id: uuid.UUID | None = None
    referring_facility_name: str | None = Field(None, max_length=200)
    receiving_doctor_id: uuid.UUID | None = None
    receiving_department_id: uuid.UUID | None = None
    receiving_facility_name: str | None = Field(None, max_length=200)
    receiving_facility_mfl: str | None = Field(None, max_length=20)
    reason: str = Field(..., max_length=2000)
    clinical_notes: str | None = Field(None, max_length=5000)
    diagnosis: str | None = Field(None, max_length=500)
    urgency: str = Field(default="routine", pattern=r"^(emergency|urgent|routine)$")
    notes: str | None = Field(None, max_length=2000)


class ReferralResponse(BaseModel):
    """Schema for referral API responses."""

    id: uuid.UUID
    referral_number: str
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None
    referral_type: str
    direction: str
    referring_doctor_id: uuid.UUID | None
    referring_department_id: uuid.UUID | None
    referring_facility_name: str | None
    receiving_doctor_id: uuid.UUID | None
    receiving_department_id: uuid.UUID | None
    receiving_facility_name: str | None
    receiving_facility_mfl: str | None
    reason: str
    clinical_notes: str | None
    diagnosis: str | None
    urgency: str
    referral_date: datetime
    status: str
    response_date: datetime | None
    response_notes: str | None
    feedback: str | None
    attachments: dict | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReferralListItem(BaseModel):
    """Referral in list view."""

    id: uuid.UUID
    referral_number: str
    patient_id: uuid.UUID
    patient_name: str | None = None
    referral_type: str
    direction: str
    reason: str
    urgency: str
    referring_facility_name: str | None = None
    receiving_facility_name: str | None = None
    referral_date: datetime
    status: str

    model_config = {"from_attributes": True}


class ReferralListResponse(BaseModel):
    """Referral list response."""

    items: list[ReferralListItem]
    total: int


class ReferralUpdateStatus(BaseModel):
    """Schema for updating referral status."""

    status: str = Field(
        ...,
        pattern=r"^(sent|received|accepted|declined|completed|cancelled)$",
    )
    response_notes: str | None = Field(None, max_length=2000)
    feedback: str | None = Field(None, max_length=2000)


class ReferralSummary(BaseModel):
    """Referral summary stats."""

    total_referrals: int = 0
    outgoing: int = 0
    incoming: int = 0
    pending: int = 0
    accepted: int = 0
    completed: int = 0
