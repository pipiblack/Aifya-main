import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.patient import Patient
from app.models.referral import Referral
from app.schemas.referral import (
    ReferralCreate,
    ReferralListItem,
    ReferralSummary,
    ReferralUpdateStatus,
)


class ReferralService:
    """Service for patient referral management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_referral(
        self,
        data: ReferralCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> Referral:
        """
        Create a new referral.

        @param data: Referral data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created referral
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count_result = await self.db.execute(
            select(func.count(Referral.id)).where(
                Referral.facility_id == facility_id,
                Referral.referral_number.like(f"REF-{date_part}-%"),
                Referral.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count_result.scalar() or 0) + 1
        referral_number = f"REF-{date_part}-{seq:04d}"

        referral = Referral(
            facility_id=facility_id,
            referral_number=referral_number,
            patient_id=data.patient_id,
            encounter_id=data.encounter_id,
            referral_type=data.referral_type,
            direction=data.direction,
            referring_doctor_id=data.referring_doctor_id,
            referring_department_id=data.referring_department_id,
            referring_facility_name=data.referring_facility_name,
            receiving_doctor_id=data.receiving_doctor_id,
            receiving_department_id=data.receiving_department_id,
            receiving_facility_name=data.receiving_facility_name,
            receiving_facility_mfl=data.receiving_facility_mfl,
            reason=data.reason,
            clinical_notes=data.clinical_notes,
            diagnosis=data.diagnosis,
            urgency=data.urgency,
            referral_date=now,
            status="draft",
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(referral)
        await self.db.flush()
        await self.db.refresh(referral)

        event = EventBase(
            facility_id=facility_id,
            stream_type="referral",
            stream_id=data.patient_id,
            event_type="ReferralCreated",
            event_data={
                "referral_id": str(referral.id),
                "referral_number": referral_number,
                "direction": data.direction,
            },
            version=1,
            created_by=created_by,
        )
        self.db.add(event)
        return referral

    async def get_referrals(
        self,
        facility_id: uuid.UUID,
        direction: str | None = None,
        status: str | None = None,
    ) -> list[ReferralListItem]:
        """
        Get referrals with patient names.

        @param facility_id: Facility UUID
        @param direction: Optional direction filter
        @param status: Optional status filter
        @returns List of referrals
        """
        query = (
            select(
                Referral,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
            )
            .join(Patient, Referral.patient_id == Patient.id)
            .where(
                Referral.facility_id == facility_id,
                Referral.is_deleted == False,  # noqa: E712
            )
        )
        if direction:
            query = query.where(Referral.direction == direction)
        if status:
            query = query.where(Referral.status == status)
        query = query.order_by(Referral.referral_date.desc())

        result = await self.db.execute(query)
        rows = result.all()

        return [
            ReferralListItem(
                id=r.id,
                referral_number=r.referral_number,
                patient_id=r.patient_id,
                patient_name=f"{pf or ''} {pl or ''}".strip() or None,
                referral_type=r.referral_type,
                direction=r.direction,
                reason=r.reason,
                urgency=r.urgency,
                referring_facility_name=r.referring_facility_name,
                receiving_facility_name=r.receiving_facility_name,
                referral_date=r.referral_date,
                status=r.status,
            )
            for r, pf, pl in rows
        ]

    async def get_referral(self, referral_id: uuid.UUID, facility_id: uuid.UUID) -> Referral | None:
        """
        Get a single referral.

        @param referral_id: Referral UUID
        @param facility_id: Facility UUID
        @returns Referral or None
        """
        result = await self.db.execute(
            select(Referral).where(
                Referral.id == referral_id,
                Referral.facility_id == facility_id,
                Referral.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        referral_id: uuid.UUID,
        data: ReferralUpdateStatus,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> Referral | None:
        """
        Update referral status.

        @param referral_id: Referral UUID
        @param data: Status update data
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated referral or None
        """
        referral = await self.get_referral(referral_id, facility_id)
        if not referral:
            return None

        referral.status = data.status
        if data.response_notes:
            referral.response_notes = data.response_notes
        if data.feedback:
            referral.feedback = data.feedback
        if data.status in ("accepted", "declined", "completed"):
            referral.response_date = datetime.now(UTC)
        referral.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(referral)
        return referral

    async def get_summary(self, facility_id: uuid.UUID) -> ReferralSummary:
        """
        Get referral summary stats.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        base = [Referral.facility_id == facility_id, Referral.is_deleted == False]  # noqa: E712

        total = await self.db.execute(select(func.count(Referral.id)).where(*base))
        outgoing = await self.db.execute(select(func.count(Referral.id)).where(*base, Referral.direction == "outgoing"))
        incoming = await self.db.execute(select(func.count(Referral.id)).where(*base, Referral.direction == "incoming"))
        pending = await self.db.execute(
            select(func.count(Referral.id)).where(*base, Referral.status.in_(["draft", "sent", "received"]))
        )
        accepted = await self.db.execute(select(func.count(Referral.id)).where(*base, Referral.status == "accepted"))
        completed = await self.db.execute(select(func.count(Referral.id)).where(*base, Referral.status == "completed"))

        return ReferralSummary(
            total_referrals=total.scalar() or 0,
            outgoing=outgoing.scalar() or 0,
            incoming=incoming.scalar() or 0,
            pending=pending.scalar() or 0,
            accepted=accepted.scalar() or 0,
            completed=completed.scalar() or 0,
        )
