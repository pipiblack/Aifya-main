import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.insurance import (
    InsuranceClaim,
    InsuranceScheme,
    PatientInsurance,
    PreAuthorization,
)
from app.models.patient import Patient
from app.schemas.insurance import (
    ClaimCreate,
    ClaimListItem,
    ClaimStatusUpdate,
    InsuranceSchemeCreate,
    InsuranceSummary,
    PatientInsuranceCreate,
    PatientInsuranceResponse,
    PatientInsuranceUpdate,
)


class InsuranceService:
    """Service for insurance schemes, claims, and pre-authorization."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_scheme(
        self, data: InsuranceSchemeCreate, facility_id: uuid.UUID, created_by: uuid.UUID
    ) -> InsuranceScheme:
        """
        Create an insurance scheme.

        @param data: Scheme data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created scheme
        """
        count = await self.db.execute(
            select(func.count(InsuranceScheme.id)).where(
                InsuranceScheme.facility_id == facility_id,
                InsuranceScheme.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count.scalar() or 0) + 1
        code = f"SCH-{seq:04d}"

        scheme = InsuranceScheme(
            facility_id=facility_id,
            name=data.name,
            scheme_code=code,
            scheme_type=data.scheme_type,
            contact_person=data.contact_person,
            phone=data.phone,
            email=data.email,
            address=data.address,
            contract_start=data.contract_start,
            contract_end=data.contract_end,
            coverage_details=data.coverage_details,
            rebate_percentage=data.rebate_percentage,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(scheme)
        await self.db.flush()
        await self.db.refresh(scheme)
        return scheme

    async def get_schemes(self, facility_id: uuid.UUID) -> list[InsuranceScheme]:
        """
        Get all active schemes.

        @param facility_id: Facility UUID
        @returns List of schemes
        """
        result = await self.db.execute(
            select(InsuranceScheme)
            .where(
                InsuranceScheme.facility_id == facility_id,
                InsuranceScheme.is_deleted == False,  # noqa: E712
            )
            .order_by(InsuranceScheme.name.asc())
        )
        return list(result.scalars().all())

    async def create_claim(self, data: ClaimCreate, facility_id: uuid.UUID, created_by: uuid.UUID) -> InsuranceClaim:
        """
        Create an insurance claim.

        @param data: Claim data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created claim
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count = await self.db.execute(
            select(func.count(InsuranceClaim.id)).where(
                InsuranceClaim.facility_id == facility_id,
                InsuranceClaim.claim_number.like(f"CLM-{date_part}-%"),
            )
        )
        seq = (count.scalar() or 0) + 1
        claim_number = f"CLM-{date_part}-{seq:04d}"

        claim = InsuranceClaim(
            facility_id=facility_id,
            claim_number=claim_number,
            patient_id=data.patient_id,
            scheme_id=data.scheme_id,
            invoice_id=data.invoice_id,
            encounter_id=data.encounter_id,
            member_number=data.member_number,
            claim_amount=data.claim_amount,
            status="draft",
            claim_date=now,
            claim_items=data.claim_items,
            diagnosis_codes=data.diagnosis_codes,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(claim)
        await self.db.flush()
        await self.db.refresh(claim)
        return claim

    async def get_claims(self, facility_id: uuid.UUID, status: str | None = None) -> list[ClaimListItem]:
        """
        Get claims with patient and scheme names.

        @param facility_id: Facility UUID
        @param status: Optional status filter
        @returns List of claims
        """
        query = (
            select(
                InsuranceClaim,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
                InsuranceScheme.name.label("scheme_name"),
            )
            .join(Patient, InsuranceClaim.patient_id == Patient.id)
            .join(InsuranceScheme, InsuranceClaim.scheme_id == InsuranceScheme.id)
            .where(
                InsuranceClaim.facility_id == facility_id,
                InsuranceClaim.is_deleted == False,  # noqa: E712
            )
        )
        if status:
            query = query.where(InsuranceClaim.status == status)
        query = query.order_by(InsuranceClaim.claim_date.desc())

        result = await self.db.execute(query)
        return [
            ClaimListItem(
                id=c.id,
                claim_number=c.claim_number,
                patient_id=c.patient_id,
                patient_name=f"{pf or ''} {pl or ''}".strip() or None,
                scheme_name=sn,
                member_number=c.member_number,
                claim_amount=c.claim_amount,
                approved_amount=c.approved_amount,
                status=c.status,
                claim_date=c.claim_date,
                sha_reference=c.sha_reference,
            )
            for c, pf, pl, sn in result.all()
        ]

    async def get_claim(self, claim_id: uuid.UUID, facility_id: uuid.UUID) -> InsuranceClaim | None:
        """
        Get a single claim.

        @param claim_id: Claim UUID
        @param facility_id: Facility UUID
        @returns Claim or None
        """
        result = await self.db.execute(
            select(InsuranceClaim).where(
                InsuranceClaim.id == claim_id,
                InsuranceClaim.facility_id == facility_id,
                InsuranceClaim.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def update_claim_status(
        self, claim_id: uuid.UUID, data: ClaimStatusUpdate, facility_id: uuid.UUID, updated_by: uuid.UUID
    ) -> InsuranceClaim | None:
        """
        Update claim status.

        @param claim_id: Claim UUID
        @param data: Status update data
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated claim or None
        """
        claim = await self.get_claim(claim_id, facility_id)
        if not claim:
            return None

        now = datetime.now(UTC)
        claim.status = data.status
        if data.approved_amount is not None:
            claim.approved_amount = data.approved_amount
        if data.paid_amount is not None:
            claim.paid_amount = data.paid_amount
        if data.rejection_reason:
            claim.rejection_reason = data.rejection_reason
        if data.sha_reference:
            claim.sha_reference = data.sha_reference

        if data.status == "submitted":
            claim.submitted_date = now
        elif data.status in ("approved", "partially_approved", "rejected"):
            claim.processed_date = now
        elif data.status == "paid":
            claim.paid_date = now

        claim.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(claim)
        return claim

    async def get_summary(self, facility_id: uuid.UUID) -> InsuranceSummary:
        """
        Get insurance summary stats.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        base = [InsuranceClaim.facility_id == facility_id, InsuranceClaim.is_deleted == False]  # noqa: E712

        total = await self.db.execute(select(func.count(InsuranceClaim.id)).where(*base))
        pending = await self.db.execute(
            select(func.count(InsuranceClaim.id)).where(*base, InsuranceClaim.status == "draft")
        )
        submitted = await self.db.execute(
            select(func.count(InsuranceClaim.id)).where(*base, InsuranceClaim.status == "submitted")
        )
        approved = await self.db.execute(
            select(func.count(InsuranceClaim.id)).where(
                *base, InsuranceClaim.status.in_(["approved", "partially_approved"])
            )
        )
        rejected = await self.db.execute(
            select(func.count(InsuranceClaim.id)).where(*base, InsuranceClaim.status == "rejected")
        )
        value = await self.db.execute(select(func.sum(InsuranceClaim.claim_amount)).where(*base))
        schemes = await self.db.execute(
            select(func.count(InsuranceScheme.id)).where(
                InsuranceScheme.facility_id == facility_id,
                InsuranceScheme.is_deleted == False,  # noqa: E712
                InsuranceScheme.is_active == True,  # noqa: E712
            )
        )
        preauth = await self.db.execute(
            select(func.count(PreAuthorization.id)).where(
                PreAuthorization.facility_id == facility_id,
                PreAuthorization.status == "pending",
            )
        )

        return InsuranceSummary(
            total_claims=total.scalar() or 0,
            pending_claims=pending.scalar() or 0,
            submitted_claims=submitted.scalar() or 0,
            approved_claims=approved.scalar() or 0,
            rejected_claims=rejected.scalar() or 0,
            total_claim_value=value.scalar() or 0,
            active_schemes=schemes.scalar() or 0,
            preauth_pending=preauth.scalar() or 0,
        )

    # ── Patient insurance (multi-entry) ─────────────────────────────────────

    async def list_patient_insurances(
        self, patient_id: uuid.UUID, facility_id: uuid.UUID
    ) -> list[PatientInsuranceResponse]:
        """
        List all (non-deleted) insurance entries for a patient.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID (multi-tenant scope)
        @returns Insurance entries with scheme details, primary first
        """
        result = await self.db.execute(
            select(
                PatientInsurance,
                InsuranceScheme.name.label("scheme_name"),
                InsuranceScheme.scheme_type.label("scheme_type"),
            )
            .join(
                InsuranceScheme, PatientInsurance.scheme_id == InsuranceScheme.id
            )
            .where(
                PatientInsurance.facility_id == facility_id,
                PatientInsurance.patient_id == patient_id,
                PatientInsurance.is_deleted == False,  # noqa: E712
            )
            .order_by(
                PatientInsurance.is_primary.desc(),
                PatientInsurance.created_at.asc(),
            )
        )
        items: list[PatientInsuranceResponse] = []
        for pi, scheme_name, scheme_type in result.all():
            items.append(
                PatientInsuranceResponse(
                    id=pi.id,
                    patient_id=pi.patient_id,
                    scheme_id=pi.scheme_id,
                    scheme_name=scheme_name,
                    scheme_type=scheme_type,
                    member_number=pi.member_number,
                    principal_name=pi.principal_name,
                    relationship=pi.relationship,
                    valid_from=pi.valid_from,
                    valid_to=pi.valid_to,
                    is_active=pi.is_active,
                    is_primary=pi.is_primary,
                    notes=pi.notes,
                    created_at=pi.created_at,
                    updated_at=pi.updated_at,
                )
            )
        return items

    async def get_patient_insurance(
        self,
        insurance_id: uuid.UUID,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> PatientInsurance | None:
        """
        Fetch a single insurance entry, scoped by patient + facility.

        @param insurance_id: Insurance entry UUID
        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @returns Row or None
        """
        result = await self.db.execute(
            select(PatientInsurance).where(
                PatientInsurance.id == insurance_id,
                PatientInsurance.patient_id == patient_id,
                PatientInsurance.facility_id == facility_id,
                PatientInsurance.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def _has_primary(
        self, patient_id: uuid.UUID, facility_id: uuid.UUID
    ) -> bool:
        """Return True if patient already has an active primary insurance."""
        result = await self.db.execute(
            select(func.count(PatientInsurance.id)).where(
                PatientInsurance.patient_id == patient_id,
                PatientInsurance.facility_id == facility_id,
                PatientInsurance.is_primary == True,  # noqa: E712
                PatientInsurance.is_deleted == False,  # noqa: E712
            )
        )
        return (result.scalar() or 0) > 0

    async def _demote_other_primaries(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        keep_id: uuid.UUID | None,
        updated_by: uuid.UUID,
    ) -> None:
        """
        Demote all other primary insurance entries for a patient. Ensures
        at most one row has is_primary=True at any time.
        """
        stmt = (
            update(PatientInsurance)
            .where(
                PatientInsurance.patient_id == patient_id,
                PatientInsurance.facility_id == facility_id,
                PatientInsurance.is_primary == True,  # noqa: E712
                PatientInsurance.is_deleted == False,  # noqa: E712
            )
            .values(is_primary=False, updated_by=updated_by)
        )
        if keep_id is not None:
            stmt = stmt.where(PatientInsurance.id != keep_id)
        await self.db.execute(stmt)

    async def _sync_patient_legacy_columns(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> None:
        """
        Mirror the patient's primary insurance into the legacy
        Patient.insurance_provider / Patient.insurance_member_number columns
        so older callers and FHIR exports stay consistent.
        """
        result = await self.db.execute(
            select(
                InsuranceScheme.name,
                PatientInsurance.member_number,
            )
            .join(
                InsuranceScheme,
                PatientInsurance.scheme_id == InsuranceScheme.id,
            )
            .where(
                PatientInsurance.patient_id == patient_id,
                PatientInsurance.facility_id == facility_id,
                PatientInsurance.is_primary == True,  # noqa: E712
                PatientInsurance.is_deleted == False,  # noqa: E712
            )
            .limit(1)
        )
        row = result.first()
        provider = row[0] if row else None
        member_no = row[1] if row else None

        await self.db.execute(
            update(Patient)
            .where(
                Patient.id == patient_id,
                Patient.facility_id == facility_id,
            )
            .values(
                insurance_provider=provider,
                insurance_member_number=member_no,
                updated_by=updated_by,
            )
        )

    async def add_patient_insurance(
        self,
        patient_id: uuid.UUID,
        data: PatientInsuranceCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> PatientInsurance:
        """
        Add a new insurance entry for a patient. If is_primary=True, demote any
        existing primary entry. If the patient has no primary yet, promote the
        new entry automatically.

        @param patient_id: Patient UUID
        @param data: Insurance entry data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created row
        """
        # Verify scheme belongs to facility
        scheme = await self.db.execute(
            select(InsuranceScheme).where(
                InsuranceScheme.id == data.scheme_id,
                InsuranceScheme.facility_id == facility_id,
                InsuranceScheme.is_deleted == False,  # noqa: E712
            )
        )
        if scheme.scalar_one_or_none() is None:
            raise ValueError("Insurance scheme not found for this facility")

        wants_primary = data.is_primary or not await self._has_primary(
            patient_id, facility_id
        )

        entry = PatientInsurance(
            facility_id=facility_id,
            patient_id=patient_id,
            scheme_id=data.scheme_id,
            member_number=data.member_number,
            principal_name=data.principal_name,
            relationship=data.relationship,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            is_active=True,
            is_primary=wants_primary,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(entry)
        await self.db.flush()

        if wants_primary:
            await self._demote_other_primaries(
                patient_id, facility_id, keep_id=entry.id, updated_by=created_by
            )
            await self._sync_patient_legacy_columns(
                patient_id, facility_id, updated_by=created_by
            )

        await self.db.refresh(entry)
        return entry

    async def update_patient_insurance(
        self,
        insurance_id: uuid.UUID,
        patient_id: uuid.UUID,
        data: PatientInsuranceUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> PatientInsurance | None:
        """
        Edit an insurance entry. Toggling is_primary=True demotes others.

        @param insurance_id: Insurance entry UUID
        @param patient_id: Patient UUID
        @param data: Update payload
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated row or None if not found
        """
        entry = await self.get_patient_insurance(
            insurance_id, patient_id, facility_id
        )
        if not entry:
            return None

        # Validate scheme switch
        if data.scheme_id is not None and data.scheme_id != entry.scheme_id:
            scheme = await self.db.execute(
                select(InsuranceScheme).where(
                    InsuranceScheme.id == data.scheme_id,
                    InsuranceScheme.facility_id == facility_id,
                    InsuranceScheme.is_deleted == False,  # noqa: E712
                )
            )
            if scheme.scalar_one_or_none() is None:
                raise ValueError(
                    "Insurance scheme not found for this facility"
                )

        update_data = data.model_dump(exclude_unset=True)
        promoting = update_data.get("is_primary") is True
        for field, value in update_data.items():
            setattr(entry, field, value)
        entry.updated_by = updated_by

        await self.db.flush()

        if promoting:
            await self._demote_other_primaries(
                patient_id, facility_id, keep_id=entry.id, updated_by=updated_by
            )

        # Always re-sync legacy columns in case primary/member changed
        await self._sync_patient_legacy_columns(
            patient_id, facility_id, updated_by=updated_by
        )

        await self.db.refresh(entry)
        return entry

    async def delete_patient_insurance(
        self,
        insurance_id: uuid.UUID,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> bool:
        """
        Soft-delete an insurance entry. If it was the primary, promote the
        oldest remaining active entry (if any) to primary.

        @param insurance_id: Insurance entry UUID
        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns True if deleted, False if not found
        """
        entry = await self.get_patient_insurance(
            insurance_id, patient_id, facility_id
        )
        if not entry:
            return False

        was_primary = entry.is_primary
        entry.is_deleted = True
        entry.deleted_at = datetime.now(UTC)
        entry.is_active = False
        entry.is_primary = False
        entry.updated_by = updated_by
        await self.db.flush()

        if was_primary:
            # Promote oldest remaining active entry to primary
            next_primary = await self.db.execute(
                select(PatientInsurance)
                .where(
                    PatientInsurance.patient_id == patient_id,
                    PatientInsurance.facility_id == facility_id,
                    PatientInsurance.is_deleted == False,  # noqa: E712
                    PatientInsurance.is_active == True,  # noqa: E712
                )
                .order_by(PatientInsurance.created_at.asc())
                .limit(1)
            )
            new_primary = next_primary.scalar_one_or_none()
            if new_primary is not None:
                new_primary.is_primary = True
                new_primary.updated_by = updated_by
                await self.db.flush()

        await self._sync_patient_legacy_columns(
            patient_id, facility_id, updated_by=updated_by
        )
        return True

    async def set_primary_insurance(
        self,
        insurance_id: uuid.UUID,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> PatientInsurance | None:
        """
        Promote a specific insurance entry to primary, demote others.

        @param insurance_id: Insurance entry UUID
        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated primary entry, or None if not found
        """
        entry = await self.get_patient_insurance(
            insurance_id, patient_id, facility_id
        )
        if not entry:
            return None

        entry.is_primary = True
        entry.is_active = True
        entry.updated_by = updated_by
        await self.db.flush()

        await self._demote_other_primaries(
            patient_id, facility_id, keep_id=entry.id, updated_by=updated_by
        )
        await self._sync_patient_legacy_columns(
            patient_id, facility_id, updated_by=updated_by
        )

        await self.db.refresh(entry)
        return entry
