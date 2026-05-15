"""HR/Payroll module REST router.

All endpoints are tenant-scoped via `current_user.facility_id`. The
service layer handles all business logic — no business logic in this
router.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.models.payroll import (
    Employee,
    EmployeeSalary,
    NSSFTier,
    PAYEBand,
    PayrollLineItem,
    PayrollRun,
    StatutoryRate,
)
from app.models.payroll_extra import LeaveType
from app.schemas.payroll import (
    EmployeeCreate,
    EmployeeListItem,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
    LeaveApprovalRequest,
    LeaveRequestCreate,
    LeaveRequestResponse,
    LeaveTypeResponse,
    NSSFTierResponse,
    P9Response,
    P9Row,
    PAYEBandResponse,
    PayrollLineItemResponse,
    PayrollRunCreate,
    PayrollRunListResponse,
    PayrollRunResponse,
    SalaryStructureCreate,
    SalaryStructureResponse,
    StatutoryRateCreate,
    StatutoryRateResponse,
)
from app.services.payroll.engine import run_monthly_payroll
from app.services.payroll.exports import render_schedule
from app.services.payroll.gl_integration import post_payroll_to_gl
from app.services.payroll.leave import (
    approve_leave_request,
    reject_leave_request,
    submit_leave_request,
)
from app.services.payroll.payslip import (
    PayslipNotAvailableError,
    generate_payslip,
)
from app.services.payroll.reports import (
    generate_p9,
    get_employee_turnover,
    get_headcount_report,
    get_leave_utilisation,
    get_monthly_payroll_summary,
    get_nssf_schedule,
    get_paye_schedule,
    get_payroll_cost_trend,
    get_shif_schedule,
)

router = APIRouter(dependencies=[Depends(require_module("hr"))])


# ── Employees ──────────────────────────────────────────────────────────────


@router.get("/employees", response_model=EmployeeListResponse)
async def list_employees(
    department_id: uuid.UUID | None = Query(None),
    active_only: bool = Query(True),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmployeeListResponse:
    """List employees in the current facility.

    @param department_id: Optional department filter
    @param active_only: Only is_active = True
    @param search: Match against full_name / staff_id (ILIKE)
    @returns Paged employees
    """
    stmt = select(Employee).where(
        Employee.facility_id == current_user.facility_id,
        Employee.is_deleted.is_(False),
    )
    if active_only:
        stmt = stmt.where(Employee.is_active.is_(True))
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Employee.full_name.ilike(pattern),
                Employee.staff_id.ilike(pattern),
            )
        )
    stmt = stmt.order_by(Employee.full_name.asc())
    rows = (await db.execute(stmt)).scalars().all()
    items = [EmployeeListItem.model_validate(e) for e in rows]
    return EmployeeListResponse(items=items, total=len(items))


@router.post(
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_employee(
    data: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("admin", "facility_admin", "hr_admin")),
) -> EmployeeResponse:
    """Create a payroll-grade employee record."""
    emp = Employee(
        facility_id=current_user.facility_id,
        **data.model_dump(),
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(emp)
    await db.flush()
    await db.refresh(emp)
    return EmployeeResponse.model_validate(emp)


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmployeeResponse:
    """Fetch a single employee."""
    emp = (
        (
            await db.execute(
                select(Employee).where(
                    Employee.id == employee_id,
                    Employee.facility_id == current_user.facility_id,
                    Employee.is_deleted.is_(False),
                )
            )
        )
        .scalars()
        .first()
    )
    if emp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return EmployeeResponse.model_validate(emp)


@router.patch("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: uuid.UUID,
    data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("admin", "facility_admin", "hr_admin")),
) -> EmployeeResponse:
    """Patch an employee record."""
    emp = (
        (
            await db.execute(
                select(Employee).where(
                    Employee.id == employee_id,
                    Employee.facility_id == current_user.facility_id,
                    Employee.is_deleted.is_(False),
                )
            )
        )
        .scalars()
        .first()
    )
    if emp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(emp, field, value)
    emp.updated_by = current_user.user_id
    await db.flush()
    await db.refresh(emp)
    return EmployeeResponse.model_validate(emp)


@router.post(
    "/employees/{employee_id}/salaries",
    response_model=SalaryStructureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_salary(
    employee_id: uuid.UUID,
    data: SalaryStructureCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("admin", "facility_admin", "hr_admin")),
) -> SalaryStructureResponse:
    """Add a salary effective record (HR admin only). Closes the previous
    open record by setting its `effective_to` to (effective_from − 1)."""
    emp = (
        (
            await db.execute(
                select(Employee).where(
                    Employee.id == employee_id,
                    Employee.facility_id == current_user.facility_id,
                    Employee.is_deleted.is_(False),
                )
            )
        )
        .scalars()
        .first()
    )
    if emp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Close any currently-open record
    open_records = (
        (
            await db.execute(
                select(EmployeeSalary).where(
                    EmployeeSalary.employee_id == employee_id,
                    EmployeeSalary.facility_id == current_user.facility_id,
                    EmployeeSalary.is_deleted.is_(False),
                    EmployeeSalary.effective_to.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for sal in open_records:
        sal.effective_to = date.fromordinal(data.effective_from.toordinal() - 1)

    salary = EmployeeSalary(
        facility_id=current_user.facility_id,
        employee_id=employee_id,
        basic_salary=data.basic_salary,
        house_allowance=data.house_allowance,
        transport_allowance=data.transport_allowance,
        other_allowances={k: str(v) for k, v in data.other_allowances.items()},
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        approved_by=current_user.user_id,
        notes=data.notes,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(salary)
    await db.flush()
    await db.refresh(salary)
    return SalaryStructureResponse.model_validate(salary)


# ── Payroll runs ───────────────────────────────────────────────────────────


@router.post(
    "/runs",
    response_model=PayrollRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payroll_run(
    data: PayrollRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("admin", "facility_admin", "hr_officer", "hr_admin")),
    x_idempotency_key: str | None = Header(None),
) -> PayrollRunResponse:
    """Calculate a draft payroll run (HR officer).

    @param x_idempotency_key: Optional idempotency key header (logged for audit;
        engine rejects duplicate active runs by month/year naturally).
    """
    _ = x_idempotency_key  # informational; dedup enforced by month/year uniqueness
    try:
        run = await run_monthly_payroll(
            db=db,
            facility_id=current_user.facility_id,
            month=data.month,
            year=data.year,
            user_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return await _build_run_response(db, current_user.facility_id, run)


@router.get("/runs", response_model=PayrollRunListResponse)
async def list_payroll_runs(
    year: int | None = Query(None),
    run_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PayrollRunListResponse:
    """List payroll runs."""
    stmt = select(PayrollRun).where(
        PayrollRun.facility_id == current_user.facility_id,
        PayrollRun.is_deleted.is_(False),
    )
    if year is not None:
        stmt = stmt.where(PayrollRun.year == year)
    if run_status is not None:
        stmt = stmt.where(PayrollRun.status == run_status)
    stmt = stmt.order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
    rows = (await db.execute(stmt)).scalars().all()
    items = [PayrollRunResponse.model_validate(r) for r in rows]
    return PayrollRunListResponse(items=items, total=len(items))


@router.get("/runs/{run_id}", response_model=PayrollRunResponse)
async def get_payroll_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PayrollRunResponse:
    """Get a payroll run with all line items."""
    run = (
        (
            await db.execute(
                select(PayrollRun).where(
                    PayrollRun.id == run_id,
                    PayrollRun.facility_id == current_user.facility_id,
                    PayrollRun.is_deleted.is_(False),
                )
            )
        )
        .scalars()
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found")
    return await _build_run_response(db, current_user.facility_id, run)


@router.post("/runs/{run_id}/approve", response_model=PayrollRunResponse)
async def approve_payroll_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("admin", "facility_admin", "finance_admin")),
) -> PayrollRunResponse:
    """Approve a draft run; triggers GL posting (gracefully degrades)."""
    run = (
        (
            await db.execute(
                select(PayrollRun).where(
                    PayrollRun.id == run_id,
                    PayrollRun.facility_id == current_user.facility_id,
                    PayrollRun.is_deleted.is_(False),
                )
            )
        )
        .scalars()
        .first()
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found")
    if run.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve run in status '{run.status}'",
        )

    run.status = "approved"
    run.approved_by = current_user.user_id
    run.approved_at = datetime.now(UTC)
    run.updated_by = current_user.user_id
    await db.flush()

    # Post to GL (best-effort)
    txn_id = await post_payroll_to_gl(db=db, run=run, user_id=current_user.user_id)
    if txn_id is not None:
        run.gl_transaction_id = txn_id
        run.status = "posted"
        await db.flush()

    await db.refresh(run)
    return await _build_run_response(db, current_user.facility_id, run)


@router.get("/runs/{run_id}/payslip/{employee_id}")
async def get_run_payslip(
    run_id: uuid.UUID,
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Render and download an individual payslip PDF.

    Access control: HR/finance admins can download any payslip; otherwise the
    requester may only download their own payslip (matched via the employee
    record's email == JWT email). Other users get 403.
    """
    privileged_roles = {"admin", "facility_admin", "hr_admin", "finance_admin"}
    is_privileged = bool(privileged_roles.intersection(current_user.roles))

    if not is_privileged:
        emp_row = (
            (
                await db.execute(
                    select(Employee).where(
                        Employee.id == employee_id,
                        Employee.facility_id == current_user.facility_id,
                        Employee.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .first()
        )
        owns_record = (
            emp_row is not None
            and bool(current_user.email)
            and (emp_row.email or "").lower() == (current_user.email or "").lower()
        )
        if not owns_record:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to access this payslip",
            )

    try:
        pdf_bytes = await generate_payslip(
            db=db,
            facility_id=current_user.facility_id,
            payroll_run_id=run_id,
            employee_id=employee_id,
        )
    except PayslipNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    media = "application/pdf" if pdf_bytes[:4] == b"%PDF" else "text/plain"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type=media,
        headers={"Content-Disposition": (f'attachment; filename="payslip-{run_id}-{employee_id}.pdf"')},
    )


@router.get("/employees/{employee_id}/payslips")
async def list_employee_payslips(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Self-service: list approved payslips for one employee.

    Access control: HR/finance admins can list any employee's payslips;
    otherwise the requester may only list their own.
    """
    privileged_roles = {"admin", "facility_admin", "hr_admin", "finance_admin"}
    is_privileged = bool(privileged_roles.intersection(current_user.roles))
    if not is_privileged:
        emp_row = (
            (
                await db.execute(
                    select(Employee).where(
                        Employee.id == employee_id,
                        Employee.facility_id == current_user.facility_id,
                        Employee.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .first()
        )
        owns_record = (
            emp_row is not None
            and bool(current_user.email)
            and (emp_row.email or "").lower() == (current_user.email or "").lower()
        )
        if not owns_record:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed to list these payslips",
            )

    rows = (
        await db.execute(
            select(
                PayrollRun.id,
                PayrollRun.month,
                PayrollRun.year,
                PayrollRun.status,
                PayrollLineItem.gross_salary,
                PayrollLineItem.net_salary,
            )
            .join(PayrollRun, PayrollRun.id == PayrollLineItem.payroll_run_id)
            .where(
                PayrollLineItem.employee_id == employee_id,
                PayrollLineItem.facility_id == current_user.facility_id,
                PayrollLineItem.is_deleted.is_(False),
                PayrollRun.is_deleted.is_(False),
                PayrollRun.status.in_(["approved", "posted", "locked"]),
            )
            .order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
        )
    ).all()
    return [
        {
            "payroll_run_id": rid,
            "month": int(m),
            "year": int(y),
            "status": st,
            "gross_salary": str(Decimal(g or 0)),
            "net_salary": str(Decimal(n or 0)),
        }
        for (rid, m, y, st, g, n) in rows
    ]


# ── Reports ────────────────────────────────────────────────────────────────


@router.get("/reports/p9/{employee_id}", response_model=P9Response)
async def get_p9(
    employee_id: uuid.UUID,
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> P9Response:
    """Annual P9 PAYE return for one employee."""
    try:
        data = await generate_p9(
            db=db,
            facility_id=current_user.facility_id,
            employee_id=employee_id,
            year=year,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return P9Response(
        employee_id=data["employee_id"],
        employee_name=data["employee_name"],
        kra_pin=data["kra_pin"],
        year=data["year"],
        rows=[P9Row(**r) for r in data["rows"]],
        total_gross=data["total_gross"],
        total_paye=data["total_paye"],
        total_nssf=data["total_nssf"],
        total_shif=data["total_shif"],
        total_housing_levy=data["total_housing_levy"],
    )


_FORMAT_DESC = (
    "Optional export format: 'csv' | 'xlsx' | 'pdf'. When omitted returns "
    "JSON. CSV / Excel / PDF outputs are KRA / NSSF / SHIF portal-ready."
)


@router.get("/reports/paye-schedule", response_model=None)
async def paye_schedule(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    format: str | None = Query(None, description=_FORMAT_DESC),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict] | StreamingResponse:
    """KRA P10 PAYE schedule per employee.

    When ``format`` is supplied (csv / xlsx / pdf), streams a downloadable file
    with KRA-compliant column headers; otherwise returns JSON rows.
    """
    rows = await get_paye_schedule(db, current_user.facility_id, month, year)
    if format:
        try:
            data, media, filename = render_schedule("paye", format, rows, month, year)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return StreamingResponse(
            iter([data]),
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return [
        {**r, "amount": str(r["amount"]), "gross": str(r["gross"])} for r in rows
    ]


@router.get("/reports/nssf-schedule", response_model=None)
async def nssf_schedule(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    format: str | None = Query(None, description=_FORMAT_DESC),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict] | StreamingResponse:
    """NSSF schedule per employee (Tier I / Tier II split for ``format`` exports)."""
    rows = await get_nssf_schedule(db, current_user.facility_id, month, year)
    if format:
        try:
            data, media, filename = render_schedule("nssf", format, rows, month, year)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return StreamingResponse(
            iter([data]),
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return [
        {**r, "amount": str(r["amount"]), "gross": str(r["gross"])} for r in rows
    ]


@router.get("/reports/shif-schedule", response_model=None)
async def shif_schedule(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    format: str | None = Query(None, description=_FORMAT_DESC),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict] | StreamingResponse:
    """SHIF schedule per employee."""
    rows = await get_shif_schedule(db, current_user.facility_id, month, year)
    if format:
        try:
            data, media, filename = render_schedule("shif", format, rows, month, year)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return StreamingResponse(
            iter([data]),
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return [
        {**r, "amount": str(r["amount"]), "gross": str(r["gross"])} for r in rows
    ]


@router.get("/reports/headcount")
async def headcount_report(
    as_of: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Headcount report by department + employment type."""
    return await get_headcount_report(
        db=db,
        facility_id=current_user.facility_id,
        as_of=as_of or date.today(),
    )


@router.get("/reports/leave-utilisation")
async def leave_utilisation(
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Leave utilisation for the year."""
    return await get_leave_utilisation(db=db, facility_id=current_user.facility_id, year=year)


@router.get("/reports/cost-trend")
async def cost_trend(
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Per-month payroll cost trend."""
    rows = await get_payroll_cost_trend(db=db, facility_id=current_user.facility_id, year=year)
    return [
        {
            "month": r["month"],
            "total_gross": str(r["total_gross"]),
            "total_net": str(r["total_net"]),
            "total_paye": str(r["total_paye"]),
        }
        for r in rows
    ]


@router.get("/reports/turnover")
async def turnover(
    period_start: date = Query(...),
    period_end: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Hires + terminations + ending headcount."""
    return await get_employee_turnover(
        db=db,
        facility_id=current_user.facility_id,
        period_start=period_start,
        period_end=period_end,
    )


# ── Statutory rate config ──────────────────────────────────────────────────


@router.get("/statutory-rates", response_model=list[StatutoryRateResponse])
async def list_statutory_rates(
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[StatutoryRateResponse]:
    """List rates available to this facility (its own + globals)."""
    stmt = select(StatutoryRate).where(
        StatutoryRate.is_deleted.is_(False),
        or_(
            StatutoryRate.facility_id == current_user.facility_id,
            StatutoryRate.facility_id.is_(None),
        ),
    )
    if category is not None:
        stmt = stmt.where(StatutoryRate.category == category)
    rows = (await db.execute(stmt.order_by(StatutoryRate.effective_from.desc()))).scalars().all()
    return [StatutoryRateResponse.model_validate(r) for r in rows]


@router.post(
    "/statutory-rates",
    response_model=StatutoryRateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_statutory_rate(
    data: StatutoryRateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("admin", "facility_admin", "finance_admin")),
) -> StatutoryRateResponse:
    """Create a facility-scoped statutory rate override."""
    rate = StatutoryRate(
        facility_id=current_user.facility_id,
        name=data.name,
        category=data.category,
        rate=data.rate,
        fixed_amount=data.fixed_amount,
        fixed_cap=data.fixed_cap,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
        notes=data.notes,
        approved_by=current_user.user_id,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    db.add(rate)
    await db.flush()
    await db.refresh(rate)
    return StatutoryRateResponse.model_validate(rate)


@router.get("/paye-bands", response_model=list[PAYEBandResponse])
async def list_paye_bands(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PAYEBandResponse]:
    """List currently-effective PAYE bands."""
    today = date.today()
    rows = (
        (
            await db.execute(
                select(PAYEBand)
                .where(
                    PAYEBand.is_deleted.is_(False),
                    PAYEBand.effective_from <= today,
                    or_(PAYEBand.effective_to.is_(None), PAYEBand.effective_to >= today),
                    or_(
                        PAYEBand.facility_id == current_user.facility_id,
                        PAYEBand.facility_id.is_(None),
                    ),
                )
                .order_by(PAYEBand.lower_limit.asc())
            )
        )
        .scalars()
        .all()
    )
    return [PAYEBandResponse.model_validate(b) for b in rows]


@router.get("/nssf-tiers", response_model=list[NSSFTierResponse])
async def list_nssf_tiers(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[NSSFTierResponse]:
    """List currently-effective NSSF tiers."""
    today = date.today()
    rows = (
        (
            await db.execute(
                select(NSSFTier)
                .where(
                    NSSFTier.is_deleted.is_(False),
                    NSSFTier.effective_from <= today,
                    or_(NSSFTier.effective_to.is_(None), NSSFTier.effective_to >= today),
                    or_(
                        NSSFTier.facility_id == current_user.facility_id,
                        NSSFTier.facility_id.is_(None),
                    ),
                )
                .order_by(NSSFTier.lower_limit.asc())
            )
        )
        .scalars()
        .all()
    )
    return [NSSFTierResponse.model_validate(t) for t in rows]


# ── Leave ──────────────────────────────────────────────────────────────────


@router.get("/leave-types", response_model=list[LeaveTypeResponse])
async def list_leave_types(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[LeaveTypeResponse]:
    """List leave types (facility-specific + globals)."""
    rows = (
        (
            await db.execute(
                select(LeaveType)
                .where(
                    LeaveType.is_deleted.is_(False),
                    or_(
                        LeaveType.facility_id == current_user.facility_id,
                        LeaveType.facility_id.is_(None),
                    ),
                )
                .order_by(LeaveType.name.asc())
            )
        )
        .scalars()
        .all()
    )
    return [LeaveTypeResponse.model_validate(lt) for lt in rows]


@router.post(
    "/leave-requests",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave_request(
    data: LeaveRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LeaveRequestResponse:
    """Submit a payroll-aware leave request."""
    try:
        req = await submit_leave_request(
            db=db,
            facility_id=current_user.facility_id,
            employee_id=data.employee_id,
            leave_type_id=data.leave_type_id,
            start_date=data.start_date,
            end_date=data.end_date,
            days_requested=data.days_requested,
            reason=data.reason,
            user_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return LeaveRequestResponse.model_validate(req)


@router.post(
    "/leave-requests/{leave_id}/approve",
    response_model=LeaveRequestResponse,
)
async def process_leave_request(
    leave_id: uuid.UUID,
    data: LeaveApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("admin", "facility_admin", "hr_admin", "hr_officer")),
) -> LeaveRequestResponse:
    """Approve or reject a leave request."""
    if data.action == "approve":
        req = await approve_leave_request(
            db=db,
            facility_id=current_user.facility_id,
            leave_id=leave_id,
            approver_id=current_user.user_id,
        )
    else:
        req = await reject_leave_request(
            db=db,
            facility_id=current_user.facility_id,
            leave_id=leave_id,
            approver_id=current_user.user_id,
            reason=data.rejection_reason,
        )
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    return LeaveRequestResponse.model_validate(req)


# ── Helpers ────────────────────────────────────────────────────────────────


async def _build_run_response(
    db: AsyncSession,
    facility_id: uuid.UUID,
    run: PayrollRun,
) -> PayrollRunResponse:
    """Hydrate a PayrollRun with its line items as a response model."""
    lines = (
        (
            await db.execute(
                select(PayrollLineItem).where(
                    PayrollLineItem.payroll_run_id == run.id,
                    PayrollLineItem.facility_id == facility_id,
                    PayrollLineItem.is_deleted.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    resp = PayrollRunResponse.model_validate(run)
    resp.line_items = [PayrollLineItemResponse.model_validate(li) for li in lines]
    return resp


# Monthly summary endpoint (placed at end so route order is intuitive)
@router.get("/reports/summary")
async def monthly_summary(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Per-department monthly summary."""
    data = await get_monthly_payroll_summary(db=db, facility_id=current_user.facility_id, month=month, year=year)
    # Convert Decimals to strings for JSON safety
    for d in data["departments"]:
        d["total_gross"] = str(d["total_gross"])
        d["total_net"] = str(d["total_net"])
        d["total_paye"] = str(d["total_paye"])
    for k in (
        "grand_total_gross",
        "grand_total_net",
        "grand_total_paye",
        "grand_total_nssf",
        "grand_total_shif",
        "grand_total_hl",
    ):
        data[k] = str(data[k])
    return data
