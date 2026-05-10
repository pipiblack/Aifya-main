"""On-demand payroll reports.

All queries scoped by facility_id (multi-tenant). Results are computed
from the materialised line items rather than re-running the engine.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, select

from app.models.payroll import (
    Employee,
    PayrollLineItem,
    PayrollRun,
)
from app.models.payroll_extra import PayrollLeaveRequest

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

_ZERO = Decimal("0")


# ── Monthly summary ────────────────────────────────────────────────────────


async def get_monthly_payroll_summary(
    db: AsyncSession,
    facility_id: uuid.UUID,
    month: int,
    year: int,
) -> dict[str, Any]:
    """Return totals per department for the given period.

    @returns dict with `month`, `year`, `departments` (list), grand totals.
    """
    run = (
        (
            await db.execute(
                select(PayrollRun)
                .where(
                    PayrollRun.facility_id == facility_id,
                    PayrollRun.is_deleted.is_(False),
                    PayrollRun.month == month,
                    PayrollRun.year == year,
                )
                .order_by(PayrollRun.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if run is None:
        return {
            "month": month,
            "year": year,
            "departments": [],
            "grand_total_gross": _ZERO,
            "grand_total_net": _ZERO,
            "grand_total_paye": _ZERO,
            "grand_total_nssf": _ZERO,
            "grand_total_shif": _ZERO,
            "grand_total_hl": _ZERO,
            "headcount": 0,
        }

    rows = (
        await db.execute(
            select(
                Employee.department_id,
                func.count(PayrollLineItem.id).label("headcount"),
                func.coalesce(func.sum(PayrollLineItem.gross_salary), 0).label("gross"),
                func.coalesce(func.sum(PayrollLineItem.net_salary), 0).label("net"),
                func.coalesce(func.sum(PayrollLineItem.paye), 0).label("paye"),
            )
            .join(Employee, Employee.id == PayrollLineItem.employee_id)
            .where(
                PayrollLineItem.payroll_run_id == run.id,
                PayrollLineItem.facility_id == facility_id,
                PayrollLineItem.is_deleted.is_(False),
            )
            .group_by(Employee.department_id)
        )
    ).all()

    departments: list[dict[str, Any]] = []
    for dept_id, headcount, gross, net, paye in rows:
        departments.append(
            {
                "department_id": dept_id,
                "department_name": None,  # router can join Department by id
                "headcount": int(headcount or 0),
                "total_gross": Decimal(gross or 0),
                "total_net": Decimal(net or 0),
                "total_paye": Decimal(paye or 0),
            }
        )

    return {
        "month": month,
        "year": year,
        "departments": departments,
        "grand_total_gross": Decimal(run.total_gross or 0),
        "grand_total_net": Decimal(run.total_net or 0),
        "grand_total_paye": Decimal(run.total_paye or 0),
        "grand_total_nssf": Decimal(run.total_nssf or 0),
        "grand_total_shif": Decimal(run.total_shif or 0),
        "grand_total_hl": Decimal(run.total_hl or 0),
        "headcount": sum(int(d["headcount"]) for d in departments),
    }


# ── Statutory schedules (P10 / NSSF / SHIF) ────────────────────────────────


async def _statutory_schedule(
    db: AsyncSession,
    facility_id: uuid.UUID,
    month: int,
    year: int,
    field: str,
    id_field: str,
) -> list[dict[str, Any]]:
    """Generic per-employee statutory schedule helper."""
    run = (
        (
            await db.execute(
                select(PayrollRun)
                .where(
                    PayrollRun.facility_id == facility_id,
                    PayrollRun.is_deleted.is_(False),
                    PayrollRun.month == month,
                    PayrollRun.year == year,
                )
                .order_by(PayrollRun.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if run is None:
        return []

    col_amount = getattr(PayrollLineItem, field)
    col_id = getattr(Employee, id_field)
    rows = (
        await db.execute(
            select(
                Employee.id,
                Employee.full_name,
                col_id,
                Employee.kra_pin,
                PayrollLineItem.gross_salary,
                col_amount,
            )
            .join(Employee, Employee.id == PayrollLineItem.employee_id)
            .where(
                PayrollLineItem.payroll_run_id == run.id,
                PayrollLineItem.facility_id == facility_id,
                PayrollLineItem.is_deleted.is_(False),
            )
            .order_by(Employee.full_name.asc())
        )
    ).all()
    return [
        {
            "employee_id": eid,
            "full_name": fn,
            "id_value": id_val,
            "kra_pin": kra,
            "gross": Decimal(gross or 0),
            "amount": Decimal(amount or 0),
        }
        for (eid, fn, id_val, kra, gross, amount) in rows
    ]


async def get_paye_schedule(db: AsyncSession, facility_id: uuid.UUID, month: int, year: int) -> list[dict[str, Any]]:
    """KRA P10 PAYE schedule per employee."""
    return await _statutory_schedule(db, facility_id, month, year, field="paye", id_field="kra_pin")


async def get_nssf_schedule(db: AsyncSession, facility_id: uuid.UUID, month: int, year: int) -> list[dict[str, Any]]:
    """NSSF schedule per employee."""
    return await _statutory_schedule(db, facility_id, month, year, field="nssf_employee", id_field="nssf_number")


async def get_shif_schedule(db: AsyncSession, facility_id: uuid.UUID, month: int, year: int) -> list[dict[str, Any]]:
    """SHIF schedule per employee."""
    return await _statutory_schedule(db, facility_id, month, year, field="shif", id_field="shif_number")


# ── P9 annual return ───────────────────────────────────────────────────────


async def generate_p9(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_id: uuid.UUID,
    year: int,
) -> dict[str, Any]:
    """Generate annual P9 (PAYE return) for one employee.

    The sum of monthly PAYE figures MUST equal `total_paye` in the response.
    """
    emp = (
        (
            await db.execute(
                select(Employee).where(
                    Employee.id == employee_id,
                    Employee.facility_id == facility_id,
                    Employee.is_deleted.is_(False),
                )
            )
        )
        .scalars()
        .first()
    )
    if emp is None:
        raise ValueError("Employee not found")

    rows = (
        await db.execute(
            select(
                PayrollRun.month,
                PayrollLineItem.gross_salary,
                PayrollLineItem.nssf_employee,
                PayrollLineItem.shif,
                PayrollLineItem.housing_levy,
                PayrollLineItem.taxable_pay,
                PayrollLineItem.paye,
            )
            .join(PayrollRun, PayrollRun.id == PayrollLineItem.payroll_run_id)
            .where(
                PayrollLineItem.facility_id == facility_id,
                PayrollLineItem.employee_id == employee_id,
                PayrollLineItem.is_deleted.is_(False),
                PayrollRun.year == year,
                PayrollRun.is_deleted.is_(False),
                PayrollRun.status.in_(["approved", "posted", "locked"]),
            )
            .order_by(PayrollRun.month.asc())
        )
    ).all()

    p9_rows: list[dict[str, Any]] = []
    total_gross = total_paye = total_nssf = total_shif = total_hl = _ZERO
    for month, gross, nssf, shif, hl, taxable, paye in rows:
        gross_d = Decimal(gross or 0)
        nssf_d = Decimal(nssf or 0)
        shif_d = Decimal(shif or 0)
        hl_d = Decimal(hl or 0)
        taxable_d = Decimal(taxable or 0)
        paye_d = Decimal(paye or 0)
        total_gross += gross_d
        total_nssf += nssf_d
        total_shif += shif_d
        total_hl += hl_d
        total_paye += paye_d
        p9_rows.append(
            {
                "month": int(month),
                "gross_salary": gross_d,
                "nssf": nssf_d,
                "shif": shif_d,
                "housing_levy": hl_d,
                "taxable_pay": taxable_d,
                "paye": paye_d,
            }
        )

    return {
        "employee_id": employee_id,
        "employee_name": emp.full_name,
        "kra_pin": emp.kra_pin,
        "year": year,
        "rows": p9_rows,
        "total_gross": total_gross,
        "total_paye": total_paye,
        "total_nssf": total_nssf,
        "total_shif": total_shif,
        "total_housing_levy": total_hl,
    }


# ── Headcount / leave / cost trend / turnover ──────────────────────────────


async def get_headcount_report(
    db: AsyncSession,
    facility_id: uuid.UUID,
    as_of: date,
) -> dict[str, Any]:
    """Headcount as of a date, broken down by department + employment type."""
    rows = (
        await db.execute(
            select(
                Employee.department_id,
                Employee.employment_type,
                func.count(Employee.id),
            )
            .where(
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
                Employee.is_active.is_(True),
                Employee.hire_date <= as_of,
            )
            .group_by(Employee.department_id, Employee.employment_type)
        )
    ).all()
    breakdown = [
        {
            "department_id": dept,
            "employment_type": emp_type,
            "count": int(count),
        }
        for (dept, emp_type, count) in rows
    ]
    return {
        "as_of": as_of.isoformat(),
        "total": sum(int(b["count"]) for b in breakdown),
        "breakdown": breakdown,
    }


async def get_leave_utilisation(
    db: AsyncSession,
    facility_id: uuid.UUID,
    year: int,
) -> dict[str, Any]:
    """Approved-leave-days per leave_type for the year."""
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    rows = (
        await db.execute(
            select(
                PayrollLeaveRequest.leave_type_id,
                func.coalesce(func.sum(PayrollLeaveRequest.days_requested), 0),
            )
            .where(
                PayrollLeaveRequest.facility_id == facility_id,
                PayrollLeaveRequest.is_deleted.is_(False),
                PayrollLeaveRequest.status == "approved",
                PayrollLeaveRequest.start_date >= year_start,
                PayrollLeaveRequest.start_date <= year_end,
            )
            .group_by(PayrollLeaveRequest.leave_type_id)
        )
    ).all()
    return {
        "year": year,
        "items": [{"leave_type_id": lt, "days_taken": int(days or 0)} for (lt, days) in rows],
    }


async def get_payroll_cost_trend(
    db: AsyncSession,
    facility_id: uuid.UUID,
    year: int,
) -> list[dict[str, Any]]:
    """Per-month total gross/net for the year (approved+ runs only)."""
    rows = (
        await db.execute(
            select(
                PayrollRun.month,
                func.coalesce(func.sum(PayrollRun.total_gross), 0),
                func.coalesce(func.sum(PayrollRun.total_net), 0),
                func.coalesce(func.sum(PayrollRun.total_paye), 0),
            )
            .where(
                PayrollRun.facility_id == facility_id,
                PayrollRun.is_deleted.is_(False),
                PayrollRun.year == year,
                PayrollRun.status.in_(["approved", "posted", "locked"]),
            )
            .group_by(PayrollRun.month)
            .order_by(PayrollRun.month.asc())
        )
    ).all()
    return [
        {
            "month": int(m),
            "total_gross": Decimal(g or 0),
            "total_net": Decimal(n or 0),
            "total_paye": Decimal(p or 0),
        }
        for (m, g, n, p) in rows
    ]


async def get_employee_turnover(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    """Hires + terminations + ending headcount."""
    hires = (
        await db.execute(
            select(func.count(Employee.id)).where(
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
                Employee.hire_date >= period_start,
                Employee.hire_date <= period_end,
            )
        )
    ).scalar() or 0
    terminations = (
        await db.execute(
            select(func.count(Employee.id)).where(
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
                Employee.termination_date.isnot(None),
                Employee.termination_date >= period_start,
                Employee.termination_date <= period_end,
            )
        )
    ).scalar() or 0
    ending = (
        await db.execute(
            select(func.count(Employee.id)).where(
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
                Employee.is_active.is_(True),
                Employee.hire_date <= period_end,
                and_(
                    (Employee.termination_date.is_(None) | (Employee.termination_date > period_end)),
                ),
            )
        )
    ).scalar() or 0
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "hires": int(hires),
        "terminations": int(terminations),
        "ending_headcount": int(ending),
    }
