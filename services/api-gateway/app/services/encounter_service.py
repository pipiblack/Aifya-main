import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.schemas.encounter import EncounterCreate, EncounterUpdate


class EncounterService:
    """Service layer for OPD encounter and queue management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_encounter(
        self,
        data: EncounterCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> Encounter:
        """
        Create a new encounter and add to OPD queue.

        @param data: Encounter creation data
        @param facility_id: Facility UUID from JWT
        @param created_by: Staff UUID
        @param idempotency_key: Optional idempotency key
        @returns Created encounter
        """
        # Generate queue number for today
        queue_number = await self._next_queue_number(facility_id)

        encounter = Encounter(
            facility_id=facility_id,
            patient_id=data.patient_id,
            encounter_type=data.encounter_type,
            department_id=data.department_id,
            chief_complaint=data.chief_complaint,
            triage_category=data.triage_category,
            priority=self._triage_priority(data.triage_category),
            queue_number=queue_number,
            status="waiting",
            created_by=created_by,
            updated_by=created_by,
        )

        self.db.add(encounter)
        await self.db.flush()
        await self.db.refresh(encounter)

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="encounter",
            stream_id=encounter.id,
            event_type="EncounterCreated",
            event_data={
                "patient_id": str(data.patient_id),
                "encounter_type": data.encounter_type,
                "chief_complaint": data.chief_complaint,
                "triage_category": data.triage_category,
                "queue_number": queue_number,
            },
            version=1,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )
        self.db.add(event)

        return encounter

    async def get_opd_queue(
        self,
        facility_id: uuid.UUID,
        status_filter: str | None = None,
    ) -> list[Encounter]:
        """
        Get the OPD queue ordered by triage priority then queue number.

        @param facility_id: Facility UUID
        @param status_filter: Optional status filter
        @returns List of encounters in queue order
        """
        stmt = (
            select(Encounter)
            .where(
                Encounter.facility_id == facility_id,
                Encounter.encounter_type == "opd",
                Encounter.is_deleted == False,  # noqa: E712
            )
            .order_by(
                Encounter.priority.desc(),
                Encounter.queue_number.asc(),
            )
        )

        if status_filter:
            stmt = stmt.where(Encounter.status == status_filter)
        else:
            stmt = stmt.where(
                Encounter.status.in_(["waiting", "in_consultation"])
            )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_encounter(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> Encounter | None:
        """
        Get a single encounter by ID.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns Encounter or None
        """
        result = await self.db.execute(
            select(Encounter).where(
                Encounter.id == encounter_id,
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def update_encounter(
        self,
        encounter_id: uuid.UUID,
        data: EncounterUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> Encounter | None:
        """
        Update encounter (status, triage, disposition, etc.).

        @param encounter_id: Encounter UUID
        @param data: Fields to update
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated encounter or None
        """
        encounter = await self.get_encounter(encounter_id, facility_id)
        if not encounter:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(encounter, field, value)

        if data.triage_category:
            encounter.priority = self._triage_priority(data.triage_category)

        encounter.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(encounter)

        return encounter

    async def call_next(
        self, facility_id: uuid.UUID, doctor_id: uuid.UUID
    ) -> Encounter | None:
        """
        Call the next patient in the OPD queue (highest priority waiting).

        @param facility_id: Facility UUID
        @param doctor_id: Doctor's staff UUID
        @returns Next encounter or None if queue empty
        """
        result = await self.db.execute(
            select(Encounter)
            .where(
                Encounter.facility_id == facility_id,
                Encounter.encounter_type == "opd",
                Encounter.status == "waiting",
                Encounter.is_deleted == False,  # noqa: E712
            )
            .order_by(
                Encounter.priority.desc(),
                Encounter.queue_number.asc(),
            )
            .limit(1)
        )
        encounter = result.scalar_one_or_none()
        if not encounter:
            return None

        encounter.status = "in_consultation"
        encounter.attending_doctor_id = doctor_id
        encounter.updated_by = doctor_id
        await self.db.flush()
        await self.db.refresh(encounter)

        return encounter

    async def _next_queue_number(self, facility_id: uuid.UUID) -> int:
        """Generate the next queue number for today."""
        result = await self.db.execute(
            select(func.coalesce(func.max(Encounter.queue_number), 0))
            .where(
                Encounter.facility_id == facility_id,
                Encounter.encounter_type == "opd",
                func.date(Encounter.encounter_date) == func.current_date(),
            )
        )
        return result.scalar_one() + 1

    @staticmethod
    def _triage_priority(category: str | None) -> int:
        """Map SATS triage category to numeric priority."""
        mapping = {
            "emergency": 5,   # Red
            "urgent": 4,      # Orange
            "standard": 3,    # Yellow
            "non_urgent": 2,  # Green
            "dead": 1,        # Blue
        }
        return mapping.get(category or "", 2)
