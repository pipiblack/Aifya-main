import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class InsuranceSchemeCreate(BaseModel):
    """Schema for creating an insurance scheme."""

    name: str = Field(..., max_length=200)
    scheme_type: str = Field(default="sha", pattern=r"^(sha|private|corporate|nhif_legacy)$")
    contact_person: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=500)
    contract_start: datetime | None = None
    contract_end: datetime | None = None
    coverage_details: dict | None = None
    rebate_percentage: int | None = Field(None, ge=0, le=100)
    notes: str | None = Field(None, max_length=1000)


class InsuranceSchemeResponse(BaseModel):
    """Schema for insurance scheme responses."""

    id: uuid.UUID
    name: str
    scheme_code: str
    scheme_type: str
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    contract_start: datetime | None
    contract_end: datetime | None
    coverage_details: dict | None
    rebate_percentage: int | None
    is_active: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InsuranceSchemeListResponse(BaseModel):
    """Scheme list response."""

    items: list[InsuranceSchemeResponse]
    total: int


class ClaimCreate(BaseModel):
    """Schema for creating a claim."""

    patient_id: uuid.UUID
    scheme_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    encounter_id: uuid.UUID | None = None
    member_number: str = Field(..., max_length=50)
    claim_amount: int = Field(..., ge=0)
    claim_items: dict | None = None
    diagnosis_codes: dict | None = None
    notes: str | None = Field(None, max_length=2000)


class ClaimResponse(BaseModel):
    """Schema for claim responses."""

    id: uuid.UUID
    claim_number: str
    patient_id: uuid.UUID
    scheme_id: uuid.UUID
    invoice_id: uuid.UUID | None
    encounter_id: uuid.UUID | None
    member_number: str
    claim_amount: int
    approved_amount: int
    paid_amount: int
    status: str
    claim_date: datetime
    submitted_date: datetime | None
    processed_date: datetime | None
    paid_date: datetime | None
    claim_items: dict | None
    diagnosis_codes: dict | None
    rejection_reason: str | None
    sha_reference: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClaimListItem(BaseModel):
    """Claim in list view."""

    id: uuid.UUID
    claim_number: str
    patient_id: uuid.UUID
    patient_name: str | None = None
    scheme_name: str | None = None
    member_number: str
    claim_amount: int
    approved_amount: int
    status: str
    claim_date: datetime
    sha_reference: str | None = None

    model_config = {"from_attributes": True}


class ClaimListResponse(BaseModel):
    """Claim list response."""

    items: list[ClaimListItem]
    total: int


class ClaimStatusUpdate(BaseModel):
    """Schema for updating claim status."""

    status: str = Field(
        ...,
        pattern=r"^(submitted|processing|approved|partially_approved|rejected|paid)$",
    )
    approved_amount: int | None = Field(None, ge=0)
    paid_amount: int | None = Field(None, ge=0)
    rejection_reason: str | None = Field(None, max_length=1000)
    sha_reference: str | None = Field(None, max_length=50)


class InsuranceSummary(BaseModel):
    """Insurance summary stats."""

    total_claims: int = 0
    pending_claims: int = 0
    submitted_claims: int = 0
    approved_claims: int = 0
    rejected_claims: int = 0
    total_claim_value: int = 0
    active_schemes: int = 0
    preauth_pending: int = 0


# ── Patient Insurance (multi-entry) ──────────────────────────────────────────


class PatientInsuranceCreate(BaseModel):
    """Schema for adding a new insurance entry to a patient."""

    scheme_id: uuid.UUID
    member_number: str = Field(..., min_length=1, max_length=50)
    principal_name: str | None = Field(None, max_length=200)
    relationship: str | None = Field(
        None, pattern=r"^(self|spouse|child|parent|other)$"
    )
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_primary: bool = Field(
        default=False,
        description="Mark this insurance as the patient's primary insurer",
    )
    notes: str | None = Field(None, max_length=1000)


class PatientInsuranceUpdate(BaseModel):
    """Schema for editing an insurance entry. All fields optional."""

    scheme_id: uuid.UUID | None = None
    member_number: str | None = Field(None, min_length=1, max_length=50)
    principal_name: str | None = Field(None, max_length=200)
    relationship: str | None = Field(
        None, pattern=r"^(self|spouse|child|parent|other)$"
    )
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_active: bool | None = None
    is_primary: bool | None = None
    notes: str | None = Field(None, max_length=1000)


class PatientInsuranceResponse(BaseModel):
    """Schema for patient insurance API responses (joined with scheme)."""

    id: uuid.UUID
    patient_id: uuid.UUID
    scheme_id: uuid.UUID
    scheme_name: str | None = None
    scheme_type: str | None = None
    member_number: str
    principal_name: str | None
    relationship: str | None
    valid_from: datetime | None
    valid_to: datetime | None
    is_active: bool
    is_primary: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatientInsuranceListResponse(BaseModel):
    """Paginated list of insurance entries for a patient."""

    items: list[PatientInsuranceResponse]
    total: int
