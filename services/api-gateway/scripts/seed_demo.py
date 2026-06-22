"""
Aifya HMIS — Comprehensive Demo Seed Script.

Loads all data needed to demo the platform end-to-end:
  - Facility, departments, staff
  - Patients (15 demographically varied)
  - Pharmacy formulary (15 common Kenyan drugs)
  - Finance: Chart of Accounts, posting rules, accounting periods
  - Sample invoices + GL postings (cash + insurance)
  - Sample payments + expenses
  - Payroll: statutory rates, employees, salaries, monthly run
  - Sample leave requests, fixed assets, budgets, recurring templates
  - M-Pesa STK sample records
  - SHA insurance scheme

IDEMPOTENT: re-running does not create duplicates. Deterministic UUIDs
are derived from uuid5(facility_id, entity-name) where applicable; for
other entities a check-then-insert pattern is used.

Usage:
    python scripts/seed_demo.py            # Seed (idempotent)
    python scripts/seed_demo.py --reset    # Soft-delete all demo facility data

Run AFTER `alembic upgrade head`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

# Ensure parent (`api-gateway/`) is on sys.path when this script is
# invoked directly via `python scripts/seed_demo.py`.
_THIS_DIR = Path(__file__).resolve().parent
_API_GATEWAY_DIR = _THIS_DIR.parent
if str(_API_GATEWAY_DIR) not in sys.path:
    sys.path.insert(0, str(_API_GATEWAY_DIR))

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models.appointment import Appointment, DoctorSchedule  # noqa: E402
from app.models.billing import Invoice, InvoiceItem, Payment  # noqa: E402
from app.models.clinical_trial import (  # noqa: E402
    ClinicalTrial,
    TrialAIScreening,
    TrialAdverseEvent,
    TrialParticipant,
    TrialParticipantVisit,
    TrialVisitSchedule,
)
from app.models.dental import DentalChart, DentalTreatmentPlan, DentalVisit  # noqa: E402
from app.models.diagnosis import Diagnosis  # noqa: E402
from app.models.emergency import EmergencyVisit  # noqa: E402
from app.models.encounter import Encounter  # noqa: E402
from app.models.facility import Facility  # noqa: E402
from app.models.finance import (  # noqa: E402
    Account,
    AccountingPeriod,
    Budget,
    FixedAsset,
    RecurringTemplate,
)
from app.models.hr import Attendance, LeaveRequest, Shift, ShiftAssignment, StaffProfile  # noqa: E402
from app.models.insurance import (  # noqa: E402
    InsuranceClaim,
    InsuranceScheme,
    PatientInsurance,
    PreAuthorization,
)
from app.models.inventory import (  # noqa: E402
    InventoryItem,
    InventoryTransaction,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from app.models.ipd import Admission, Bed, NursingNote, Ward  # noqa: E402
from app.models.lab import LabOrder, LabResult  # noqa: E402
from app.models.mch import ANCProfile, ANCVisit, ChildRecord, Immunization  # noqa: E402
from app.models.mpesa import MpesaStkRequest  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.payroll import Employee, EmployeeSalary, PayrollRun  # noqa: E402
from app.models.payroll_extra import LeaveType, PayrollLeaveRequest  # noqa: E402
from app.models.pharmacy import PharmacyItem  # noqa: E402
from app.models.prescription import Prescription  # noqa: E402
from app.models.radiology import ImagingOrder, ImagingResult  # noqa: E402
from app.models.referral import Referral  # noqa: E402
from app.models.report import GeneratedReport, ReportTemplate  # noqa: E402
from app.models.sms import SmsCampaign, SmsDeliveryLog  # noqa: E402
from app.models.staff import Department, Staff  # noqa: E402
from app.models.theatre import OperatingTheatre, SurgicalCase  # noqa: E402
from app.models.vital import VitalSign  # noqa: E402
from app.services.finance.posting_engine import post_transaction  # noqa: E402
from app.services.finance.seed_data import seed_facility_finance  # noqa: E402
from app.services.payroll.engine import run_monthly_payroll  # noqa: E402
from app.services.payroll.gl_integration import post_payroll_to_gl  # noqa: E402
from app.services.payroll.seed_data import seed_payroll_defaults  # noqa: E402


# ── Constants ────────────────────────────────────────────────────────────────

# Stable namespace for deterministic UUID generation across runs.
# Re-running the seed yields identical UUIDs, which makes the script idempotent.
DEMO_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "aifya-demo.aifya.co.ke")

DEMO_FACILITY_NAME = "Aifya Demo Hospital"
DEMO_FACILITY_CODE = "AIFYA-DEMO"
DEMO_FACILITY_MFL = "99999"

# Must match app.auth.dependencies local development auth bypass.
LOCAL_DEMO_FACILITY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
LOCAL_DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")

# Today's reference date (overridable for stable demos)
TODAY = date.today()
NOW = datetime.now(timezone.utc)


def _det(label: str) -> uuid.UUID:
    """Deterministic UUID derived from a label (idempotency key)."""
    return uuid.uuid5(DEMO_NAMESPACE, label)


def _kes_to_cents(kes: int | float | Decimal) -> int:
    """Convert KES to integer cents (per CLAUDE.md money rules)."""
    return int((Decimal(str(kes)) * 100).to_integral_value())


# ── Facility ─────────────────────────────────────────────────────────────────


async def get_or_create_facility(db: AsyncSession) -> Facility:
    """Find or create the demo facility (idempotent).

    @param db: Async DB session
    @returns The Facility row (existing or newly created)
    """
    local = (
        await db.execute(
            select(Facility).where(Facility.id == LOCAL_DEMO_FACILITY_ID)
        )
    ).scalar_one_or_none()
    if local is not None:
        local.name = DEMO_FACILITY_NAME
        local.code = DEMO_FACILITY_CODE
        local.mfl_code = DEMO_FACILITY_MFL
        local.facility_type = "hospital"
        local.keph_level = "4"
        local.county = "Nairobi"
        local.sub_county = "Westlands"
        local.ward = "Parklands"
        local.physical_address = "Aifya Plaza, 5th Floor, Westlands, Nairobi"
        local.phone = "+254700000000"
        local.email = "info@aifya.co.ke"
        local.website = "https://aifya.co.ke"
        local.timezone = "Africa/Nairobi"
        local.currency = "KES"
        local.is_active = True
        await db.flush()
        return local

    existing = (
        await db.execute(
            select(Facility).where(Facility.code == DEMO_FACILITY_CODE)
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Older seeds used a generated UUID. Rename that legacy facility so
        # the local Docker auth facility can own the canonical demo code.
        existing.code = f"{DEMO_FACILITY_CODE}-LEGACY"
        existing.mfl_code = None
        await db.flush()

    fac = Facility(
        id=LOCAL_DEMO_FACILITY_ID,
        name=DEMO_FACILITY_NAME,
        code=DEMO_FACILITY_CODE,
        facility_type="hospital",
        keph_level="4",
        mfl_code=DEMO_FACILITY_MFL,
        county="Nairobi",
        sub_county="Westlands",
        ward="Parklands",
        physical_address="Aifya Plaza, 5th Floor, Westlands, Nairobi",
        phone="+254700000000",
        email="info@aifya.co.ke",
        website="https://aifya.co.ke",
        timezone="Africa/Nairobi",
        currency="KES",
        is_active=True,
    )
    db.add(fac)
    await db.flush()
    print(f"  Created facility: {fac.name} ({fac.code})")
    return fac


# ── Departments ──────────────────────────────────────────────────────────────


DEPARTMENTS: list[tuple[str, str, str]] = [
    # (code, name, type)
    ("OPD", "Outpatient", "clinical"),
    ("IPD", "Inpatient", "clinical"),
    ("PHARM", "Pharmacy", "clinical"),
    ("LAB", "Laboratory", "clinical"),
    ("RAD", "Radiology", "clinical"),
    ("MCH", "Maternal & Child Health", "clinical"),
    ("ER", "Emergency", "clinical"),
    ("ADMIN", "Administration", "admin"),
]


async def seed_departments(
    db: AsyncSession, facility_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """Seed the 8 demo departments idempotently.

    @returns Map {code: department_id}
    """
    by_code: dict[str, uuid.UUID] = {}
    existing = (
        await db.execute(
            select(Department).where(Department.facility_id == facility_id)
        )
    ).scalars().all()
    existing_codes = {d.code: d.id for d in existing}

    created = 0
    for code, name, dtype in DEPARTMENTS:
        if code in existing_codes:
            by_code[code] = existing_codes[code]
            continue
        dept = Department(
            id=_det(f"dept:{code}"),
            facility_id=facility_id,
            code=code,
            name=name,
            department_type=dtype,
            is_active=True,
        )
        db.add(dept)
        await db.flush()
        by_code[code] = dept.id
        created += 1

    print(f"  Departments: {created} created, {len(existing_codes)} existing")
    return by_code


# ── Staff ────────────────────────────────────────────────────────────────────

STAFF_DEFINITIONS: list[dict[str, Any]] = [
    # employee_number, first, last, role, title, dept_code, email
    {"emp": "AIFYA-001", "first": "Wanjiku", "last": "Kamau", "role": "admin",
     "title": "Dr.", "dept": "ADMIN", "email": "admin@aifya.co.ke",
     "license_body": "KMPDC", "license": "KMPDC/12345"},
    {"emp": "AIFYA-002", "first": "James", "last": "Otieno", "role": "doctor",
     "title": "Dr.", "dept": "OPD", "email": "doctor@aifya.co.ke",
     "license_body": "KMPDC", "license": "KMPDC/22001"},
    {"emp": "AIFYA-003", "first": "Mary", "last": "Akinyi", "role": "doctor",
     "title": "Dr.", "dept": "IPD", "email": "mary.akinyi@aifya.co.ke",
     "license_body": "KMPDC", "license": "KMPDC/22002"},
    {"emp": "AIFYA-004", "first": "Faith", "last": "Njeri", "role": "nurse",
     "title": "Sister", "dept": "OPD", "email": "nurse@aifya.co.ke",
     "license_body": "NCK", "license": "NCK/33001"},
    {"emp": "AIFYA-005", "first": "Grace", "last": "Wanjiru", "role": "nurse",
     "title": "Sister", "dept": "MCH", "email": "grace.wanjiru@aifya.co.ke",
     "license_body": "NCK", "license": "NCK/33002"},
    {"emp": "AIFYA-006", "first": "Peter", "last": "Mwangi", "role": "pharmacist",
     "title": "Mr.", "dept": "PHARM", "email": "pharmacy@aifya.co.ke",
     "license_body": "PPB", "license": "PPB/44001"},
    {"emp": "AIFYA-007", "first": "John", "last": "Kiprop", "role": "lab_tech",
     "title": "Mr.", "dept": "LAB", "email": "lab@aifya.co.ke",
     "license_body": "KMLTTB", "license": "KMLTTB/55001"},
    {"emp": "AIFYA-008", "first": "Ruth", "last": "Achieng", "role": "cashier",
     "title": "Ms.", "dept": "ADMIN", "email": "cashier@aifya.co.ke",
     "license_body": None, "license": None},
    {"emp": "AIFYA-009", "first": "Esther", "last": "Nyambura", "role": "hr_admin",
     "title": "Ms.", "dept": "ADMIN", "email": "hr@aifya.co.ke",
     "license_body": None, "license": None},
    {"emp": "AIFYA-010", "first": "David", "last": "Kimani", "role": "receptionist",
     "title": "Mr.", "dept": "OPD", "email": "reception@aifya.co.ke",
     "license_body": None, "license": None},
]


async def seed_staff(
    db: AsyncSession,
    facility_id: uuid.UUID,
    dept_map: dict[str, uuid.UUID],
) -> dict[str, uuid.UUID]:
    """Seed 10 demo Staff rows idempotently.

    @returns Map {employee_number: staff.id}
    """
    by_num: dict[str, uuid.UUID] = {}
    existing = (
        await db.execute(
            select(Staff).where(Staff.facility_id == facility_id)
        )
    ).scalars().all()
    existing_by_num = {s.employee_number: s.id for s in existing}

    created = 0
    for s in STAFF_DEFINITIONS:
        if s["emp"] in existing_by_num:
            by_num[s["emp"]] = existing_by_num[s["emp"]]
            continue
        kc_id = _det(f"keycloak:{s['emp']}")
        dept_id = dept_map.get(s["dept"])
        staff = Staff(
            id=LOCAL_DEMO_USER_ID if s["emp"] == "AIFYA-001" else _det(f"staff:{s['emp']}"),
            facility_id=facility_id,
            keycloak_user_id=kc_id,
            employee_number=s["emp"],
            first_name=s["first"],
            last_name=s["last"],
            title=s["title"],
            role=s["role"],
            license_body=s["license_body"],
            license_number=s["license"],
            department_id=dept_id,
            primary_department_id=dept_id,
            email=s["email"],
            phone=f"+25470000{int(s['emp'].split('-')[1]):04d}",
            is_active=True,
        )
        db.add(staff)
        await db.flush()
        by_num[s["emp"]] = staff.id
        created += 1

    local_staff = (
        await db.execute(
            select(Staff).where(
                Staff.facility_id == facility_id,
                Staff.id == LOCAL_DEMO_USER_ID,
            )
        )
    ).scalar_one_or_none()
    if local_staff is None:
        local_staff = Staff(
            id=LOCAL_DEMO_USER_ID,
            facility_id=facility_id,
            keycloak_user_id=LOCAL_DEMO_USER_ID,
            employee_number="AIFYA-LOCAL-ADMIN",
            first_name="Aifya",
            last_name="Local Admin",
            title="Dr.",
            role="admin",
            license_body="KMPDC",
            license_number="KMPDC/LOCAL",
            department_id=dept_map.get("ADMIN"),
            primary_department_id=dept_map.get("ADMIN"),
            email="admin@aifya.local",
            phone="+254700000002",
            permissions={"local_demo": True},
            is_active=True,
        )
        db.add(local_staff)
        await db.flush()
        by_num["AIFYA-LOCAL-ADMIN"] = local_staff.id
        created += 1
    else:
        by_num.setdefault("AIFYA-LOCAL-ADMIN", local_staff.id)

    print(f"  Staff: {created} created, {len(existing_by_num)} existing")
    return by_num


# ── Patients ─────────────────────────────────────────────────────────────────

PATIENTS: list[dict[str, Any]] = [
    # name, dob_offset_years, gender, insurance_provider, conditions, pregnant
    {"first": "Baby", "last": "Mwangi", "age_months": 1, "gender": "female",
     "ins": None, "phone_suffix": "001", "county": "Nairobi"},
    {"first": "Brian", "last": "Otieno", "age_years": 8, "gender": "male",
     "ins": "SHA", "phone_suffix": "002", "county": "Kisumu"},
    {"first": "Sharon", "last": "Achieng", "age_years": 15, "gender": "female",
     "ins": "SHA", "phone_suffix": "003", "county": "Nairobi"},
    {"first": "Kevin", "last": "Kariuki", "age_years": 25, "gender": "male",
     "ins": None, "phone_suffix": "004", "county": "Kiambu"},
    {"first": "Mercy", "last": "Wanjiku", "age_years": 28, "gender": "female",
     "ins": "SHA", "phone_suffix": "005", "county": "Nairobi", "pregnant": True},
    {"first": "Daniel", "last": "Kipchoge", "age_years": 30, "gender": "male",
     "ins": "Britam", "phone_suffix": "006", "county": "Uasin Gishu"},
    {"first": "Lucy", "last": "Njoki", "age_years": 32, "gender": "female",
     "ins": "SHA", "phone_suffix": "007", "county": "Nairobi", "pregnant": True},
    {"first": "Samuel", "last": "Kiplagat", "age_years": 35, "gender": "male",
     "ins": None, "phone_suffix": "008", "county": "Nakuru"},
    {"first": "Faith", "last": "Mumbi", "age_years": 40, "gender": "female",
     "ins": "Jubilee", "phone_suffix": "009", "county": "Nairobi"},
    {"first": "Joseph", "last": "Mutua", "age_years": 45, "gender": "male",
     "ins": "SHA", "phone_suffix": "010", "county": "Machakos",
     "conditions": ["Diabetes Mellitus Type 2"]},
    {"first": "Grace", "last": "Wairimu", "age_years": 50, "gender": "female",
     "ins": "SHA", "phone_suffix": "011", "county": "Nairobi"},
    {"first": "Joshua", "last": "Omondi", "age_years": 60, "gender": "male",
     "ins": "AAR", "phone_suffix": "012", "county": "Kisumu"},
    {"first": "Margaret", "last": "Wambui", "age_years": 65, "gender": "female",
     "ins": "SHA", "phone_suffix": "013", "county": "Nyeri"},
    {"first": "Patrick", "last": "Ngugi", "age_years": 70, "gender": "male",
     "ins": "SHA", "phone_suffix": "014", "county": "Kiambu"},
    {"first": "Ruth", "last": "Atieno", "age_years": 75, "gender": "female",
     "ins": None, "phone_suffix": "015", "county": "Siaya"},
]


async def seed_patients(
    db: AsyncSession, facility_id: uuid.UUID
) -> list[uuid.UUID]:
    """Seed 15 demographically-varied patients (idempotent by MRN).

    @returns List of patient.id
    """
    ids: list[uuid.UUID] = []
    existing = (
        await db.execute(
            select(Patient).where(Patient.facility_id == facility_id)
        )
    ).scalars().all()
    existing_mrns = {p.mrn: p.id for p in existing}

    created = 0
    for i, p in enumerate(PATIENTS, start=1):
        mrn = f"MRN-{i:05d}"
        if mrn in existing_mrns:
            ids.append(existing_mrns[mrn])
            continue

        if "age_months" in p:
            dob = TODAY - timedelta(days=int(p["age_months"]) * 30)
        else:
            dob = TODAY - timedelta(days=int(p["age_years"]) * 365)

        chronic = p.get("conditions") or None
        if p.get("pregnant"):
            chronic = (chronic or []) + ["Currently Pregnant"]

        patient = Patient(
            id=_det(f"patient:{mrn}"),
            facility_id=facility_id,
            mrn=mrn,
            first_name=p["first"],
            last_name=p["last"],
            date_of_birth=dob,
            gender=p["gender"],
            phone_number=f"+254712345{p['phone_suffix']}",
            county=p.get("county"),
            insurance_provider=p.get("ins"),
            insurance_member_number=(
                f"SHA{i:09d}" if p.get("ins") == "SHA" else None
            ),
            sha_number=f"SHA{i:09d}" if p.get("ins") == "SHA" else None,
            chronic_conditions=chronic,
            blood_group="O+" if i % 2 == 0 else "A+",
        )
        db.add(patient)
        await db.flush()
        ids.append(patient.id)
        created += 1

    print(f"  Patients: {created} created, {len(existing_mrns)} existing")
    return ids


# ── Pharmacy Items ───────────────────────────────────────────────────────────

PHARMACY_ITEMS: list[dict[str, Any]] = [
    {"code": "PCM500", "name": "Paracetamol 500mg", "form": "tablet",
     "strength": "500mg", "kes": 5, "uom": "tablet", "stock": 500, "keml": True},
    {"code": "AMX500", "name": "Amoxicillin 500mg", "form": "capsule",
     "strength": "500mg", "kes": 15, "uom": "capsule", "stock": 300, "keml": True},
    {"code": "MET500", "name": "Metformin 500mg", "form": "tablet",
     "strength": "500mg", "kes": 8, "uom": "tablet", "stock": 400, "keml": True},
    {"code": "AML5", "name": "Amlodipine 5mg", "form": "tablet",
     "strength": "5mg", "kes": 12, "uom": "tablet", "stock": 250, "keml": True},
    {"code": "ORS01", "name": "Oral Rehydration Salts", "form": "sachet",
     "strength": "20.5g", "kes": 30, "uom": "sachet", "stock": 200, "keml": True},
    {"code": "FEFOL", "name": "Iron + Folic Acid", "form": "tablet",
     "strength": "60mg/0.4mg", "kes": 5, "uom": "tablet", "stock": 500, "keml": True},
    {"code": "ALB400", "name": "Albendazole 400mg", "form": "tablet",
     "strength": "400mg", "kes": 25, "uom": "tablet", "stock": 200, "keml": True},
    {"code": "DCF50", "name": "Diclofenac 50mg", "form": "tablet",
     "strength": "50mg", "kes": 10, "uom": "tablet", "stock": 300, "keml": True},
    {"code": "CTX1G", "name": "Ceftriaxone 1g", "form": "injection",
     "strength": "1g", "kes": 250, "uom": "vial", "stock": 100, "keml": True},
    {"code": "SAL100", "name": "Salbutamol Inhaler", "form": "inhaler",
     "strength": "100mcg", "kes": 350, "uom": "inhaler", "stock": 100, "keml": True},
    {"code": "INSR", "name": "Insulin Regular", "form": "injection",
     "strength": "100IU/ml", "kes": 500, "uom": "vial", "stock": 100, "keml": True},
    {"code": "CSY100", "name": "Cough Syrup 100ml", "form": "syrup",
     "strength": "100ml", "kes": 180, "uom": "bottle", "stock": 150, "keml": False},
    {"code": "VITC", "name": "Vitamin C 500mg", "form": "tablet",
     "strength": "500mg", "kes": 3, "uom": "tablet", "stock": 500, "keml": False},
    {"code": "MVITS", "name": "Multivitamin Syrup", "form": "syrup",
     "strength": "200ml", "kes": 220, "uom": "bottle", "stock": 200, "keml": False},
    {"code": "COART", "name": "Coartem (Artemether/Lumefantrine)", "form": "tablet",
     "strength": "20mg/120mg", "kes": 850, "uom": "dose", "stock": 150, "keml": True},
]


async def seed_pharmacy(
    db: AsyncSession, facility_id: uuid.UUID
) -> list[uuid.UUID]:
    """Seed 15 pharmacy items idempotently."""
    ids: list[uuid.UUID] = []
    existing = (
        await db.execute(
            select(PharmacyItem).where(PharmacyItem.facility_id == facility_id)
        )
    ).scalars().all()
    by_code = {p.drug_code: p.id for p in existing}

    created = 0
    for item in PHARMACY_ITEMS:
        if item["code"] in by_code:
            ids.append(by_code[item["code"]])
            continue
        # 1-year expiry from today
        expiry = TODAY + timedelta(days=365)
        ph = PharmacyItem(
            id=_det(f"pharm:{item['code']}"),
            facility_id=facility_id,
            drug_code=item["code"],
            drug_name=item["name"],
            generic_name=item["name"],
            is_keml=item["keml"],
            dosage_form=item["form"],
            strength=item["strength"],
            current_quantity=item["stock"],
            unit_of_measure=item["uom"],
            reorder_level=20,
            buying_price_cents=_kes_to_cents(item["kes"]) // 2,
            selling_price_cents=_kes_to_cents(item["kes"]),
            expiry_date=expiry,
            manufacturer="Generic Manufacturer Ltd",
            is_active=True,
        )
        db.add(ph)
        await db.flush()
        ids.append(ph.id)
        created += 1

    print(f"  Pharmacy items: {created} created, {len(by_code)} existing")
    return ids


# ── Insurance Schemes ────────────────────────────────────────────────────────


async def seed_insurance(
    db: AsyncSession, facility_id: uuid.UUID
) -> uuid.UUID:
    """Seed SHA insurance scheme (idempotent)."""
    existing = (
        await db.execute(
            select(InsuranceScheme).where(
                InsuranceScheme.facility_id == facility_id,
                InsuranceScheme.scheme_code == "SHA",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        print("  Insurance: SHA scheme already exists")
        return existing.id

    sha = InsuranceScheme(
        id=_det("ins:SHA"),
        facility_id=facility_id,
        name="Social Health Authority",
        scheme_code="SHA",
        scheme_type="sha",
        contact_person="SHA Help Desk",
        phone="+254709000000",
        email="claims@sha.go.ke",
        rebate_percentage=80,
        is_active=True,
    )
    db.add(sha)
    await db.flush()
    print("  Insurance: SHA scheme created")
    return sha.id


# ── Accounting Periods ───────────────────────────────────────────────────────


async def seed_accounting_periods(
    db: AsyncSession, facility_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """Seed 12 monthly periods + 1 fiscal year for the current year (idempotent).

    Always creates periods for the current calendar year and all of the
    previous calendar year (so historical postings work in the demo).
    """
    by_name: dict[str, uuid.UUID] = {}
    year = TODAY.year

    existing = (
        await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.facility_id == facility_id
            )
        )
    ).scalars().all()
    existing_names = {p.name: p.id for p in existing}

    created = 0
    # Create periods for previous + current year so 30-day-old invoices
    # always land in an open period.
    for y in (year - 1, year):
        for month in range(1, 13):
            name = f"{y}-{month:02d}"
            if name in existing_names:
                by_name[name] = existing_names[name]
                continue
            start = date(y, month, 1)
            if month == 12:
                end = date(y, 12, 31)
            else:
                end = date(y, month + 1, 1) - timedelta(days=1)
            period = AccountingPeriod(
                id=_det(f"period:{name}"),
                facility_id=facility_id,
                name=name,
                start_date=start,
                end_date=end,
                status="open",
                year_end=False,
            )
            db.add(period)
            await db.flush()
            by_name[name] = period.id
            created += 1

        # Fiscal year period (overlaps monthly — used for year-end close).
        fy_name = f"FY{y}"
        if fy_name not in existing_names:
            fy = AccountingPeriod(
                id=_det(f"period:{fy_name}"),
                facility_id=facility_id,
                name=fy_name,
                start_date=date(y, 1, 1),
                end_date=date(y, 12, 31),
                status="open",
                year_end=True,
            )
            db.add(fy)
            await db.flush()
            by_name[fy_name] = fy.id
            created += 1
        else:
            by_name[fy_name] = existing_names[fy_name]

    print(f"  Accounting periods: {created} created, {len(existing_names)} existing")
    return by_name


# ── Invoices, Payments, Expenses ─────────────────────────────────────────────


async def _next_invoice_number(
    db: AsyncSession, facility_id: uuid.UUID
) -> str:
    """Generate the next invoice number for the facility."""
    count = (
        await db.execute(
            select(Invoice).where(Invoice.facility_id == facility_id)
        )
    ).scalars().all()
    n = len(count) + 1
    return f"INV-{TODAY.year}-{n:05d}"


async def ensure_billing_gl_postings(
    db: AsyncSession,
    facility_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[int, int, int]:
    """Post GL entries for existing demo invoices, payments, and expenses."""
    invoices = (
        await db.execute(select(Invoice).where(Invoice.facility_id == facility_id))
    ).scalars().all()
    invoice_posts = 0
    for inv in invoices:
        event = "invoice_insurance" if inv.payment_method == "insurance" else "invoice_cash"
        posting_date = (
            inv.finalized_at.date()
            if inv.finalized_at is not None
            else inv.created_at.date()
        )
        try:
            await post_transaction(
                db=db,
                facility_id=facility_id,
                event_type=event,
                amount=Decimal(inv.total_cents) / Decimal("100"),
                metadata={
                    "date": posting_date.isoformat(),
                    "reference_type": "invoice",
                    "reference_id": str(inv.id),
                    "description": f"{inv.invoice_number} - GL reconciliation",
                    "department_id": None,
                },
                idempotency_key=f"demo-invoice:{inv.id}",
                user_id=user_id,
            )
            invoice_posts += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  WARN: GL reconcile failed for {inv.invoice_number}: {exc}")

    payments = (
        await db.execute(select(Payment).where(Payment.facility_id == facility_id))
    ).scalars().all()
    payment_posts = 0
    for pay in payments:
        try:
            await post_transaction(
                db=db,
                facility_id=facility_id,
                event_type=(
                    "insurance_payment_received"
                    if pay.payment_method == "insurance"
                    else "payment_received"
                ),
                amount=Decimal(pay.amount_cents) / Decimal("100"),
                metadata={
                    "date": pay.paid_at.date().isoformat(),
                    "reference_type": "payment",
                    "reference_id": str(pay.id),
                    "description": f"Payment {pay.reference_number or pay.id}",
                },
                idempotency_key=f"demo-pay:{pay.id}",
                user_id=user_id,
            )
            payment_posts += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  WARN: GL reconcile failed for payment {pay.id}: {exc}")

    expense_posts = 0
    expenses: list[tuple[str, int]] = [
        ("Monthly rent", 100_000),
        ("Electricity bill", 25_000),
        ("Water bill", 5_000),
        ("Internet", 8_000),
        ("Cleaning supplies", 12_000),
        ("Office stationery", 6_500),
        ("Security services", 18_000),
        ("Generator fuel", 15_000),
    ]
    for k, (desc, kes) in enumerate(expenses, start=1):
        try:
            await post_transaction(
                db=db,
                facility_id=facility_id,
                event_type="expense_paid",
                amount=Decimal(str(kes)),
                metadata={
                    "date": (TODAY - timedelta(days=k * 3)).isoformat(),
                    "reference_type": "expense",
                    "reference_id": str(_det(f"expense:{k}")),
                    "description": desc,
                },
                idempotency_key=f"demo-expense:{k}",
                user_id=user_id,
            )
            expense_posts += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  WARN: GL reconcile failed for expense '{desc}': {exc}")

    return invoice_posts, payment_posts, expense_posts


# Mix of invoice scenarios: (label, kes_amount, payment_method, dept_code)
INVOICE_SCENARIOS: list[tuple[str, int, str, str]] = [
    ("Consultation", 500, "cash", "OPD"),
    ("Consultation + Lab", 1500, "cash", "OPD"),
    ("Pharmacy dispense", 800, "cash", "PHARM"),
    ("Specialist consult", 2500, "insurance", "OPD"),
    ("Lab panel CBC + UA", 1200, "cash", "LAB"),
    ("Lab full chem", 3500, "insurance", "LAB"),
    ("Antenatal visit", 600, "insurance", "MCH"),
    ("Pharmacy + injection", 1800, "cash", "PHARM"),
    ("X-ray chest", 2200, "insurance", "RAD"),
    ("Ultrasound", 3000, "insurance", "RAD"),
    ("Emergency triage", 1500, "cash", "ER"),
    ("ER stitches", 4500, "cash", "ER"),
    ("IPD admission day 1", 8500, "insurance", "IPD"),
    ("IPD admission day 2", 7500, "insurance", "IPD"),
    ("Diabetes review", 1200, "insurance", "OPD"),
    ("Hypertension review", 1100, "cash", "OPD"),
    ("Child immunization", 400, "cash", "MCH"),
    ("Pediatric consult", 800, "cash", "OPD"),
    ("Pharmacy refill chronic", 2500, "insurance", "PHARM"),
    ("Geriatric consult", 1200, "cash", "OPD"),
    ("Pre-op assessment", 5500, "insurance", "OPD"),
    ("Post-op follow-up", 1500, "insurance", "OPD"),
    ("Dressing change", 350, "cash", "OPD"),
    ("Family planning", 500, "insurance", "MCH"),
    ("Comprehensive checkup", 25000, "insurance", "OPD"),
]


async def seed_invoices_and_postings(
    db: AsyncSession,
    facility_id: uuid.UUID,
    patient_ids: list[uuid.UUID],
    dept_map: dict[str, uuid.UUID],
    user_id: uuid.UUID,
) -> tuple[int, int]:
    """Seed ~25 invoices spread over the last 30 days. Each is GL-posted.

    @returns (invoices_created, payments_created)
    """
    # Idempotency: skip if we already have invoices in the system.
    already = (
        await db.execute(
            select(Invoice).where(Invoice.facility_id == facility_id)
        )
    ).scalars().all()
    if already:
        inv_posts, pay_posts, expense_posts = await ensure_billing_gl_postings(
            db, facility_id, user_id
        )
        print(
            f"  Invoices: {len(already)} already exist; "
            f"GL reconciled invoices={inv_posts}, payments={pay_posts}, "
            f"expenses={expense_posts}"
        )
        return (0, 0)

    # We need encounters to attach invoices to (FK constraint).
    # Create one synthetic encounter per invoice for the demo.
    invoices_created = 0
    payments_created = 0

    for i, (label, kes, method, dept_code) in enumerate(INVOICE_SCENARIOS, start=1):
        days_ago = (i * 30) // len(INVOICE_SCENARIOS)
        inv_date = TODAY - timedelta(days=days_ago)
        patient_id = patient_ids[i % len(patient_ids)]
        dept_id = dept_map.get(dept_code)

        # Synthetic encounter
        enc = Encounter(
            id=_det(f"enc:demo:{i}"),
            facility_id=facility_id,
            patient_id=patient_id,
            encounter_type="opd",
            encounter_date=datetime.combine(inv_date, datetime.min.time(), tzinfo=timezone.utc),
            department_id=dept_id,
            status="completed",
            chief_complaint=label,
            billing_status="billed",
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(enc)
        await db.flush()

        total_cents = _kes_to_cents(kes)
        inv_num = f"INV-{TODAY.year}-{i:05d}"
        inv = Invoice(
            id=_det(f"inv:demo:{i}"),
            facility_id=facility_id,
            encounter_id=enc.id,
            patient_id=patient_id,
            invoice_number=inv_num,
            status="finalized" if method == "cash" else "partially_paid",
            payment_method=method,
            insurance_provider="SHA" if method == "insurance" else None,
            subtotal_cents=total_cents,
            total_cents=total_cents,
            paid_cents=total_cents if method == "cash" else 0,
            balance_cents=0 if method == "cash" else total_cents,
            finalized_at=NOW,
            finalized_by=user_id,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(inv)
        await db.flush()

        # Single line item (demo only)
        item = InvoiceItem(
            id=_det(f"invitem:demo:{i}"),
            facility_id=facility_id,
            invoice_id=inv.id,
            item_type="consultation" if dept_code == "OPD" else (
                "pharmacy" if dept_code == "PHARM" else (
                    "lab" if dept_code == "LAB" else "procedure"
                )
            ),
            description=label,
            quantity=1,
            unit_price_cents=total_cents,
            total_cents=total_cents,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(item)
        invoices_created += 1

        # Post to GL via the real posting engine.
        event = "invoice_cash" if method == "cash" else "invoice_insurance"
        try:
            await post_transaction(
                db=db,
                facility_id=facility_id,
                event_type=event,
                amount=Decimal(str(kes)),
                metadata={
                    "date": inv_date.isoformat(),
                    "reference_type": "invoice",
                    "reference_id": str(inv.id),
                    "description": f"{inv_num} — {label}",
                    "department_id": str(dept_id) if dept_id else None,
                },
                idempotency_key=f"demo-invoice:{inv.id}",
                user_id=user_id,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  WARN: GL post failed for {inv_num}: {exc}")

    # Sample payments — ~15 settle (full or partial) the insurance invoices
    insurance_invoices = (
        await db.execute(
            select(Invoice).where(
                Invoice.facility_id == facility_id,
                Invoice.payment_method == "insurance",
            )
        )
    ).scalars().all()

    for j, inv in enumerate(insurance_invoices[:15], start=1):
        # Mix of partial (50%) and full payments
        is_partial = j % 3 == 0
        amount_cents = inv.total_cents // 2 if is_partial else inv.total_cents
        pay = Payment(
            id=_det(f"pay:demo:{j}"),
            facility_id=facility_id,
            invoice_id=inv.id,
            patient_id=inv.patient_id,
            amount_cents=amount_cents,
            payment_method="insurance",
            reference_number=f"SHA-RCT-{j:05d}",
            received_by=user_id,
            paid_at=NOW,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(pay)
        # Post insurance receipt to GL
        try:
            await post_transaction(
                db=db,
                facility_id=facility_id,
                event_type="insurance_payment_received",
                amount=Decimal(amount_cents) / Decimal("100"),
                metadata={
                    "date": TODAY.isoformat(),
                    "reference_type": "payment",
                    "reference_id": str(pay.id),
                    "description": f"SHA remittance for {inv.invoice_number}",
                },
                idempotency_key=f"demo-pay:{pay.id}",
                user_id=user_id,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  WARN: GL post failed for payment: {exc}")
        payments_created += 1

    # Sample expenses: rent, utilities, supplies, etc.
    expenses: list[tuple[str, int]] = [
        ("Monthly rent", 100_000),
        ("Electricity bill", 25_000),
        ("Water bill", 5_000),
        ("Internet", 8_000),
        ("Cleaning supplies", 12_000),
        ("Office stationery", 6_500),
        ("Security services", 18_000),
        ("Generator fuel", 15_000),
    ]
    for k, (desc, kes) in enumerate(expenses, start=1):
        try:
            await post_transaction(
                db=db,
                facility_id=facility_id,
                event_type="expense_paid",
                amount=Decimal(str(kes)),
                metadata={
                    "date": (TODAY - timedelta(days=k * 3)).isoformat(),
                    "reference_type": "expense",
                    "reference_id": str(_det(f"expense:{k}")),
                    "description": desc,
                },
                idempotency_key=f"demo-expense:{k}",
                user_id=user_id,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  WARN: GL post failed for expense '{desc}': {exc}")

    print(
        f"  Invoices posted: {invoices_created}, "
        f"Payments: {payments_created}, "
        f"Expenses: {len(expenses)}"
    )
    return (invoices_created, payments_created)


# ── Employees, Salaries, Payroll ─────────────────────────────────────────────


EMPLOYEE_DEFINITIONS: list[dict[str, Any]] = [
    # Admin / Doctor tier — KSh 200k basic + 50k house + 30k transport
    {"staff_emp": "AIFYA-001", "name": "Wanjiku Kamau", "title": "Medical Director",
     "tier": "exec", "kra": "A009658233G", "nssf": "100000001",
     "shif": "CR1620021837701-1", "bank": "Equity Bank", "branch": "Westlands",
     "hire_months_ago": 24, "disability": False},
    {"staff_emp": "AIFYA-002", "name": "James Otieno", "title": "Doctor",
     "tier": "exec", "kra": "A009658234G", "nssf": "100000002",
     "shif": "CR1620021837702-1", "bank": "KCB", "branch": "Sarit Centre",
     "hire_months_ago": 20, "disability": False},
    {"staff_emp": "AIFYA-003", "name": "Mary Akinyi", "title": "Doctor",
     "tier": "exec", "kra": "A009658235G", "nssf": "100000003",
     "shif": "CR1620021837703-1", "bank": "Cooperative", "branch": "Westlands",
     "hire_months_ago": 18, "disability": False},
    # Nurse tier — 80k basic + 20k house + 10k transport
    {"staff_emp": "AIFYA-004", "name": "Faith Njeri", "title": "Senior Nurse",
     "tier": "nurse", "kra": "A009658236G", "nssf": "100000004",
     "shif": "CR1620021837704-1", "bank": "Equity Bank", "branch": "Westlands",
     "hire_months_ago": 16, "disability": False},
    {"staff_emp": "AIFYA-005", "name": "Grace Wanjiru", "title": "MCH Nurse",
     "tier": "nurse", "kra": "A009658237G", "nssf": "100000005",
     "shif": "CR1620021837705-1", "bank": "KCB", "branch": "Westlands",
     "hire_months_ago": 12, "disability": False},
    # Pharmacist tier — 90k basic + 25k house + 12k transport
    {"staff_emp": "AIFYA-006", "name": "Peter Mwangi", "title": "Chief Pharmacist",
     "tier": "pharmacist", "kra": "A009658238G", "nssf": "100000006",
     "shif": "CR1620021837706-1", "bank": "Equity Bank", "branch": "Sarit Centre",
     "hire_months_ago": 14, "disability": False},
    # Lab Tech tier — 70k basic + 18k house + 10k transport
    {"staff_emp": "AIFYA-007", "name": "John Kiprop", "title": "Lab Technologist",
     "tier": "lab", "kra": "A009658239G", "nssf": "100000007",
     "shif": "CR1620021837707-1", "bank": "Cooperative", "branch": "Westlands",
     "hire_months_ago": 10, "disability": True},
    # Cashier / Receptionist / HR tier — 50k + 15k + 8k
    {"staff_emp": "AIFYA-008", "name": "Ruth Achieng", "title": "Cashier",
     "tier": "support", "kra": "A009658240G", "nssf": "100000008",
     "shif": "CR1620021837708-1", "bank": "Equity Bank", "branch": "Westlands",
     "hire_months_ago": 8, "disability": False},
    {"staff_emp": "AIFYA-009", "name": "Esther Nyambura", "title": "HR Officer",
     "tier": "support", "kra": "A009658241G", "nssf": "100000009",
     "shif": "CR1620021837709-1", "bank": "KCB", "branch": "Sarit Centre",
     "hire_months_ago": 12, "disability": False},
    {"staff_emp": "AIFYA-010", "name": "David Kimani", "title": "Receptionist",
     "tier": "support", "kra": "A009658242G", "nssf": "100000010",
     "shif": "CR1620021837710-1", "bank": "Cooperative", "branch": "Westlands",
     "hire_months_ago": 6, "disability": False},
    # Cleaner / Security — 25k + 8k + 5k
    {"staff_emp": None, "name": "Mary Wanjala", "title": "Cleaner",
     "tier": "lowpay", "kra": "A009658243G", "nssf": "100000011",
     "shif": "CR1620021837711-1", "bank": "Equity Bank", "branch": "Westlands",
     "hire_months_ago": 10, "disability": False},
    {"staff_emp": None, "name": "Joseph Kamau", "title": "Security Guard",
     "tier": "lowpay", "kra": "A009658244G", "nssf": "100000012",
     "shif": "CR1620021837712-1", "bank": "KCB", "branch": "Westlands",
     "hire_months_ago": 14, "disability": False},
]

SALARY_TIERS: dict[str, tuple[int, int, int]] = {
    # tier -> (basic, house, transport) in KES
    "exec": (200_000, 50_000, 30_000),
    "nurse": (80_000, 20_000, 10_000),
    "pharmacist": (90_000, 25_000, 12_000),
    "lab": (70_000, 18_000, 10_000),
    "support": (50_000, 15_000, 8_000),
    "lowpay": (25_000, 8_000, 5_000),
}


async def seed_employees(
    db: AsyncSession,
    facility_id: uuid.UUID,
    dept_map: dict[str, uuid.UUID],
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Seed 12 payroll-grade employees + their salary records."""
    ids: list[uuid.UUID] = []
    existing = (
        await db.execute(
            select(Employee).where(Employee.facility_id == facility_id)
        )
    ).scalars().all()
    existing_by_staff_id = {e.staff_id: e.id for e in existing}

    created = 0
    for ed in EMPLOYEE_DEFINITIONS:
        staff_id_str = ed["staff_emp"] or f"AIFYA-EXTRA-{ed['nssf'][-3:]}"
        if staff_id_str in existing_by_staff_id:
            ids.append(existing_by_staff_id[staff_id_str])
            continue

        hire_date = TODAY - timedelta(days=int(ed["hire_months_ago"]) * 30)

        emp = Employee(
            id=_det(f"employee:{staff_id_str}"),
            facility_id=facility_id,
            staff_id=staff_id_str,
            full_name=ed["name"],
            kra_pin=ed["kra"],
            nssf_number=ed["nssf"],
            shif_number=ed["shif"],
            department_id=dept_map.get("ADMIN"),
            job_title=ed["title"],
            employment_type="permanent",
            hire_date=hire_date,
            is_active=True,
            bank_name=ed["bank"],
            bank_branch=ed["branch"],
            bank_account=f"01{int(ed['nssf']):010d}",
            disability_exemption=ed["disability"],
            phone=f"+25471111{ed['nssf'][-4:]}",
            email=f"{ed['name'].split()[0].lower()}.{ed['name'].split()[-1].lower()}@aifya.co.ke",
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(emp)
        await db.flush()
        ids.append(emp.id)

        basic, house, transport = SALARY_TIERS[ed["tier"]]
        salary = EmployeeSalary(
            id=_det(f"salary:{staff_id_str}"),
            facility_id=facility_id,
            employee_id=emp.id,
            basic_salary=Decimal(basic),
            house_allowance=Decimal(house),
            transport_allowance=Decimal(transport),
            other_allowances={},
            effective_from=hire_date,
            approved_by=user_id,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(salary)
        created += 1

    await db.flush()
    print(f"  Employees: {created} created, {len(existing_by_staff_id)} existing")
    return ids


async def run_demo_payroll(
    db: AsyncSession,
    facility_id: uuid.UUID,
    user_id: uuid.UUID,
) -> PayrollRun | None:
    """Run payroll for the previous month, approve, and post to GL."""
    # Previous month from today.
    if TODAY.month == 1:
        month, year = 12, TODAY.year - 1
    else:
        month, year = TODAY.month - 1, TODAY.year

    # Idempotency: skip if a run already exists for this period.
    existing_run = (
        await db.execute(
            select(PayrollRun).where(
                PayrollRun.facility_id == facility_id,
                PayrollRun.month == month,
                PayrollRun.year == year,
                PayrollRun.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if existing_run is not None:
        print(f"  Payroll: run for {year}-{month:02d} already exists ({existing_run.status})")
        return existing_run

    try:
        run = await run_monthly_payroll(
            db=db,
            facility_id=facility_id,
            month=month,
            year=year,
            user_id=user_id,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  WARN: payroll run failed: {exc}")
        return None

    # Approve so payslips are generatable.
    run.status = "approved"
    run.approved_by = user_id
    run.approved_at = NOW
    await db.flush()

    # Post to GL (uses different account codes — falls back to warning if
    # accounts don't match — that's OK for demo).
    try:
        gl_id = await post_payroll_to_gl(db=db, run=run, user_id=user_id)
        if gl_id is not None:
            run.gl_transaction_id = gl_id
            run.status = "posted"
            await db.flush()
            print(f"  Payroll: run {year}-{month:02d} approved + posted to GL")
        else:
            print(f"  Payroll: run {year}-{month:02d} approved (GL post skipped)")
    except Exception as exc:  # noqa: BLE001
        print(f"  WARN: payroll GL post failed: {exc}")
    return run


# ── Leave Requests ───────────────────────────────────────────────────────────


async def seed_leave_requests(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_ids: list[uuid.UUID],
    user_id: uuid.UUID,
) -> int:
    """Seed 5 sample leave requests."""
    if not employee_ids:
        return 0

    existing = (
        await db.execute(
            select(PayrollLeaveRequest).where(
                PayrollLeaveRequest.facility_id == facility_id
            )
        )
    ).scalars().all()
    if existing:
        print(f"  Leave requests: {len(existing)} already exist")
        return 0

    # Resolve leave types (global defaults).
    leave_types = {
        lt.name: lt.id
        for lt in (
            await db.execute(select(LeaveType).where(LeaveType.facility_id.is_(None)))
        ).scalars().all()
    }
    if not leave_types:
        print("  Leave requests: no leave types found, skipping")
        return 0

    samples: list[dict[str, Any]] = [
        {"emp_idx": 0, "type": "Annual", "days": 5, "status": "approved",
         "start_offset": -30, "reason": "Vacation"},
        {"emp_idx": 1, "type": "Sick", "days": 3, "status": "pending",
         "start_offset": -2, "reason": "Flu"},
        {"emp_idx": 4, "type": "Maternity", "days": 90, "status": "approved",
         "start_offset": 30, "reason": "Maternity leave"},
        {"emp_idx": 7, "type": "Unpaid", "days": 2, "status": "approved",
         "start_offset": -10, "reason": "Personal matters"},
        {"emp_idx": 9, "type": "Annual", "days": 7, "status": "rejected",
         "start_offset": -5, "reason": "Travel"},
    ]

    created = 0
    for s in samples:
        if s["emp_idx"] >= len(employee_ids):
            continue
        if s["type"] not in leave_types:
            continue
        start = TODAY + timedelta(days=int(s["start_offset"]))
        end = start + timedelta(days=int(s["days"]) - 1)
        deduction = Decimal("2500") if s["type"] == "Unpaid" else Decimal("0")
        lr = PayrollLeaveRequest(
            id=_det(f"leave:{s['emp_idx']}:{s['type']}"),
            facility_id=facility_id,
            employee_id=employee_ids[s["emp_idx"]],
            leave_type_id=leave_types[s["type"]],
            start_date=start,
            end_date=end,
            days_requested=s["days"],
            reason=s["reason"],
            status=s["status"],
            approved_by=user_id if s["status"] in ("approved", "rejected") else None,
            approved_at=NOW if s["status"] in ("approved", "rejected") else None,
            rejection_reason="Insufficient cover" if s["status"] == "rejected" else None,
            payroll_deduction=deduction,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(lr)
        created += 1

    await db.flush()
    print(f"  Leave requests: {created} created")
    return created


# ── Fixed Assets ─────────────────────────────────────────────────────────────


async def seed_fixed_assets(
    db: AsyncSession, facility_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    """Seed 4 sample fixed assets for the depreciation demo."""
    existing = (
        await db.execute(
            select(FixedAsset).where(FixedAsset.facility_id == facility_id)
        )
    ).scalars().all()
    if existing:
        print(f"  Fixed assets: {len(existing)} already exist")
        return 0

    # Look up the asset + depreciation accounts seeded by seed_facility_finance.
    accounts = (
        await db.execute(
            select(Account).where(Account.facility_id == facility_id)
        )
    ).scalars().all()
    by_code = {a.code: a.id for a in accounts}

    asset_acc_id = by_code.get("1500")  # Fixed Assets - Equipment
    accum_dep_id = by_code.get("1510")  # Accumulated Depreciation
    dep_exp_id = by_code.get("5020")    # Depreciation Expense
    if not asset_acc_id:
        print("  Fixed assets: required accounts missing, skipping")
        return 0

    samples: list[dict[str, Any]] = [
        {"name": "Ultrasound Machine", "tag": "ASSET-001",
         "cost": 1_200_000, "months": 60, "salvage_pct": 5},
        {"name": "X-ray Machine", "tag": "ASSET-002",
         "cost": 2_500_000, "months": 84, "salvage_pct": 10},
        {"name": "ICU Monitor", "tag": "ASSET-003",
         "cost": 350_000, "months": 60, "salvage_pct": 5},
        {"name": "Hospital Beds (5 units)", "tag": "ASSET-004",
         "cost": 80_000 * 5, "months": 120, "salvage_pct": 10},
    ]

    created = 0
    for s in samples:
        salvage = (Decimal(s["cost"]) * Decimal(s["salvage_pct"]) / Decimal(100))
        fa = FixedAsset(
            id=_det(f"asset:{s['tag']}"),
            facility_id=facility_id,
            name=s["name"],
            asset_tag=s["tag"],
            account_id=asset_acc_id,
            accumulated_depreciation_account_id=accum_dep_id,
            depreciation_expense_account_id=dep_exp_id,
            purchase_date=TODAY - timedelta(days=180),
            purchase_cost=Decimal(s["cost"]),
            useful_life_months=s["months"],
            salvage_value=salvage,
            depreciation_method="straight_line",
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(fa)
        created += 1

    await db.flush()
    print(f"  Fixed assets: {created} created")
    return created


# ── Budgets ──────────────────────────────────────────────────────────────────


async def seed_budgets(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_map: dict[str, uuid.UUID],
    dept_map: dict[str, uuid.UUID],
    user_id: uuid.UUID,
) -> int:
    """Seed ~10 budget lines for the current month."""
    existing = (
        await db.execute(
            select(Budget).where(Budget.facility_id == facility_id)
        )
    ).scalars().all()
    if existing:
        print(f"  Budgets: {len(existing)} already exist")
        return 0

    accounts = (
        await db.execute(
            select(Account).where(Account.facility_id == facility_id)
        )
    ).scalars().all()
    by_code = {a.code: a.id for a in accounts}

    current_period_name = f"{TODAY.year}-{TODAY.month:02d}"
    period_id = period_map.get(current_period_name)
    if not period_id:
        print("  Budgets: current period missing, skipping")
        return 0

    samples: list[tuple[str, str, int]] = [
        # (account_code, dept_code, kes_amount)
        ("5000", "OPD", 500_000),     # OPD Salaries
        ("5030", "OPD", 50_000),      # OPD Operating
        ("1200", "PHARM", 800_000),   # Pharmacy Inventory
        ("5000", "PHARM", 200_000),   # Pharmacy Salaries
        ("5030", "LAB", 150_000),     # Lab Reagents (op exp)
        ("5000", "LAB", 250_000),     # Lab Salaries
        ("5030", "ADMIN", 80_000),    # Admin Utilities (op exp)
        ("5030", "ADMIN", 100_000),   # Admin Rent (op exp)
        ("5000", "IPD", 600_000),     # IPD Salaries
        ("5030", "IPD", 100_000),     # IPD Supplies (op exp)
    ]

    created = 0
    for i, (acc_code, dept_code, kes) in enumerate(samples):
        acc_id = by_code.get(acc_code)
        dept_id = dept_map.get(dept_code)
        if not acc_id:
            continue
        budget = Budget(
            id=_det(f"budget:{i}:{acc_code}:{dept_code}"),
            facility_id=facility_id,
            account_id=acc_id,
            department_id=dept_id,
            period_id=period_id,
            budgeted_amount=Decimal(kes),
            approved_by=user_id,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(budget)
        created += 1

    await db.flush()
    print(f"  Budgets: {created} created")
    return created


# ── Recurring Templates ──────────────────────────────────────────────────────


async def seed_recurring_templates(
    db: AsyncSession, facility_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    """Seed 3 sample recurring transaction templates."""
    existing = (
        await db.execute(
            select(RecurringTemplate).where(
                RecurringTemplate.facility_id == facility_id
            )
        )
    ).scalars().all()
    if existing:
        print(f"  Recurring templates: {len(existing)} already exist")
        return 0

    accounts = (
        await db.execute(
            select(Account).where(Account.facility_id == facility_id)
        )
    ).scalars().all()
    by_code = {a.code: a.id for a in accounts}

    cash_id = by_code.get("1010")
    bank_id = by_code.get("1020")
    op_exp_id = by_code.get("5030")
    sal_exp_id = by_code.get("5000")
    if not all([cash_id, op_exp_id, sal_exp_id, bank_id]):
        print("  Recurring templates: required accounts missing, skipping")
        return 0

    # Last day of current month
    if TODAY.month == 12:
        last_day = date(TODAY.year, 12, 31)
    else:
        last_day = date(TODAY.year, TODAY.month + 1, 1) - timedelta(days=1)

    samples: list[dict[str, Any]] = [
        {"name": "Monthly Rent", "event": "expense_paid",
         "amount": 100_000, "debit": op_exp_id, "credit": cash_id,
         "frequency": "monthly", "next": last_day},
        {"name": "Monthly Salary Run", "event": "payroll_run",
         "amount": 1_000_000, "debit": sal_exp_id, "credit": bank_id,
         "frequency": "monthly", "next": date(TODAY.year, TODAY.month, 25)
         if TODAY.day <= 25 else (
             date(TODAY.year + (1 if TODAY.month == 12 else 0),
                  1 if TODAY.month == 12 else TODAY.month + 1, 25))},
        {"name": "Insurance Premium", "event": "expense_paid",
         "amount": 25_000, "debit": op_exp_id, "credit": cash_id,
         "frequency": "monthly",
         "next": date(TODAY.year + (1 if TODAY.month == 12 else 0),
                      1 if TODAY.month == 12 else TODAY.month + 1, 1)},
    ]

    created = 0
    for s in samples:
        rt = RecurringTemplate(
            id=_det(f"recurring:{s['name']}"),
            facility_id=facility_id,
            name=s["name"],
            event_type=s["event"],
            amount=Decimal(s["amount"]),
            account_debit_id=s["debit"],
            account_credit_id=s["credit"],
            frequency=s["frequency"],
            next_post_date=s["next"],
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(rt)
        created += 1

    await db.flush()
    print(f"  Recurring templates: {created} created")
    return created


# ── M-Pesa STK Sample Records ────────────────────────────────────────────────


async def seed_mpesa_samples(
    db: AsyncSession,
    facility_id: uuid.UUID,
    patient_ids: list[uuid.UUID],
    user_id: uuid.UUID,
) -> int:
    """Seed 5 sample M-Pesa STK Push request rows."""
    existing = (
        await db.execute(
            select(MpesaStkRequest).where(
                MpesaStkRequest.facility_id == facility_id
            )
        )
    ).scalars().all()
    if existing:
        print(f"  M-Pesa samples: {len(existing)} already exist")
        return 0

    samples: list[dict[str, Any]] = [
        {"phone": "+254712345001", "amount": 500, "status": "success",
         "result_code": 0, "receipt": "QA12CD3456"},
        {"phone": "+254712345004", "amount": 1500, "status": "success",
         "result_code": 0, "receipt": "QB45EF6789"},
        {"phone": "+254712345008", "amount": 800, "status": "pending",
         "result_code": None, "receipt": None},
        {"phone": "+254712345002", "amount": 2200, "status": "failed",
         "result_code": 1032, "receipt": None,
         "result_desc": "Request cancelled by user"},
        {"phone": "+254712345011", "amount": 1200, "status": "success",
         "result_code": 0, "receipt": "QC78GH9012"},
    ]

    created = 0
    for i, s in enumerate(samples, start=1):
        patient_id = patient_ids[i % len(patient_ids)] if patient_ids else None
        m = MpesaStkRequest(
            id=_det(f"mpesa:{i}"),
            facility_id=facility_id,
            patient_id=patient_id,
            phone_number=s["phone"],
            amount=Decimal(s["amount"]),
            reference=f"INV-{TODAY.year}-{i:05d}",
            description=f"Hospital invoice payment {i}",
            checkout_request_id=f"ws_CO_demo_{i:08d}",
            merchant_request_id=f"merchant_demo_{i:08d}",
            status=s["status"],
            result_code=s["result_code"],
            result_desc=s.get("result_desc"),
            mpesa_receipt_number=s["receipt"],
            transaction_date=NOW if s["status"] == "success" else None,
            completed_at=NOW if s["status"] != "pending" else None,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(m)
        created += 1

    await db.flush()
    print(f"  M-Pesa samples: {created} created")
    return created


# ── Clinical + Operational Modules ──────────────────────────────────────────


async def seed_hr_operations(
    db: AsyncSession,
    facility_id: uuid.UUID,
    dept_map: dict[str, uuid.UUID],
    staff_map: dict[str, uuid.UUID],
    user_id: uuid.UUID,
) -> int:
    """Seed HR profiles, shifts, assignments, leave, and attendance."""
    existing_profiles = (
        await db.execute(
            select(StaffProfile).where(StaffProfile.facility_id == facility_id)
        )
    ).scalars().all()
    created = 0
    if not existing_profiles:
        for i, staff_id in enumerate(list(staff_map.values())[:10], start=1):
            profile = StaffProfile(
                id=_det(f"staff-profile:{staff_id}"),
                facility_id=facility_id,
                staff_id=staff_id,
                date_of_birth=date(1980 + (i % 12), min(i, 12), 15),
                gender="female" if i % 2 else "male",
                national_id=f"30{i:06d}",
                kra_pin=f"A0096582{i:02d}G",
                nssf_number=f"1000000{i:03d}",
                address="Westlands, Nairobi",
                county="Nairobi",
                employment_type="permanent",
                employment_date=TODAY - timedelta(days=365 + i * 20),
                basic_salary=_kes_to_cents(60_000 + i * 5_000),
                allowances={"housing": 15000, "transport": 8000},
                annual_leave_balance=21 - (i % 5),
                qualifications=[{"name": "Clinical Practice", "year": 2018 + i % 4}],
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(profile)
            created += 1

    existing_shifts = (
        await db.execute(select(Shift).where(Shift.facility_id == facility_id))
    ).scalars().all()
    shift_ids: list[uuid.UUID] = [s.id for s in existing_shifts]
    if not existing_shifts:
        shifts = [
            ("MORNING", "Morning Shift", time(6, 0), time(14, 0), False),
            ("EVENING", "Evening Shift", time(14, 0), time(22, 0), False),
            ("NIGHT", "Night Shift", time(22, 0), time(6, 0), True),
        ]
        for code, name, start, end, is_night in shifts:
            shift = Shift(
                id=_det(f"shift:{code}"),
                facility_id=facility_id,
                code=code,
                name=name,
                start_time=start,
                end_time=end,
                duration_hours=8,
                is_night_shift=is_night,
                department_id=dept_map.get("OPD"),
                is_active=True,
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(shift)
            shift_ids.append(shift.id)
            created += 1

    existing_assignments = (
        await db.execute(
            select(ShiftAssignment).where(ShiftAssignment.facility_id == facility_id)
        )
    ).scalars().all()
    if not existing_assignments and shift_ids:
        for i, staff_id in enumerate(list(staff_map.values())[:8]):
            assignment = ShiftAssignment(
                id=_det(f"shift-assignment:{i}"),
                facility_id=facility_id,
                staff_id=staff_id,
                shift_id=shift_ids[i % len(shift_ids)],
                department_id=dept_map.get("OPD"),
                assignment_date=TODAY + timedelta(days=i % 5),
                status="confirmed",
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(assignment)
            created += 1

    existing_leave = (
        await db.execute(select(LeaveRequest).where(LeaveRequest.facility_id == facility_id))
    ).scalars().all()
    if not existing_leave:
        staff_ids = list(staff_map.values())
        for i, staff_id in enumerate(staff_ids[:4], start=1):
            lr = LeaveRequest(
                id=_det(f"hr-leave:{i}"),
                facility_id=facility_id,
                staff_id=staff_id,
                leave_type="annual" if i != 2 else "sick",
                start_date=TODAY + timedelta(days=i * 3),
                end_date=TODAY + timedelta(days=i * 3 + 2),
                days_requested=3,
                reason="Demo leave request",
                status="approved" if i % 2 else "pending",
                approved_by=user_id if i % 2 else None,
                approved_at=NOW if i % 2 else None,
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(lr)
            created += 1

    existing_attendance = (
        await db.execute(select(Attendance).where(Attendance.facility_id == facility_id))
    ).scalars().all()
    if not existing_attendance and shift_ids:
        for i, staff_id in enumerate(list(staff_map.values())[:8]):
            clock_in = datetime.combine(
                TODAY - timedelta(days=i % 4),
                time(8, 0),
                tzinfo=timezone.utc,
            )
            attendance = Attendance(
                id=_det(f"attendance:{i}"),
                facility_id=facility_id,
                staff_id=staff_id,
                shift_id=shift_ids[i % len(shift_ids)],
                attendance_date=clock_in.date(),
                clock_in=clock_in,
                clock_out=clock_in + timedelta(hours=8, minutes=15),
                status="present",
                overtime_minutes=15,
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(attendance)
            created += 1

    await db.flush()
    print(f"  HR operations: {created} created")
    return created


async def seed_clinical_workflow(
    db: AsyncSession,
    facility_id: uuid.UUID,
    patient_ids: list[uuid.UUID],
    dept_map: dict[str, uuid.UUID],
    staff_map: dict[str, uuid.UUID],
    user_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    """Seed OPD queue, appointments, notes, vitals, dx, Rx, lab, and radiology."""
    if not patient_ids:
        return {}

    doctor_id = staff_map.get("AIFYA-002", user_id)
    nurse_id = staff_map.get("AIFYA-004", user_id)
    lab_id = staff_map.get("AIFYA-007", user_id)
    pharm_id = staff_map.get("AIFYA-006", user_id)
    created = 0

    schedules = (
        await db.execute(
            select(DoctorSchedule).where(DoctorSchedule.facility_id == facility_id)
        )
    ).scalars().all()
    if not schedules:
        for dow in range(0, 5):
            schedule = DoctorSchedule(
                id=_det(f"doctor-schedule:{dow}"),
                facility_id=facility_id,
                doctor_id=doctor_id,
                department_id=dept_map.get("OPD"),
                day_of_week=dow,
                start_time=time(8, 0),
                end_time=time(16, 0),
                slot_duration_minutes=20,
                max_patients=24,
                room=f"Consultation {dow + 1}",
                consultation_type="general",
                is_active=True,
                effective_from=TODAY - timedelta(days=30),
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(schedule)
            created += 1

    appointments = (
        await db.execute(select(Appointment).where(Appointment.facility_id == facility_id))
    ).scalars().all()
    if not appointments:
        appointment_types = ["consultation", "follow_up", "anc", "dental", "lab", "radiology"]
        statuses = ["scheduled", "confirmed", "checked_in", "completed"]
        for i in range(12):
            start = time(8 + (i % 8), (i % 3) * 20)
            appt = Appointment(
                id=_det(f"appointment:{i}"),
                facility_id=facility_id,
                patient_id=patient_ids[i % len(patient_ids)],
                doctor_id=doctor_id,
                department_id=dept_map.get("OPD"),
                appointment_number=f"APT-{TODAY:%Y%m%d}-{i + 1:04d}",
                appointment_date=TODAY + timedelta(days=(i % 5) - 1),
                start_time=start,
                end_time=time(start.hour, min(start.minute + 20, 59)),
                duration_minutes=20,
                appointment_type=appointment_types[i % len(appointment_types)],
                visit_reason="Demo clinic booking",
                priority="urgent" if i == 2 else "routine",
                status=statuses[i % len(statuses)],
                checked_in_at=NOW if statuses[i % len(statuses)] in ("checked_in", "completed") else None,
                checked_in_by=nurse_id if statuses[i % len(statuses)] in ("checked_in", "completed") else None,
                room="Consultation 1",
                booked_by=user_id,
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(appt)
            created += 1

    existing_encounters = (
        await db.execute(
            select(Encounter).where(
                Encounter.facility_id == facility_id,
                Encounter.chief_complaint.like("Demo clinical workflow%"),
            )
        )
    ).scalars().all()
    encounter_ids: dict[str, uuid.UUID] = {f"encounter:{i}": e.id for i, e in enumerate(existing_encounters)}
    if not existing_encounters:
        complaints = [
            ("opd", "Cough and fever", "J06.9", "Acute upper respiratory infection"),
            ("opd", "Diabetes review", "E11.9", "Type 2 diabetes mellitus"),
            ("opd", "Hypertension review", "I10", "Essential hypertension"),
            ("mch", "Antenatal review", "Z34.9", "Supervision of normal pregnancy"),
            ("dental", "Tooth pain", "K02.9", "Dental caries"),
            ("emergency", "Abdominal pain", "R10.9", "Unspecified abdominal pain"),
        ]
        for i, (etype, complaint, icd, desc) in enumerate(complaints):
            enc = Encounter(
                id=_det(f"clinical-encounter:{i}"),
                facility_id=facility_id,
                patient_id=patient_ids[i % len(patient_ids)],
                encounter_type=etype,
                encounter_date=NOW - timedelta(days=i),
                department_id=dept_map.get("MCH" if etype == "mch" else "OPD"),
                attending_doctor_id=doctor_id,
                nurse_id=nurse_id,
                queue_number=i + 1,
                triage_category="standard",
                priority=1 if i == 5 else 0,
                status="completed",
                chief_complaint=f"Demo clinical workflow: {complaint}",
                disposition="discharged",
                billing_status="billed",
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(enc)
            await db.flush()
            encounter_ids[f"encounter:{i}"] = enc.id

            db.add(VitalSign(
                id=_det(f"vitals:{i}"),
                facility_id=facility_id,
                encounter_id=enc.id,
                patient_id=enc.patient_id,
                recorded_by=nurse_id,
                recorded_at=enc.encounter_date,
                systolic_bp=120 + i * 3,
                diastolic_bp=78 + i,
                heart_rate=76 + i * 2,
                temperature=36.7 + (i % 3) * 0.3,
                temperature_site="oral",
                respiratory_rate=18,
                oxygen_saturation=98,
                weight_kg=62 + i * 4,
                height_cm=165,
                bmi=22.8 + i,
                pain_score=i % 5,
                created_by=user_id,
                updated_by=user_id,
            ))
            db.add(Diagnosis(
                id=_det(f"diagnosis:{i}"),
                facility_id=facility_id,
                encounter_id=enc.id,
                patient_id=enc.patient_id,
                diagnosed_by=doctor_id,
                icd10_code=icd,
                icd10_description=desc,
                diagnosis_type="primary",
                clinical_status="active",
                onset_date=enc.encounter_date.date(),
                certainty="confirmed",
                is_chronic=icd in {"E11.9", "I10"},
                notes="Demo diagnosis",
                created_by=user_id,
                updated_by=user_id,
            ))
            db.add(Prescription(
                id=_det(f"prescription:{i}"),
                facility_id=facility_id,
                encounter_id=enc.id,
                patient_id=enc.patient_id,
                prescriber_id=doctor_id,
                drug_name="Paracetamol 500mg" if i % 2 == 0 else "Amoxicillin 500mg",
                drug_code="PCM500" if i % 2 == 0 else "AMX500",
                generic_name="Paracetamol" if i % 2 == 0 else "Amoxicillin",
                is_keml=True,
                dosage="500mg",
                dosage_value=500,
                dosage_unit="mg",
                route="oral",
                frequency="tds",
                duration_days=5,
                quantity=15,
                instructions="Take after meals",
                interaction_checked=True,
                interactions=[],
                status="dispensed" if i % 2 == 0 else "pending",
                dispensed_by=pharm_id if i % 2 == 0 else None,
                dispensed_at=NOW if i % 2 == 0 else None,
                dispensed_quantity=15 if i % 2 == 0 else None,
                unit_cost_cents=_kes_to_cents(5),
                total_cost_cents=_kes_to_cents(75),
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 4

    lab_orders = (
        await db.execute(select(LabOrder).where(LabOrder.facility_id == facility_id))
    ).scalars().all()
    if not lab_orders and encounter_ids:
        tests = [
            ("CBC", "Complete Blood Count", "blood", "WBC", "White Blood Cells", "6.2", 6.2, "10^9/L", "4.0-11.0"),
            ("RBS", "Random Blood Sugar", "blood", "GLU", "Glucose", "7.8", 7.8, "mmol/L", "3.9-7.8"),
            ("MAL", "Malaria RDT", "blood", "MRDT", "Malaria RDT", "Negative", None, "", "Negative"),
        ]
        for i, sample in enumerate(tests):
            code, panel, specimen, test_code, test_name, value, numeric, unit, ref = sample
            enc_id = list(encounter_ids.values())[i % len(encounter_ids)]
            patient_id = patient_ids[i % len(patient_ids)]
            order = LabOrder(
                id=_det(f"lab-order:{i}"),
                facility_id=facility_id,
                encounter_id=enc_id,
                patient_id=patient_id,
                ordered_by=doctor_id,
                order_number=f"LAB-{TODAY:%Y%m%d}-{i + 1:04d}",
                priority="urgent" if i == 1 else "routine",
                status="completed",
                specimen_type=specimen,
                specimen_collected_at=NOW - timedelta(hours=2),
                specimen_collected_by=lab_id,
                specimen_id=f"SPC-{i + 1:05d}",
                clinical_info="Demo lab order",
                total_cost_cents=_kes_to_cents(800 + i * 250),
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(order)
            await db.flush()
            db.add(LabResult(
                id=_det(f"lab-result:{i}"),
                facility_id=facility_id,
                order_id=order.id,
                patient_id=patient_id,
                performed_by=lab_id,
                verified_by=lab_id,
                test_code=test_code,
                test_name=test_name,
                panel_name=panel,
                result_value=value,
                result_numeric=numeric,
                result_unit=unit,
                reference_range=ref,
                interpretation="normal",
                status="final",
                resulted_at=NOW - timedelta(hours=1),
                verified_at=NOW,
                method=code,
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 2

    imaging_orders = (
        await db.execute(select(ImagingOrder).where(ImagingOrder.facility_id == facility_id))
    ).scalars().all()
    if not imaging_orders and encounter_ids:
        studies = [
            ("xray", "chest", "Chest X-ray PA", "Cough and fever"),
            ("ultrasound", "abdomen", "Abdominal ultrasound", "Abdominal pain"),
            ("xray", "left arm", "Left forearm X-ray", "Fall injury"),
        ]
        for i, (modality, body_part, description, indication) in enumerate(studies):
            patient_id = patient_ids[(i + 3) % len(patient_ids)]
            order = ImagingOrder(
                id=_det(f"imaging-order:{i}"),
                facility_id=facility_id,
                encounter_id=list(encounter_ids.values())[i % len(encounter_ids)],
                patient_id=patient_id,
                ordered_by=doctor_id,
                order_number=f"RAD-{TODAY:%Y%m%d}-{i + 1:04d}",
                accession_number=f"ACC-{TODAY:%Y%m%d}-{i + 1:04d}",
                modality=modality,
                body_part=body_part,
                laterality="na",
                views_requested="PA" if modality == "xray" else None,
                study_description=description,
                priority="urgent" if i == 1 else "routine",
                clinical_indication=indication,
                status="completed",
                scheduled_at=NOW - timedelta(hours=3),
                room="Radiology 1",
                performed_by=lab_id,
                performed_at=NOW - timedelta(hours=2),
                total_cost_cents=_kes_to_cents(2200 + i * 800),
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(order)
            await db.flush()
            db.add(ImagingResult(
                id=_det(f"imaging-result:{i}"),
                facility_id=facility_id,
                order_id=order.id,
                patient_id=patient_id,
                reported_by=doctor_id,
                verified_by=doctor_id,
                findings="No acute abnormality identified.",
                impression="Stable demo study.",
                recommendations="Clinical correlation advised.",
                technique="Standard departmental protocol.",
                urgency="normal",
                status="final",
                reported_at=NOW - timedelta(hours=1),
                verified_at=NOW,
                image_keys=[{"key": f"demo/radiology/{i}.dcm", "modality": modality}],
                dicom_study_uid=f"1.2.826.0.1.3680043.10.543.{i}",
                dicom_series_count=1,
                dicom_instance_count=2,
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 2

    await db.flush()
    print(f"  Clinical workflow: {created} created")
    return encounter_ids


async def seed_ipd_emergency_theatre(
    db: AsyncSession,
    facility_id: uuid.UUID,
    patient_ids: list[uuid.UUID],
    dept_map: dict[str, uuid.UUID],
    staff_map: dict[str, uuid.UUID],
    user_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    """Seed IPD wards/beds/admissions, emergency visits, and theatre cases."""
    if not patient_ids:
        return {}

    doctor_id = staff_map.get("AIFYA-003", user_id)
    nurse_id = staff_map.get("AIFYA-004", user_id)
    created = 0
    ward_ids: dict[str, uuid.UUID] = {}

    wards = (
        await db.execute(select(Ward).where(Ward.facility_id == facility_id))
    ).scalars().all()
    if wards:
        ward_ids = {w.code: w.id for w in wards}
    else:
        for code, name, ward_type, beds, charge in [
            ("MMW", "Male Medical Ward", "general", 12, 2500),
            ("FSW", "Female Surgical Ward", "surgical", 10, 3000),
            ("MAT", "Maternity Ward", "maternity", 8, 3500),
            ("ICU", "Intensive Care Unit", "icu", 4, 12000),
        ]:
            ward = Ward(
                id=_det(f"ward:{code}"),
                facility_id=facility_id,
                name=name,
                code=code,
                ward_type=ward_type,
                department_id=dept_map.get("IPD"),
                floor="1",
                total_beds=beds,
                gender_restriction="any",
                charge_per_day_cents=_kes_to_cents(charge),
                is_active=True,
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(ward)
            ward_ids[code] = ward.id
            created += 1

    beds = (
        await db.execute(select(Bed).where(Bed.facility_id == facility_id))
    ).scalars().all()
    bed_ids: list[uuid.UUID] = [b.id for b in beds]
    if not beds:
        for code, ward_id in ward_ids.items():
            for i in range(1, 5):
                bed = Bed(
                    id=_det(f"bed:{code}:{i}"),
                    facility_id=facility_id,
                    ward_id=ward_id,
                    bed_number=f"{code}-{i:02d}",
                    bed_type="icu" if code == "ICU" else "standard",
                    status="available",
                    created_by=user_id,
                    updated_by=user_id,
                )
                db.add(bed)
                bed_ids.append(bed.id)
                created += 1

    admissions = (
        await db.execute(select(Admission).where(Admission.facility_id == facility_id))
    ).scalars().all()
    admission_ids: dict[str, uuid.UUID] = {}
    if admissions:
        admission_ids = {a.admission_number: a.id for a in admissions}
    elif bed_ids:
        for i in range(3):
            enc = Encounter(
                id=_det(f"ipd-encounter:{i}"),
                facility_id=facility_id,
                patient_id=patient_ids[(i + 4) % len(patient_ids)],
                encounter_type="ipd",
                encounter_date=NOW - timedelta(days=i + 1),
                department_id=dept_map.get("IPD"),
                attending_doctor_id=doctor_id,
                nurse_id=nurse_id,
                status="admitted" if i < 2 else "discharged",
                chief_complaint="Demo IPD admission",
                disposition="admitted",
                billing_status="billed",
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(enc)
            await db.flush()
            bed_id = bed_ids[i]
            admission = Admission(
                id=_det(f"admission:{i}"),
                facility_id=facility_id,
                encounter_id=enc.id,
                patient_id=enc.patient_id,
                ward_id=list(ward_ids.values())[i % len(ward_ids)],
                bed_id=bed_id,
                admission_number=f"ADM-{TODAY:%Y%m%d}-{i + 1:04d}",
                attending_doctor_id=doctor_id,
                primary_nurse_id=nurse_id,
                status="admitted" if i < 2 else "discharged",
                admission_reason="Observation and inpatient care",
                admission_diagnosis="Pneumonia",
                admitted_from="opd",
                accommodation_type="general",
                admitted_at=NOW - timedelta(days=i + 1),
                discharged_at=NOW if i == 2 else None,
                discharged_by=doctor_id if i == 2 else None,
                discharge_type="improved" if i == 2 else None,
                discharge_summary="Recovered well and discharged.",
                length_of_stay_days=2 if i == 2 else None,
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(admission)
            admission_ids[admission.admission_number] = admission.id
            created += 2
            db.add(NursingNote(
                id=_det(f"nursing-note:{i}"),
                facility_id=facility_id,
                admission_id=admission.id,
                patient_id=enc.patient_id,
                author_id=nurse_id,
                note_type="observation",
                content="Patient stable, medication given, vitals within range.",
                shift="morning",
                severity="normal",
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 1

    emergency = (
        await db.execute(select(EmergencyVisit).where(EmergencyVisit.facility_id == facility_id))
    ).scalars().all()
    if not emergency:
        for i, color in enumerate(["red", "orange", "yellow", "green"]):
            enc = Encounter(
                id=_det(f"er-encounter:{i}"),
                facility_id=facility_id,
                patient_id=patient_ids[(i + 7) % len(patient_ids)],
                encounter_type="emergency",
                encounter_date=NOW - timedelta(hours=i + 1),
                department_id=dept_map.get("ER"),
                attending_doctor_id=doctor_id,
                nurse_id=nurse_id,
                triage_category="emergency" if color == "red" else "urgent",
                priority=4 - i,
                status="completed",
                chief_complaint="Demo emergency visit",
                disposition="discharged" if i else "admitted",
                billing_status="billed",
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(enc)
            await db.flush()
            db.add(EmergencyVisit(
                id=_det(f"emergency:{i}"),
                facility_id=facility_id,
                patient_id=enc.patient_id,
                encounter_id=enc.id,
                visit_number=f"ER-{TODAY:%Y%m%d}-{i + 1:04d}",
                arrival_time=NOW - timedelta(hours=i + 2),
                arrival_mode="ambulance" if i == 0 else "walk_in",
                brought_by="St John Ambulance" if i == 0 else None,
                chief_complaint="Chest pain" if i == 0 else "Fever and weakness",
                triage_category="emergency" if color == "red" else "urgent",
                triage_color=color,
                triage_score=8 - i,
                triage_time=NOW - timedelta(hours=i + 1),
                triaged_by=nurse_id,
                triage_vitals={"bp_systolic": 130, "hr": 92, "spo2": 97, "gcs": 15},
                assigned_doctor_id=doctor_id,
                treatment_area="resus" if i == 0 else "acute",
                treatment_started_at=NOW - timedelta(minutes=45),
                status="admitted" if i == 0 else "discharged",
                disposition="admit" if i == 0 else "discharge",
                disposition_time=NOW,
                is_resuscitation=i == 0,
                interventions=[{"procedure": "IV access", "by": str(nurse_id)}],
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 2

    theatres = (
        await db.execute(select(OperatingTheatre).where(OperatingTheatre.facility_id == facility_id))
    ).scalars().all()
    theatre_ids = [t.id for t in theatres]
    if not theatres:
        for i, name in enumerate(["Main Theatre", "Minor Theatre"], start=1):
            theatre = OperatingTheatre(
                id=_det(f"theatre:{i}"),
                facility_id=facility_id,
                name=name,
                code=f"OT-{i}",
                theatre_type="general" if i == 1 else "minor",
                status="available",
                floor="2",
                equipment=[{"name": "Anaesthesia Machine", "status": "ready"}],
                is_active=True,
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(theatre)
            theatre_ids.append(theatre.id)
            created += 1

    cases = (
        await db.execute(select(SurgicalCase).where(SurgicalCase.facility_id == facility_id))
    ).scalars().all()
    if not cases and theatre_ids:
        for i, procedure in enumerate(["Appendectomy", "Caesarean Section", "Wound Debridement"]):
            db.add(SurgicalCase(
                id=_det(f"surgical-case:{i}"),
                facility_id=facility_id,
                case_number=f"SC-{TODAY:%Y%m%d}-{i + 1:04d}",
                patient_id=patient_ids[(i + 8) % len(patient_ids)],
                theatre_id=theatre_ids[i % len(theatre_ids)],
                scheduled_date=NOW + timedelta(days=i),
                estimated_duration_min=90,
                priority="urgent" if i == 0 else "elective",
                procedure_name=procedure,
                laterality="na",
                diagnosis="Demo surgical diagnosis",
                anaesthesia_type="spinal" if i == 1 else "general",
                lead_surgeon_id=doctor_id,
                scrub_nurse_id=nurse_id,
                circulating_nurse_id=nurse_id,
                status="scheduled" if i < 2 else "completed",
                surgery_start=NOW - timedelta(hours=3) if i == 2 else None,
                surgery_end=NOW - timedelta(hours=1) if i == 2 else None,
                operative_findings="Demo operative findings",
                blood_loss_ml=150 if i == 2 else None,
                preop_checklist={"consent": True, "site_marked": True},
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 1

    await db.flush()
    print(f"  IPD/Emergency/Theatre: {created} created")
    return admission_ids


async def seed_specialty_modules(
    db: AsyncSession,
    facility_id: uuid.UUID,
    patient_ids: list[uuid.UUID],
    dept_map: dict[str, uuid.UUID],
    staff_map: dict[str, uuid.UUID],
    user_id: uuid.UUID,
) -> int:
    """Seed MCH, dental, referrals, inventory, claims, reports, SMS, and trials."""
    if not patient_ids:
        return 0

    doctor_id = staff_map.get("AIFYA-002", user_id)
    nurse_id = staff_map.get("AIFYA-005", user_id)
    dentist_id = staff_map.get("AIFYA-002", user_id)
    created = 0

    dental_charts = (
        await db.execute(select(DentalChart).where(DentalChart.facility_id == facility_id))
    ).scalars().all()
    if not dental_charts:
        for i in range(3):
            patient_id = patient_ids[(i + 4) % len(patient_ids)]
            db.add(DentalChart(
                id=_det(f"dental-chart:{i}"),
                facility_id=facility_id,
                patient_id=patient_id,
                teeth={
                    "36": {"status": "filled", "notes": "Amalgam restoration"},
                    "46": {"status": "decayed", "notes": "Needs restoration"},
                },
                periodontal_status="Mild gingivitis",
                occlusion_notes="Class I occlusion",
                notes="Demo dental chart",
                created_by=user_id,
                updated_by=user_id,
            ))
            db.add(DentalVisit(
                id=_det(f"dental-visit:{i}"),
                facility_id=facility_id,
                visit_number=f"DV-{TODAY:%Y%m%d}-{i + 1:04d}",
                patient_id=patient_id,
                dentist_id=dentist_id,
                visit_date=NOW - timedelta(days=i),
                chief_complaint="Tooth pain",
                examination_findings="Caries on lower molar",
                procedures=[{"tooth": "46", "procedure_type": "restoration"}],
                diagnosis="Dental caries",
                status="completed",
                created_by=user_id,
                updated_by=user_id,
            ))
            db.add(DentalTreatmentPlan(
                id=_det(f"dental-plan:{i}"),
                facility_id=facility_id,
                plan_number=f"DP-{TODAY:%Y%m%d}-{i + 1:04d}",
                patient_id=patient_id,
                dentist_id=dentist_id,
                diagnosis="Dental caries",
                plan_items=[{
                    "tooth": "46",
                    "procedure_type": "composite restoration",
                    "priority": "routine",
                    "estimated_cost": 350000,
                    "status": "planned",
                }],
                total_estimated_cost=_kes_to_cents(3500),
                status="approved",
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 3

    anc_profiles = (
        await db.execute(select(ANCProfile).where(ANCProfile.facility_id == facility_id))
    ).scalars().all()
    if not anc_profiles:
        mother_id = patient_ids[4 % len(patient_ids)]
        child_id = patient_ids[0]
        anc = ANCProfile(
            id=_det("anc-profile:1"),
            facility_id=facility_id,
            patient_id=mother_id,
            anc_number=f"ANC-{TODAY:%Y%m%d}-0001",
            gravida=2,
            parity=1,
            living_children=1,
            lmp_date=TODAY - timedelta(days=168),
            expected_delivery_date=TODAY + timedelta(days=112),
            first_visit_date=TODAY - timedelta(days=80),
            gestation_at_first_visit=12,
            risk_level="moderate",
            risk_factors=["previous_cs"],
            blood_group="O+",
            hiv_status="negative",
            hiv_test_date=TODAY - timedelta(days=30),
            vdrl_status="non_reactive",
            hepatitis_b="negative",
            pmtct_enrolled=True,
            status="active",
            notes="Demo ANC profile",
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(anc)
        await db.flush()
        db.add(ANCVisit(
            id=_det("anc-visit:1"),
            facility_id=facility_id,
            anc_profile_id=anc.id,
            patient_id=mother_id,
            provider_id=nurse_id,
            visit_number=2,
            visit_date=TODAY,
            gestation_weeks=24,
            weight_kg=68.5,
            bp_systolic=118,
            bp_diastolic=76,
            pulse_rate=82,
            temperature=36.8,
            urine_protein="nil",
            urine_glucose="nil",
            fundal_height_cm=24,
            fetal_heart_rate=144,
            fetal_presentation="cephalic",
            fetal_movement="present",
            hb_level=11.8,
            iron_folate_given=True,
            tetanus_dose="TT2",
            ipt_malaria_dose="IPT2",
            birth_plan_discussed=True,
            danger_signs_counselled=True,
            breastfeeding_counselled=True,
            next_visit_date=TODAY + timedelta(days=28),
            clinical_notes="Routine ANC review.",
            created_by=user_id,
            updated_by=user_id,
        ))
        child = ChildRecord(
            id=_det("child-record:1"),
            facility_id=facility_id,
            patient_id=child_id,
            mother_patient_id=mother_id,
            child_number=f"CH-{TODAY:%Y%m%d}-0001",
            date_of_birth=TODAY - timedelta(days=35),
            birth_weight_grams=3200,
            sex="female",
            place_of_birth="facility",
            birth_notification_number="BN-2026-0001",
            feeding_method="exclusive_breastfeeding",
            status="active",
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(child)
        await db.flush()
        for i, (code, name, dose) in enumerate([("BCG", "BCG", 1), ("OPV_0", "OPV 0", 0)]):
            db.add(Immunization(
                id=_det(f"immunization:{code}"),
                facility_id=facility_id,
                child_record_id=child.id,
                patient_id=child_id,
                administered_by=nurse_id,
                vaccine_code=code,
                vaccine_name=name,
                dose_number=dose,
                date_given=TODAY - timedelta(days=30 - i),
                age_at_dose_weeks=0,
                batch_number=f"KEPI-{i + 1:03d}",
                site="left_arm" if code == "BCG" else "oral",
                route="id" if code == "BCG" else "oral",
                created_by=user_id,
                updated_by=user_id,
            ))
        created += 5

    referrals = (
        await db.execute(select(Referral).where(Referral.facility_id == facility_id))
    ).scalars().all()
    if not referrals:
        for i in range(4):
            db.add(Referral(
                id=_det(f"referral:{i}"),
                facility_id=facility_id,
                referral_number=f"REF-{TODAY:%Y%m%d}-{i + 1:04d}",
                patient_id=patient_ids[(i + 2) % len(patient_ids)],
                referral_type="external" if i % 2 else "internal",
                direction="outgoing",
                referring_doctor_id=doctor_id,
                referring_department_id=dept_map.get("OPD"),
                receiving_department_id=dept_map.get("RAD") if i % 2 == 0 else None,
                receiving_facility_name="Kenyatta National Hospital" if i % 2 else None,
                receiving_facility_mfl="13023" if i % 2 else None,
                reason="Specialist review",
                clinical_notes="Demo referral note with attached summary.",
                diagnosis="Hypertension",
                urgency="urgent" if i == 0 else "routine",
                referral_date=NOW - timedelta(days=i),
                status="sent" if i < 3 else "completed",
                response_date=NOW if i == 3 else None,
                response_notes="Patient reviewed and returned to facility.",
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 1

    inventory_items = (
        await db.execute(select(InventoryItem).where(InventoryItem.facility_id == facility_id))
    ).scalars().all()
    inventory_ids: list[uuid.UUID] = [item.id for item in inventory_items]
    if not inventory_items:
        for i, item in enumerate([
            ("GLOVES-M", "Examination Gloves Medium", "consumable", "box", 450, 120),
            ("SYR-5ML", "5ml Syringes", "consumable", "piece", 8, 1000),
            ("GAUZE", "Sterile Gauze", "surgical", "pack", 120, 250),
            ("REAG-CBC", "CBC Reagent Pack", "reagent", "pack", 8500, 12),
            ("PAPER-A4", "A4 Printing Paper", "stationery", "ream", 650, 50),
        ]):
            code, name, category, uom, cost, stock = item
            inv = InventoryItem(
                id=_det(f"inventory-item:{code}"),
                facility_id=facility_id,
                item_code=code,
                name=name,
                category=category,
                unit_of_measure=uom,
                unit_cost=_kes_to_cents(cost),
                current_stock=stock,
                reorder_level=20,
                reorder_quantity=100,
                max_stock=2000,
                store_location="Main Store",
                department_id=dept_map.get("LAB") if category == "reagent" else dept_map.get("ADMIN"),
                is_active=True,
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(inv)
            inventory_ids.append(inv.id)
            db.add(InventoryTransaction(
                id=_det(f"inventory-opening:{code}"),
                facility_id=facility_id,
                item_id=inv.id,
                transaction_type="opening",
                quantity=stock,
                balance_after=stock,
                unit_cost=_kes_to_cents(cost),
                total_cost=_kes_to_cents(cost * stock),
                transaction_date=NOW - timedelta(days=7),
                reference_number=f"OPEN-{code}",
                reason="Opening demo stock",
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 2

    suppliers = (
        await db.execute(select(Supplier).where(Supplier.facility_id == facility_id))
    ).scalars().all()
    supplier_id = suppliers[0].id if suppliers else _det("supplier:medsurg")
    if not suppliers:
        db.add(Supplier(
            id=supplier_id,
            facility_id=facility_id,
            name="MediSurg Supplies Kenya",
            supplier_code="SUP-001",
            contact_person="Jane Njeri",
            phone="+254722000111",
            email="orders@medisurg.example",
            address="Industrial Area, Nairobi",
            kra_pin="P051234567A",
            payment_terms="net_30",
            category="medical",
            rating=5,
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        ))
        created += 1

    pos = (
        await db.execute(select(PurchaseOrder).where(PurchaseOrder.facility_id == facility_id))
    ).scalars().all()
    if not pos and inventory_ids:
        po = PurchaseOrder(
            id=_det("purchase-order:1"),
            facility_id=facility_id,
            po_number=f"PO-{TODAY:%Y%m%d}-0001",
            supplier_id=supplier_id,
            order_date=NOW - timedelta(days=2),
            expected_delivery=NOW + timedelta(days=5),
            status="approved",
            subtotal=_kes_to_cents(45_000),
            tax_amount=_kes_to_cents(7_200),
            total_amount=_kes_to_cents(52_200),
            approved_by=user_id,
            approved_at=NOW - timedelta(days=1),
            delivery_address="Aifya Demo Hospital Main Store",
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(po)
        await db.flush()
        db.add(PurchaseOrderItem(
            id=_det("purchase-order-item:1"),
            facility_id=facility_id,
            purchase_order_id=po.id,
            item_id=inventory_ids[0],
            quantity_ordered=100,
            quantity_received=0,
            unit_cost=_kes_to_cents(450),
            total_cost=_kes_to_cents(45_000),
            created_by=user_id,
            updated_by=user_id,
        ))
        created += 2

    scheme = (
        await db.execute(
            select(InsuranceScheme).where(
                InsuranceScheme.facility_id == facility_id,
                InsuranceScheme.scheme_code == "SHA",
            )
        )
    ).scalar_one_or_none()
    claims = (
        await db.execute(select(InsuranceClaim).where(InsuranceClaim.facility_id == facility_id))
    ).scalars().all()
    if scheme and not claims:
        invoices = (
            await db.execute(select(Invoice).where(Invoice.facility_id == facility_id))
        ).scalars().all()
        for i, patient_id in enumerate(patient_ids[:5]):
            member = f"SHA{i + 1:09d}"
            db.add(PatientInsurance(
                id=_det(f"patient-insurance:{i}"),
                facility_id=facility_id,
                patient_id=patient_id,
                scheme_id=scheme.id,
                member_number=member,
                principal_name="Self",
                relationship="self",
                valid_from=NOW - timedelta(days=30),
                valid_to=NOW + timedelta(days=365),
                is_active=True,
                created_by=user_id,
                updated_by=user_id,
            ))
            inv = invoices[i % len(invoices)] if invoices else None
            db.add(InsuranceClaim(
                id=_det(f"insurance-claim:{i}"),
                facility_id=facility_id,
                claim_number=f"CLM-{TODAY:%Y%m%d}-{i + 1:04d}",
                patient_id=patient_id,
                scheme_id=scheme.id,
                invoice_id=inv.id if inv else None,
                encounter_id=inv.encounter_id if inv else None,
                member_number=member,
                claim_amount=_kes_to_cents(3500 + i * 800),
                approved_amount=_kes_to_cents(3000 + i * 500),
                paid_amount=_kes_to_cents(2500 + i * 400),
                status="paid" if i < 2 else "submitted",
                submitted_date=NOW - timedelta(days=3),
                claim_items=[{"service": "OPD consultation", "amount": 150000}],
                diagnosis_codes=["J06.9"],
                sha_reference=f"SHA-REF-{i + 1:05d}",
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 2
        db.add(PreAuthorization(
            id=_det("preauth:1"),
            facility_id=facility_id,
            auth_number=f"PA-{TODAY:%Y%m%d}-0001",
            patient_id=patient_ids[3 % len(patient_ids)],
            scheme_id=scheme.id,
            member_number="SHA000000004",
            service_description="Elective surgical procedure",
            estimated_cost=_kes_to_cents(85_000),
            approved_amount=_kes_to_cents(70_000),
            diagnosis="Cholelithiasis",
            status="approved",
            request_date=NOW - timedelta(days=4),
            response_date=NOW - timedelta(days=2),
            valid_until=NOW + timedelta(days=30),
            created_by=user_id,
            updated_by=user_id,
        ))
        created += 1

    templates = (
        await db.execute(select(ReportTemplate).where(ReportTemplate.facility_id == facility_id))
    ).scalars().all()
    if not templates:
        for i, (code, name, category, dept) in enumerate([
            ("MOH_705A", "MOH 705A Outpatient Morbidity", "moh", "opd"),
            ("PHARMACY_STOCK", "Pharmacy Stock Status", "operational", "pharmacy"),
            ("FINANCE_DAILY", "Daily Revenue Summary", "financial", "billing"),
        ]):
            tpl = ReportTemplate(
                id=_det(f"report-template:{code}"),
                facility_id=facility_id,
                name=name,
                code=code,
                description="Demo report template",
                category=category,
                department=dept,
                report_type="summary",
                parameters_schema={"type": "object"},
                query_config={"source": "demo"},
                columns_config=[{"key": "metric", "label": "Metric"}],
                is_scheduled=i == 0,
                schedule_cron="0 8 * * *" if i == 0 else None,
                moh_form_number="MOH 705A" if i == 0 else None,
                reporting_period="monthly",
                created_by=user_id,
                updated_by=user_id,
            )
            db.add(tpl)
            db.add(GeneratedReport(
                id=_det(f"generated-report:{code}"),
                facility_id=facility_id,
                template_id=tpl.id,
                title=f"{name} - Demo",
                report_number=f"RPT-{TODAY:%Y%m%d}-{i + 1:04d}",
                parameters={"demo": True},
                date_from=TODAY - timedelta(days=30),
                date_to=TODAY,
                result_data={"rows": [{"metric": "Patients", "value": len(patient_ids)}]},
                summary_data={"patients": len(patient_ids), "status": "complete"},
                row_count=1,
                status="completed",
                format="json",
                generated_by=user_id,
                generated_at=NOW,
                expires_at=NOW + timedelta(days=30),
                created_by=user_id,
                updated_by=user_id,
            ))
            created += 2

    campaigns = (
        await db.execute(select(SmsCampaign).where(SmsCampaign.facility_id == facility_id))
    ).scalars().all()
    if not campaigns:
        campaign = SmsCampaign(
            id=_det("sms-campaign:1"),
            facility_id=facility_id,
            name="Clinic appointment reminders",
            message="Aifya Demo Hospital: please remember your appointment tomorrow.",
            recipient_count=5,
            sent_count=4,
            failed_count=1,
            status="completed",
            completed_at=NOW,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(campaign)
        for i in range(5):
            db.add(SmsDeliveryLog(
                id=_det(f"sms-delivery:{i}"),
                facility_id=facility_id,
                campaign_id=campaign.id,
                phone_number=f"+254712345{i + 1:03d}",
                message=campaign.message,
                status="delivered" if i < 4 else "failed",
                provider_message_id=f"MSG-DEMO-{i + 1:04d}",
                cost=Decimal("0.85"),
                sent_at=NOW - timedelta(minutes=10),
                delivered_at=NOW - timedelta(minutes=8) if i < 4 else None,
                error_msg="Invalid number" if i == 4 else None,
                created_by=user_id,
                updated_by=user_id,
            ))
        created += 6

    trials = (
        await db.execute(select(ClinicalTrial).where(ClinicalTrial.facility_id == facility_id))
    ).scalars().all()
    if not trials:
        trial = ClinicalTrial(
            id=_det("trial:diabetes"),
            facility_id=facility_id,
            trial_code="AIFYA-DM-001",
            pactr_number="PACTR202606001",
            title="Pragmatic Diabetes Follow-up Study in Kenyan Primary Care",
            short_title="Aifya Diabetes Follow-up",
            phase="observational",
            study_type="observational",
            therapeutic_area="Endocrinology",
            sponsor="Aifya Research Network",
            principal_investigator_id=doctor_id,
            co_investigators=[str(nurse_id)],
            irb_approval_number="IRB-AFY-2026-001",
            irb_approval_date=TODAY - timedelta(days=60),
            irb_expiry_date=TODAY + timedelta(days=305),
            ethics_committee="Aifya Demo ERC",
            protocol_version="1.0",
            protocol_date=TODAY - timedelta(days=70),
            inclusion_criteria=["Age >= 18", "Type 2 diabetes diagnosis"],
            exclusion_criteria=["Pregnancy", "Severe renal impairment"],
            target_enrollment=120,
            redcap_sync_enabled=False,
            redcap_sync_mode="push_only",
            status="recruiting",
            start_date=TODAY - timedelta(days=30),
            end_date=TODAY + timedelta(days=365),
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(trial)
        await db.flush()
        participant = TrialParticipant(
            id=_det("trial-participant:1"),
            facility_id=facility_id,
            trial_id=trial.id,
            patient_id=patient_ids[9 % len(patient_ids)],
            participant_number="DM-001-0001",
            randomization_arm="standard-care",
            status="active",
            screening_date=NOW - timedelta(days=10),
            screened_by=doctor_id,
            eligibility_check={"eligible": True},
            ai_eligibility_score=0.91,
            consent_version="1.0",
            consent_date=NOW - timedelta(days=9),
            enrollment_date=NOW - timedelta(days=8),
            enrolled_by=doctor_id,
            redcap_sync_status="synced",
            created_by=user_id,
            updated_by=user_id,
        )
        schedule = TrialVisitSchedule(
            id=_det("trial-schedule:v1"),
            trial_id=trial.id,
            visit_code="V1",
            visit_name="Baseline",
            day_from_enrollment=0,
            window_before_days=0,
            window_after_days=7,
            required_assessments=["HbA1c", "Blood pressure", "Medication review"],
            sort_order=1,
        )
        db.add(participant)
        db.add(schedule)
        await db.flush()
        db.add(TrialParticipantVisit(
            id=_det("trial-participant-visit:1"),
            facility_id=facility_id,
            participant_id=participant.id,
            schedule_id=schedule.id,
            scheduled_date=TODAY - timedelta(days=8),
            actual_date=TODAY - timedelta(days=8),
            status="completed",
            assessments_completed=["HbA1c", "Blood pressure"],
            redcap_synced=True,
            redcap_sync_at=NOW - timedelta(days=7),
            created_by=user_id,
            updated_by=user_id,
        ))
        db.add(TrialAdverseEvent(
            id=_det("trial-ae:1"),
            facility_id=facility_id,
            participant_id=participant.id,
            trial_id=trial.id,
            ae_term="Mild nausea",
            ctcae_grade=1,
            severity="mild",
            is_serious=False,
            relatedness="unlikely",
            onset_date=TODAY - timedelta(days=5),
            outcome="resolved",
            action_taken="none",
            reported_by=doctor_id,
            reported_date=NOW - timedelta(days=4),
            created_by=user_id,
            updated_by=user_id,
        ))
        db.add(TrialAIScreening(
            id=_det("trial-ai-screening:1"),
            facility_id=facility_id,
            patient_id=patient_ids[9 % len(patient_ids)],
            trial_id=trial.id,
            eligibility_score=0.91,
            criteria_met=["Age >= 18", "Type 2 diabetes diagnosis"],
            criteria_not_met=[],
            criteria_unknown=["Latest HbA1c"],
            ai_reasoning="Demo patient has diabetes diagnosis and active follow-up.",
            model_version="demo",
            investigator_reviewed=True,
            investigator_id=doctor_id,
            investigator_decision="proceed_to_screen",
        ))
        created += 6

    await db.flush()
    print(f"  Specialty/admin modules: {created} created")
    return created


# ── Reset (soft delete) ──────────────────────────────────────────────────────


async def reset_demo_data(db: AsyncSession) -> None:
    """Soft-delete all demo facility data (is_deleted=True)."""
    fac = (
        await db.execute(
            select(Facility).where(Facility.code == DEMO_FACILITY_CODE)
        )
    ).scalar_one_or_none()
    if fac is None:
        print("No demo facility found, nothing to reset.")
        return

    facility_id = fac.id
    print(f"Resetting demo data for facility {facility_id}...")

    # Tables with AuditMixin (have is_deleted) — flag them.
    tables_with_soft_delete = [
        Department, Staff, Patient, Encounter, Invoice, InvoiceItem, Payment,
        PharmacyItem, InsuranceScheme, Account, AccountingPeriod, Budget,
        FixedAsset, RecurringTemplate, Employee, EmployeeSalary, PayrollRun,
        PayrollLeaveRequest, MpesaStkRequest, DoctorSchedule, Appointment,
        StaffProfile, Shift, ShiftAssignment, LeaveRequest, Attendance,
        VitalSign, Diagnosis, Prescription, LabOrder, LabResult, ImagingOrder,
        ImagingResult, Ward, Bed, Admission, NursingNote, EmergencyVisit,
        OperatingTheatre, SurgicalCase, DentalChart, DentalVisit,
        DentalTreatmentPlan, ANCProfile, ANCVisit, ChildRecord, Immunization,
        Referral, InventoryItem, InventoryTransaction, Supplier, PurchaseOrder,
        PurchaseOrderItem, PatientInsurance, InsuranceClaim, PreAuthorization,
        ReportTemplate, GeneratedReport, SmsCampaign, SmsDeliveryLog,
        ClinicalTrial, TrialParticipant, TrialParticipantVisit,
        TrialAdverseEvent,
    ]
    for model in tables_with_soft_delete:
        await db.execute(
            update(model)
            .where(model.facility_id == facility_id)
            .values(is_deleted=True, deleted_at=NOW)
        )
    # Facility itself: is_active=False (no is_deleted on Facility model).
    fac.is_active = False
    await db.flush()
    print("Reset complete (soft delete).")


# ── Orchestration ────────────────────────────────────────────────────────────


async def main(reset: bool = False) -> None:
    """Run the full demo seed.

    @param reset: if True, soft-delete all demo facility data and exit.
    """
    async with async_session() as db:
        try:
            if reset:
                await reset_demo_data(db)
                await db.commit()
                return

            print("\n=== Aifya Demo Seed ===\n")

            print("[1] Facility")
            fac = await get_or_create_facility(db)
            facility_id = fac.id
            # Use the admin staff UUID once it exists; for the early
            # passes the user_id is the deterministic admin staff ID.
            admin_staff_id = _det("staff:AIFYA-001")

            print("\n[2] Departments")
            dept_map = await seed_departments(db, facility_id)

            print("\n[3] Staff")
            staff_map = await seed_staff(db, facility_id, dept_map)
            admin_staff_id = (
                staff_map.get("AIFYA-LOCAL-ADMIN")
                or staff_map.get("AIFYA-001", admin_staff_id)
            )

            print("\n[4] Patients")
            patient_ids = await seed_patients(db, facility_id)

            print("\n[5] Pharmacy Items")
            await seed_pharmacy(db, facility_id)

            print("\n[6] SHA Insurance Scheme")
            await seed_insurance(db, facility_id)

            print("\n[7] Finance: Chart of Accounts + Posting Rules")
            fin_summary = await seed_facility_finance(
                db, facility_id, admin_staff_id
            )
            print(
                f"  Accounts: {fin_summary['accounts_created']}, "
                f"Posting rules: {fin_summary['rules_created']}"
            )

            print("\n[8] Accounting Periods")
            period_map = await seed_accounting_periods(db, facility_id)

            # Finance needs to be committed before invoices can post,
            # because the posting engine reads accounts/rules in a
            # SAVEPOINT.
            await db.flush()

            print("\n[9] Invoices, Payments, Expenses (with GL postings)")
            await seed_invoices_and_postings(
                db, facility_id, patient_ids, dept_map, admin_staff_id
            )

            print("\n[10] Payroll: Statutory Defaults (PAYE, NSSF, SHIF, HL)")
            await seed_payroll_defaults(db)

            print("\n[11] Employees + Salaries")
            employee_ids = await seed_employees(
                db, facility_id, dept_map, admin_staff_id
            )

            print("\n[12] Demo Payroll Run (previous month)")
            await run_demo_payroll(db, facility_id, admin_staff_id)

            print("\n[13] Leave Requests")
            await seed_leave_requests(
                db, facility_id, employee_ids, admin_staff_id
            )

            print("\n[14] Fixed Assets")
            await seed_fixed_assets(db, facility_id, admin_staff_id)

            print("\n[15] Budgets")
            await seed_budgets(
                db, facility_id, period_map, dept_map, admin_staff_id
            )

            print("\n[16] Recurring Templates")
            await seed_recurring_templates(db, facility_id, admin_staff_id)

            print("\n[17] M-Pesa Sample Records")
            await seed_mpesa_samples(db, facility_id, patient_ids, admin_staff_id)

            print("\n[18] HR Operations")
            await seed_hr_operations(
                db, facility_id, dept_map, staff_map, admin_staff_id
            )

            print("\n[19] Clinical Workflow")
            await seed_clinical_workflow(
                db, facility_id, patient_ids, dept_map, staff_map, admin_staff_id
            )

            print("\n[20] IPD, Emergency, Theatre")
            await seed_ipd_emergency_theatre(
                db, facility_id, patient_ids, dept_map, staff_map, admin_staff_id
            )

            print("\n[21] Specialty + Admin Modules")
            await seed_specialty_modules(
                db, facility_id, patient_ids, dept_map, staff_map, admin_staff_id
            )

            await db.commit()
            print_summary(facility_id)

        except Exception:
            await db.rollback()
            raise


def print_summary(facility_id: uuid.UUID) -> None:
    """Print a clear post-seed summary with credentials."""
    print(
        "\n"
        "=== AIFYA DEMO SEED COMPLETE ===\n"
        f"Facility: {DEMO_FACILITY_NAME} ({DEMO_FACILITY_CODE})\n"
        f"Facility ID: {facility_id}\n"
        f"Patients: {len(PATIENTS)}\n"
        f"Staff: {len(STAFF_DEFINITIONS)}\n"
        f"Employees (payroll): {len(EMPLOYEE_DEFINITIONS)}\n"
        f"Pharmacy items: {len(PHARMACY_ITEMS)}\n"
        f"Invoices: {len(INVOICE_SCENARIOS)}\n"
        "Appointments, OPD notes, vitals, diagnoses, prescriptions: seeded\n"
        "Lab, radiology, IPD, emergency, theatre, dental, MCH: seeded\n"
        "Inventory, referrals, insurance claims, reports, SMS, trials: seeded\n"
        "GL transactions: invoices + payments + expenses reconciled\n"
        "Payroll runs: 1 (approved; GL bridge posts when account mappings match)\n"
        "\n"
        "DEMO USERS (create these in Keycloak separately):\n"
        "  admin@aifya.co.ke   / DemoAdmin2026!  -- Admin / Finance\n"
        "  doctor@aifya.co.ke  / DemoDoctor2026! -- Doctor\n"
        "  nurse@aifya.co.ke   / DemoNurse2026!  -- Nurse\n"
        "  pharmacy@aifya.co.ke/ DemoPharm2026!  -- Pharmacist\n"
        "  lab@aifya.co.ke     / DemoLab2026!    -- Lab Tech\n"
        "  cashier@aifya.co.ke / DemoCash2026!   -- Cashier\n"
        "  hr@aifya.co.ke      / DemoHR2026!     -- HR Admin\n"
        "  reception@aifya.co.ke / DemoRec2026!  -- Receptionist\n"
        "\n"
        "NOTE: This script seeds the database only. A Keycloak admin must\n"
        "create the matching users in the 'aifya' realm with the same\n"
        "emails before login will work. Each Staff row has a deterministic\n"
        "keycloak_user_id which the Keycloak users should be linked to,\n"
        "or you can update the Staff.keycloak_user_id after creating the\n"
        "Keycloak users.\n"
        "\n"
        "Next steps:\n"
        "  1. Visit http://localhost:3000\n"
        "  2. Log in with one of the credentials above\n"
        "  3. Navigate to /finance, /hr/payroll, /performance\n"
        "================================="
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    p = argparse.ArgumentParser(
        description="Seed (or reset) the Aifya demo dataset."
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Soft-delete all data for the demo facility (is_deleted=True).",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(reset=args.reset))
