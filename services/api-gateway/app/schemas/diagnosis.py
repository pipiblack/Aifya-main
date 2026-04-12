import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class DiagnosisCreate(BaseModel):
    """Schema for creating a diagnosis."""

    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    icd10_code: str = Field(..., min_length=3, max_length=20)
    icd10_description: str = Field(..., min_length=1, max_length=500)
    diagnosis_type: str = Field(
        ..., pattern=r"^(primary|secondary|differential|ruled_out)$"
    )
    clinical_status: str = Field(
        default="active",
        pattern=r"^(active|recurrence|relapse|inactive|remission|resolved)$",
    )
    certainty: str = Field(
        default="confirmed",
        pattern=r"^(confirmed|provisional|differential|refuted)$",
    )
    onset_date: date | None = None
    notes: str | None = Field(None, max_length=2000)
    is_chronic: bool = False


class DiagnosisResponse(BaseModel):
    """Schema for diagnosis API responses."""

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    diagnosed_by: uuid.UUID
    icd10_code: str
    icd10_description: str
    diagnosis_type: str
    clinical_status: str
    certainty: str
    onset_date: date | None
    resolved_date: date | None
    notes: str | None
    is_chronic: bool
    created_at: datetime

    model_config = {"from_attributes": True}
