"""Pydantic schemas for the HR/Payroll module."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# ── Employees ────────────────────────────────────────────────────────────────


class EmployeeCreate(BaseModel):
    """Create a payroll-grade employee record."""

    staff_id: str = Field(..., max_length=50)
    full_name: str = Field(..., max_length=200)
    id_number: str | None = Field(None, max_length=20)
    kra_pin: str | None = Field(None, max_length=20)
    nssf_number: str | None = Field(None, max_length=20)
    shif_number: str | None = Field(None, max_length=20)
    department_id: uuid.UUID | None = None
    job_title: str | None = Field(None, max_length=200)
    employment_type: str = Field(
        default="permanent",
        pattern=r"^(permanent|contract|casual|intern)$",
    )
    hire_date: date
    termination_date: date | None = None
    is_active: bool = True
    bank_name: str | None = Field(None, max_length=100)
    bank_branch: str | None = Field(None, max_length=100)
    bank_account: str | None = Field(None, max_length=200)
    disability_exemption: bool = False
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=2000)


class EmployeeUpdate(BaseModel):
    """Patch an employee. All fields optional."""

    full_name: str | None = Field(None, max_length=200)
    id_number: str | None = Field(None, max_length=20)
    kra_pin: str | None = Field(None, max_length=20)
    nssf_number: str | None = Field(None, max_length=20)
    shif_number: str | None = Field(None, max_length=20)
    department_id: uuid.UUID | None = None
    job_title: str | None = Field(None, max_length=200)
    employment_type: str | None = Field(None, pattern=r"^(permanent|contract|casual|intern)$")
    termination_date: date | None = None
    is_active: bool | None = None
    bank_name: str | None = Field(None, max_length=100)
    bank_branch: str | None = Field(None, max_length=100)
    bank_account: str | None = Field(None, max_length=200)
    disability_exemption: bool | None = None
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=2000)


class EmployeeResponse(BaseModel):
    """Employee API response (full record, returned on detail endpoints).

    Sensitive fields (kra_pin, nssf_number, shif_number, bank_*) are exposed
    here. The list endpoint returns the lighter EmployeeListItem instead.
    bank_account is NEVER exposed in any response (it is encrypted at rest;
    the service layer must decrypt explicitly when needed for payslip rendering).
    """

    id: uuid.UUID
    staff_id: str
    full_name: str
    id_number: str | None
    kra_pin: str | None
    nssf_number: str | None
    shif_number: str | None
    department_id: uuid.UUID | None
    job_title: str | None
    employment_type: str
    hire_date: date
    termination_date: date | None
    is_active: bool
    bank_name: str | None
    bank_branch: str | None
    disability_exemption: bool
    phone: str | None
    email: str | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployeeListItem(BaseModel):
    """Light-weight employee row for list endpoints — hides PII / statutory IDs."""

    id: uuid.UUID
    staff_id: str
    full_name: str
    department_id: uuid.UUID | None
    job_title: str | None
    employment_type: str
    hire_date: date
    is_active: bool
    phone: str | None
    email: str | None

    model_config = ConfigDict(from_attributes=True)


class EmployeeListResponse(BaseModel):
    """Paged employee list."""

    items: list[EmployeeListItem]
    total: int


# ── Salary structure ────────────────────────────────────────────────────────


class SalaryStructureCreate(BaseModel):
    """Create a new salary effective record for an employee."""

    basic_salary: Decimal = Field(..., ge=0)
    house_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    transport_allowance: Decimal = Field(default=Decimal("0"), ge=0)
    other_allowances: dict[str, Decimal] = Field(default_factory=dict)
    effective_from: date
    effective_to: date | None = None
    notes: str | None = Field(None, max_length=500)


class SalaryStructureResponse(BaseModel):
    """Salary structure API response."""

    id: uuid.UUID
    employee_id: uuid.UUID
    basic_salary: Decimal
    house_allowance: Decimal
    transport_allowance: Decimal
    other_allowances: dict
    effective_from: date
    effective_to: date | None
    approved_by: uuid.UUID | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Payroll runs ────────────────────────────────────────────────────────────


class PayrollRunCreate(BaseModel):
    """Trigger calculation of a draft payroll run."""

    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000, le=2100)
    notes: str | None = Field(None, max_length=500)


class PayrollRunApprove(BaseModel):
    """Approve a draft payroll run."""

    notes: str | None = Field(None, max_length=500)


class PayrollLineItemResponse(BaseModel):
    """Per-employee payslip line response."""

    id: uuid.UUID
    payroll_run_id: uuid.UUID
    employee_id: uuid.UUID
    basic_salary: Decimal
    house_allowance: Decimal
    transport_allowance: Decimal
    other_allowances: dict
    gross_salary: Decimal
    nssf_employee: Decimal
    shif: Decimal
    housing_levy: Decimal
    taxable_pay: Decimal
    paye_gross: Decimal
    personal_relief: Decimal
    insurance_relief: Decimal
    paye: Decimal
    other_deductions: dict
    total_deductions: Decimal
    net_salary: Decimal
    employer_nssf: Decimal
    employer_housing_levy: Decimal
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class PayrollRunResponse(BaseModel):
    """Payroll run summary."""

    id: uuid.UUID
    period_id: uuid.UUID | None
    month: int
    year: int
    status: str
    run_date: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    gl_transaction_id: uuid.UUID | None
    total_gross: Decimal
    total_paye: Decimal
    total_nssf: Decimal
    total_shif: Decimal
    total_hl: Decimal
    total_net: Decimal
    total_employer_nssf: Decimal
    total_employer_hl: Decimal
    notes: str | None
    created_at: datetime
    line_items: list[PayrollLineItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PayrollRunListResponse(BaseModel):
    """Paged payroll run list."""

    items: list[PayrollRunResponse]
    total: int


# ── Statutory rates ─────────────────────────────────────────────────────────


class StatutoryRateCreate(BaseModel):
    """Create a statutory rate."""

    name: str = Field(..., max_length=100)
    category: str = Field(..., pattern=r"^(paye|nssf|shif|housing_levy|relief)$")
    rate: Decimal | None = None
    fixed_amount: Decimal | None = None
    fixed_cap: Decimal | None = None
    effective_from: date
    effective_to: date | None = None
    notes: str | None = Field(None, max_length=500)


class StatutoryRateResponse(BaseModel):
    """Statutory rate API response."""

    id: uuid.UUID
    facility_id: uuid.UUID | None
    name: str
    category: str
    rate: Decimal | None
    fixed_amount: Decimal | None
    fixed_cap: Decimal | None
    effective_from: date
    effective_to: date | None
    approved_by: uuid.UUID | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PAYEBandResponse(BaseModel):
    """PAYE band response."""

    id: uuid.UUID
    facility_id: uuid.UUID | None
    lower_limit: Decimal
    upper_limit: Decimal | None
    rate: Decimal
    effective_from: date
    effective_to: date | None

    model_config = ConfigDict(from_attributes=True)


class NSSFTierResponse(BaseModel):
    """NSSF tier response."""

    id: uuid.UUID
    facility_id: uuid.UUID | None
    tier: str
    lower_limit: Decimal
    upper_limit: Decimal
    employee_rate: Decimal
    employer_rate: Decimal
    effective_from: date
    effective_to: date | None

    model_config = ConfigDict(from_attributes=True)


# ── Leave ───────────────────────────────────────────────────────────────────


class LeaveTypeResponse(BaseModel):
    """Leave type response."""

    id: uuid.UUID
    facility_id: uuid.UUID | None
    name: str
    days_entitlement: int
    paid: bool
    partial_pay: bool
    carries_over: bool
    max_carryover: int | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class LeaveRequestCreate(BaseModel):
    """Submit a payroll-aware leave request."""

    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    days_requested: int = Field(..., ge=1, le=365)
    reason: str | None = Field(None, max_length=1000)


class LeaveRequestResponse(BaseModel):
    """Payroll leave request response."""

    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    days_requested: int
    reason: str | None
    status: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    payroll_deduction: Decimal
    payroll_period_id: uuid.UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeaveApprovalRequest(BaseModel):
    """Approve/reject a leave request."""

    action: str = Field(..., pattern=r"^(approve|reject)$")
    rejection_reason: str | None = Field(None, max_length=500)


# ── Reports ─────────────────────────────────────────────────────────────────


class PayslipResponse(BaseModel):
    """Computed payslip view (line item + employee + facility)."""

    payroll_run_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    staff_id: str
    kra_pin: str | None
    nssf_number: str | None
    shif_number: str | None
    bank_name: str | None
    bank_branch: str | None
    month: int
    year: int
    line: PayrollLineItemResponse


class P9Row(BaseModel):
    """Single month row of a P9 annual return."""

    month: int
    gross_salary: Decimal
    nssf: Decimal
    shif: Decimal
    housing_levy: Decimal
    taxable_pay: Decimal
    paye: Decimal


class P9Response(BaseModel):
    """Annual P9 PAYE return for a single employee."""

    employee_id: uuid.UUID
    employee_name: str
    kra_pin: str | None
    year: int
    rows: list[P9Row]
    total_gross: Decimal
    total_paye: Decimal
    total_nssf: Decimal
    total_shif: Decimal
    total_housing_levy: Decimal


class DepartmentTotals(BaseModel):
    """Per-department payroll totals."""

    department_id: uuid.UUID | None
    department_name: str | None
    headcount: int
    total_gross: Decimal
    total_net: Decimal
    total_paye: Decimal


class PayrollSummaryResponse(BaseModel):
    """Monthly payroll summary, totals per department."""

    month: int
    year: int
    departments: list[DepartmentTotals]
    grand_total_gross: Decimal
    grand_total_net: Decimal
    grand_total_paye: Decimal
    grand_total_nssf: Decimal
    grand_total_shif: Decimal
    grand_total_hl: Decimal
    headcount: int
