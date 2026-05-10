import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.emergency import EmergencyVisit
from app.models.patient import Patient
from app.models.staff import Staff
from app.schemas.emergency import (
    AssignDoctorRequest,
    DispositionRequest,
    EmergencyListItem,
    EmergencySummary,
    EmergencyVisitCreate,
    TriageRequest,
)

TRIAGE_COLORS = {
    "emergency": "red",
    "urgent": "orange",
    "standard": "yellow",
    "non_urgent": "green",
    "dead": "blue",
}


class EmergencyService:
    """
    Service for emergency department: registration, SATS triage,
    doctor assignment, treatment tracking, and disposition.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register_visit(
        self,
        data: EmergencyVisitCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> EmergencyVisit:
        """
        Register a new emergency visit.

        @param data: Visit data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created emergency visit
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count_result = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(
                EmergencyVisit.facility_id == facility_id,
                EmergencyVisit.visit_number.like(f"ER-{date_part}-%"),
                EmergencyVisit.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count_result.scalar() or 0) + 1
        visit_number = f"ER-{date_part}-{seq:04d}"

        visit = EmergencyVisit(
            facility_id=facility_id,
            patient_id=data.patient_id,
            visit_number=visit_number,
            arrival_time=now,
            arrival_mode=data.arrival_mode,
            brought_by=data.brought_by,
            chief_complaint=data.chief_complaint,
            is_trauma=data.is_trauma,
            is_resuscitation=False,  # Default; updated during triage when category is "emergency"
            allergies_noted=data.allergies_noted,
            notes=data.notes,
            status="arrived",
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(visit)
        await self.db.flush()
        await self.db.refresh(visit)

        event = EventBase(
            facility_id=facility_id,
            stream_type="emergency",
            stream_id=data.patient_id,
            event_type="EmergencyVisitRegistered",
            event_data={"visit_id": str(visit.id), "visit_number": visit_number, "complaint": data.chief_complaint},
            version=1,
            created_by=created_by,
        )
        self.db.add(event)
        return visit

    async def triage(
        self,
        visit_id: uuid.UUID,
        data: TriageRequest,
        facility_id: uuid.UUID,
        triaged_by: uuid.UUID,
    ) -> EmergencyVisit | None:
        """
        Perform SATS triage on an emergency visit.

        @param visit_id: Visit UUID
        @param data: Triage data
        @param facility_id: Facility UUID
        @param triaged_by: Staff UUID
        @returns Updated visit or None
        """
        visit = await self._get_visit(visit_id, facility_id)
        if not visit:
            return None

        now = datetime.now(UTC)
        visit.triage_category = data.triage_category
        visit.triage_color = TRIAGE_COLORS.get(data.triage_category, "yellow")
        visit.triage_score = data.triage_score
        visit.triage_vitals = data.triage_vitals
        visit.triage_time = now
        visit.triaged_by = triaged_by
        visit.status = "triaged"
        if data.treatment_area:
            visit.treatment_area = data.treatment_area
        if data.triage_category == "emergency":
            visit.is_resuscitation = True
            visit.treatment_area = visit.treatment_area or "resus"
        if data.notes:
            visit.notes = (visit.notes or "") + f"\n[Triage] {data.notes}"
        visit.updated_by = triaged_by
        await self.db.flush()
        await self.db.refresh(visit)
        return visit

    async def assign_doctor(
        self,
        visit_id: uuid.UUID,
        data: AssignDoctorRequest,
        facility_id: uuid.UUID,
        assigned_by: uuid.UUID,
    ) -> EmergencyVisit | None:
        """
        Assign a doctor to an emergency visit.

        @param visit_id: Visit UUID
        @param data: Assignment data
        @param facility_id: Facility UUID
        @param assigned_by: Staff UUID
        @returns Updated visit or None
        """
        visit = await self._get_visit(visit_id, facility_id)
        if not visit:
            return None

        visit.assigned_doctor_id = data.doctor_id
        visit.status = "in_treatment"
        visit.treatment_started_at = datetime.now(UTC)
        visit.updated_by = assigned_by
        await self.db.flush()
        await self.db.refresh(visit)
        return visit

    async def record_disposition(
        self,
        visit_id: uuid.UUID,
        data: DispositionRequest,
        facility_id: uuid.UUID,
        disposed_by: uuid.UUID,
    ) -> EmergencyVisit | None:
        """
        Record disposition for an emergency visit.

        @param visit_id: Visit UUID
        @param data: Disposition data
        @param facility_id: Facility UUID
        @param disposed_by: Staff UUID
        @returns Updated visit or None
        """
        visit = await self._get_visit(visit_id, facility_id)
        if not visit:
            return None

        now = datetime.now(UTC)
        visit.disposition = data.disposition
        visit.disposition_time = now
        visit.disposition_notes = data.disposition_notes

        status_map = {
            "discharge": "discharged",
            "admit": "admitted",
            "transfer": "transferred",
            "deceased": "deceased",
            "left_ama": "left_against_advice",
        }
        visit.status = status_map.get(data.disposition, "discharged")
        if data.admitted_to_ward_id:
            visit.admitted_to_ward_id = data.admitted_to_ward_id
        visit.updated_by = disposed_by
        await self.db.flush()
        await self.db.refresh(visit)

        event = EventBase(
            facility_id=facility_id,
            stream_type="emergency",
            stream_id=visit.patient_id,
            event_type="EmergencyDisposition",
            event_data={"visit_id": str(visit.id), "disposition": data.disposition},
            version=1,
            created_by=disposed_by,
        )
        self.db.add(event)
        return visit

    async def get_queue(
        self,
        facility_id: uuid.UUID,
        status: str | None = None,
    ) -> list[EmergencyListItem]:
        """
        Get emergency queue with patient and doctor names.

        @param facility_id: Facility UUID
        @param status: Optional status filter
        @returns List of emergency visits
        """
        DoctorStaff = Staff.__table__.alias("doctor_staff")

        query = (
            select(
                EmergencyVisit,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
                Patient.mrn,
                DoctorStaff.c.first_name.label("d_first"),
                DoctorStaff.c.last_name.label("d_last"),
            )
            .join(Patient, EmergencyVisit.patient_id == Patient.id)
            .outerjoin(DoctorStaff, EmergencyVisit.assigned_doctor_id == DoctorStaff.c.id)
            .where(
                EmergencyVisit.facility_id == facility_id,
                EmergencyVisit.is_deleted == False,  # noqa: E712
            )
        )

        if status:
            query = query.where(EmergencyVisit.status == status)
        else:
            query = query.where(EmergencyVisit.status.in_(["arrived", "triaged", "in_treatment", "observation"]))

        # Priority order: red first, then by arrival time
        triage_order = func.array_position(
            func.cast(["red", "orange", "yellow", "green", "blue"], type_=None),
            EmergencyVisit.triage_color,
        )
        query = query.order_by(triage_order.asc(), EmergencyVisit.arrival_time.asc())

        result = await self.db.execute(query)
        rows = result.all()

        items: list[EmergencyListItem] = []
        for visit, p_first, p_last, mrn, d_first, d_last in rows:
            items.append(
                EmergencyListItem(
                    id=visit.id,
                    visit_number=visit.visit_number,
                    patient_id=visit.patient_id,
                    patient_name=f"{p_first or ''} {p_last or ''}".strip() or None,
                    patient_mrn=mrn,
                    arrival_time=visit.arrival_time,
                    arrival_mode=visit.arrival_mode,
                    chief_complaint=visit.chief_complaint,
                    triage_category=visit.triage_category,
                    triage_color=visit.triage_color,
                    triage_score=visit.triage_score,
                    treatment_area=visit.treatment_area,
                    assigned_doctor_name=f"{d_first or ''} {d_last or ''}".strip() or None,
                    status=visit.status,
                    is_trauma=visit.is_trauma,
                    is_resuscitation=visit.is_resuscitation,
                )
            )
        return items

    async def get_visit(self, visit_id: uuid.UUID, facility_id: uuid.UUID) -> EmergencyVisit | None:
        """
        Get a single emergency visit.

        @param visit_id: Visit UUID
        @param facility_id: Facility UUID
        @returns Emergency visit or None
        """
        return await self._get_visit(visit_id, facility_id)

    async def get_summary(self, facility_id: uuid.UUID) -> EmergencySummary:
        """
        Get emergency department summary.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        today = date.today()
        base = [
            EmergencyVisit.facility_id == facility_id,
            EmergencyVisit.is_deleted == False,  # noqa: E712
            func.date(EmergencyVisit.arrival_time) == today,
        ]

        total = await self.db.execute(select(func.count(EmergencyVisit.id)).where(*base))
        awaiting = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.status == "arrived")
        )
        treating = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.status == "in_treatment")
        )
        observing = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.status == "observation")
        )
        red = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.triage_color == "red")
        )
        orange = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.triage_color == "orange")
        )
        discharged = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.status == "discharged")
        )
        admitted = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(*base, EmergencyVisit.status == "admitted")
        )
        trauma = await self.db.execute(
            select(func.count(EmergencyVisit.id)).where(
                *base,
                EmergencyVisit.is_trauma == True,  # noqa: E712
            )
        )

        return EmergencySummary(
            total_today=total.scalar() or 0,
            awaiting_triage=awaiting.scalar() or 0,
            in_treatment=treating.scalar() or 0,
            in_observation=observing.scalar() or 0,
            critical_red=red.scalar() or 0,
            urgent_orange=orange.scalar() or 0,
            discharged_today=discharged.scalar() or 0,
            admitted_today=admitted.scalar() or 0,
            trauma_cases=trauma.scalar() or 0,
        )

    async def _get_visit(self, visit_id: uuid.UUID, facility_id: uuid.UUID) -> EmergencyVisit | None:
        """Get a single visit by ID."""
        result = await self.db.execute(
            select(EmergencyVisit).where(
                EmergencyVisit.id == visit_id,
                EmergencyVisit.facility_id == facility_id,
                EmergencyVisit.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()
