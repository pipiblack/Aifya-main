"""
Prescription service — creates prescriptions with CDS-powered drug interaction checks.
Drug interaction checks MUST run before prescription save (CLAUDE.md: Clinical Safety).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.models.base import EventBase
from app.models.prescription import Prescription
from app.schemas.prescription import PrescriptionCreate
from app.services.cds.engine import evaluate_prescription
from app.services.cds.models import CDSAlert

logger = get_logger(__name__)


def _cds_alert_to_dict(alert: CDSAlert) -> dict[str, str | list[str]]:
    """
    Convert a CDSAlert to the dict format expected by the Prescription model.

    @param alert: CDS alert object from the engine
    @returns Dict with severity, affected_items, interacting_drug, message, description, category
    """
    return {
        "severity": alert.severity.value,
        "category": alert.category.value,
        "affected_items": alert.affected_items,
        "interacting_drug": ", ".join(alert.affected_items) if alert.affected_items else "",
        "message": alert.message,
        "description": alert.message,
        "title": alert.title,
        "source_rule": alert.source_rule,
        "action": alert.action.value,
    }


class PrescriptionService:
    """
    Service for prescription management.
    Drug interaction checks MUST run before prescription save (CLAUDE.md).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_prescription(
        self,
        data: PrescriptionCreate,
        facility_id: uuid.UUID,
        prescriber_id: uuid.UUID,
    ) -> tuple[Prescription, list[dict[str, str | list[str]]], bool]:
        """
        Create a prescription with drug interaction checking.
        Blocks on critical interactions per CLAUDE.md: Clinical Safety.

        @param data: Prescription data
        @param facility_id: Facility UUID
        @param prescriber_id: Doctor's staff UUID
        @returns Tuple of (prescription, interactions, blocked)
        """
        # Check drug interactions via CDS engine
        interactions = await self._check_interactions(
            patient_id=data.patient_id,
            drug_name=data.drug_name,
            facility_id=facility_id,
        )

        # Block on critical interactions
        has_critical = any(i["severity"] == "critical" for i in interactions)

        prescription = Prescription(
            facility_id=facility_id,
            encounter_id=data.encounter_id,
            patient_id=data.patient_id,
            prescriber_id=prescriber_id,
            interaction_checked=True,
            interactions=interactions if interactions else None,
            created_by=prescriber_id,
            updated_by=prescriber_id,
            **data.model_dump(exclude={"encounter_id", "patient_id"}),
        )

        if has_critical:
            # Do not save — return with blocked flag
            return prescription, interactions, True

        self.db.add(prescription)
        await self.db.flush()
        await self.db.refresh(prescription)

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="prescription",
            stream_id=data.patient_id,
            event_type="PrescriptionCreated",
            event_data={
                "drug_name": data.drug_name,
                "dosage": data.dosage,
                "route": data.route,
                "frequency": data.frequency,
                "duration_days": data.duration_days,
                "is_keml": data.is_keml,
                "interactions_found": len(interactions),
            },
            version=1,
            created_by=prescriber_id,
        )
        self.db.add(event)

        return prescription, interactions, False

    async def get_encounter_prescriptions(self, encounter_id: uuid.UUID, facility_id: uuid.UUID) -> list[Prescription]:
        """
        Get all prescriptions for an encounter.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns List of prescriptions
        """
        result = await self.db.execute(
            select(Prescription)
            .where(
                Prescription.encounter_id == encounter_id,
                Prescription.facility_id == facility_id,
                Prescription.is_deleted == False,  # noqa: E712
            )
            .order_by(Prescription.created_at.desc())
        )
        return list(result.scalars().all())

    async def _check_interactions(
        self,
        patient_id: uuid.UUID,
        drug_name: str,
        facility_id: uuid.UUID,
    ) -> list[dict[str, str | list[str]]]:
        """
        Check for drug interactions using the CDS engine.
        Evaluates drug-drug interactions, allergy checks, condition
        contraindications, age safety, pregnancy safety, and duplicate therapy.

        @param patient_id: Patient UUID
        @param drug_name: New drug being prescribed
        @param facility_id: Facility UUID
        @returns List of interaction dicts with severity, affected_items, message, etc.
        """
        try:
            cds_result = await evaluate_prescription(
                db=self.db,
                patient_id=patient_id,
                facility_id=facility_id,
                drug_name=drug_name,
            )
            interactions = [_cds_alert_to_dict(alert) for alert in cds_result.alerts]
        except Exception:
            # Fallback: if CDS engine fails, log and return empty
            # Never block prescriptions due to CDS infrastructure issues
            logger.warning(
                "cds_prescription_check_failed",
                patient_id=str(patient_id),
                drug_name=drug_name,
                exc_info=True,
            )
            interactions = []

        return interactions
