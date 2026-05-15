"""ClaimFlow action endpoints — submit / sync / approve from within Aifya.

These routes piggy-back on the existing ``/api/v1/insurance`` prefix so that
the frontend can call them right next to the regular insurance endpoints
without users having to switch tools.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.config import settings
from app.database import get_db
from app.models.insurance import InsuranceClaim, InsuranceScheme
from app.models.patient import Patient
from app.services.claimflow import (
    ClaimFlowClient,
    ClaimFlowUnavailableError,
    get_claimflow_client,
)
from sqlalchemy import select

router = APIRouter(dependencies=[Depends(require_module("insurance"))])


async def _load_claim_with_context(
    db: AsyncSession,
    claim_id: uuid.UUID,
    facility_id: uuid.UUID,
) -> tuple[InsuranceClaim, Patient | None, InsuranceScheme | None]:
    """Load a claim + patient + scheme scoped to the caller's facility."""
    claim_result = await db.execute(
        select(InsuranceClaim).where(
            InsuranceClaim.id == claim_id,
            InsuranceClaim.facility_id == facility_id,
            InsuranceClaim.is_deleted == False,  # noqa: E712
        )
    )
    claim = claim_result.scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    patient_result = await db.execute(
        select(Patient).where(
            Patient.id == claim.patient_id,
            Patient.facility_id == facility_id,
            Patient.is_deleted == False,  # noqa: E712
        )
    )
    patient = patient_result.scalar_one_or_none()

    scheme_result = await db.execute(
        select(InsuranceScheme).where(
            InsuranceScheme.id == claim.scheme_id,
            InsuranceScheme.facility_id == facility_id,
            InsuranceScheme.is_deleted == False,  # noqa: E712
        )
    )
    scheme = scheme_result.scalar_one_or_none()
    return claim, patient, scheme


def _build_claimflow_payload(
    claim: InsuranceClaim, patient: Patient | None, scheme: InsuranceScheme | None
) -> dict[str, Any]:
    """Translate an Aifya claim into the ClaimFlow submission shape."""
    return {
        "claim_number": claim.claim_number,
        "facility_id": str(claim.facility_id),
        "patient": {
            "id": str(claim.patient_id),
            "name": (
                f"{patient.first_name} {patient.last_name}"
                if patient is not None
                else None
            ),
            "mrn": patient.mrn if patient is not None else None,
            "national_id": patient.national_id if patient is not None else None,
        },
        "scheme": {
            "id": str(claim.scheme_id),
            "name": scheme.name if scheme is not None else None,
            "scheme_type": scheme.scheme_type if scheme is not None else None,
            "code": scheme.scheme_code if scheme is not None else None,
        },
        "member_number": claim.member_number,
        "amount_cents": claim.claim_amount,
        "items": claim.claim_items or [],
        "diagnosis_codes": claim.diagnosis_codes or [],
        "notes": claim.notes,
        "encounter_id": str(claim.encounter_id) if claim.encounter_id else None,
        "invoice_id": str(claim.invoice_id) if claim.invoice_id else None,
    }


def _store_external_id_in_sha_reference(
    claim: InsuranceClaim, external_id: str | None
) -> None:
    """Persist the ClaimFlow external_id on the claim row.

    The ``insurance_claims`` table already has a ``sha_reference`` column we
    reuse for this (no schema change required). It is prefixed ``CF:`` so we
    can tell ClaimFlow-issued ids apart from SHA reference numbers.
    """
    if external_id:
        claim.sha_reference = f"CF:{external_id}"


# ── Submit ───────────────────────────────────────────────────────────────────


@router.post("/claims/{claim_id}/submit-to-claimflow")
async def submit_to_claimflow(
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("claims_admin", "finance_admin", "admin", "facility_admin", "billing_officer")
    ),
    client: ClaimFlowClient = Depends(get_claimflow_client),
) -> dict[str, Any]:
    """Submit an Aifya claim to ClaimFlow.

    Updates the local claim status to ``submitted`` and records the
    ClaimFlow ``external_id`` in ``sha_reference`` (prefixed ``CF:``).
    """
    claim, patient, scheme = await _load_claim_with_context(
        db, claim_id, current_user.facility_id
    )

    payload = _build_claimflow_payload(claim, patient, scheme)
    try:
        response = await client.submit_claim(payload)
    except ClaimFlowUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    if not response.ok:
        detail = response.data.get("detail") or response.data.get("message") or (
            "ClaimFlow rejected the submission."
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    external_id = response.data.get("external_id") or response.data.get("id")
    external_status = response.data.get("status", "submitted")

    _store_external_id_in_sha_reference(claim, external_id)
    claim.status = "submitted"
    claim.submitted_date = datetime.now(UTC)
    claim.updated_by = current_user.user_id
    await db.flush()

    return {
        "ok": True,
        "claim_id": str(claim.id),
        "local_status": claim.status,
        "claimflow_external_id": external_id,
        "claimflow_status": external_status,
        "view_url": (
            f"{settings.claimflow_api_url.rstrip('/')}/claims/{external_id}"
            if external_id
            else None
        ),
    }


# ── Status ───────────────────────────────────────────────────────────────────


@router.get("/claims/{claim_id}/claimflow-status")
async def get_claimflow_status(
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    client: ClaimFlowClient = Depends(get_claimflow_client),
) -> dict[str, Any]:
    """Fetch the latest status from ClaimFlow for this claim."""
    claim, _patient, _scheme = await _load_claim_with_context(
        db, claim_id, current_user.facility_id
    )

    external_id = _extract_claimflow_id(claim.sha_reference)
    if not external_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This claim has not been submitted to ClaimFlow yet.",
        )

    try:
        response = await client.get_claim_status(external_id)
    except ClaimFlowUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return {
        "ok": response.ok,
        "claim_id": str(claim.id),
        "claimflow_external_id": external_id,
        "claimflow_status": response.data.get("status"),
        "details": response.data,
        "view_url": (
            f"{settings.claimflow_api_url.rstrip('/')}/claims/{external_id}"
        ),
    }


# ── Sync ─────────────────────────────────────────────────────────────────────


@router.post("/claims/{claim_id}/sync-with-claimflow")
async def sync_with_claimflow(
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("claims_admin", "finance_admin", "admin", "facility_admin", "billing_officer")
    ),
    client: ClaimFlowClient = Depends(get_claimflow_client),
) -> dict[str, Any]:
    """Fetch latest from ClaimFlow and update local claim status/amounts."""
    claim, _patient, _scheme = await _load_claim_with_context(
        db, claim_id, current_user.facility_id
    )

    external_id = _extract_claimflow_id(claim.sha_reference)
    if not external_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This claim has not been submitted to ClaimFlow yet.",
        )

    try:
        response = await client.get_claim_status(external_id)
    except ClaimFlowUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    if not response.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.data.get("detail") or "ClaimFlow returned an error",
        )

    cf_status = response.data.get("status")
    approved = response.data.get("approved_amount_cents")
    paid = response.data.get("paid_amount_cents")

    # Map ClaimFlow statuses to Aifya statuses (best-effort)
    mapping = {
        "submitted": "submitted",
        "under_review": "processing",
        "processing": "processing",
        "approved": "approved",
        "partially_approved": "partially_approved",
        "rejected": "rejected",
        "paid": "paid",
    }
    mapped = mapping.get(str(cf_status or "").lower())
    if mapped:
        claim.status = mapped
        if mapped in ("approved", "partially_approved", "rejected"):
            claim.processed_date = datetime.now(UTC)
        if mapped == "paid":
            claim.paid_date = datetime.now(UTC)
    if isinstance(approved, int) and approved >= 0:
        claim.approved_amount = approved
    if isinstance(paid, int) and paid >= 0:
        claim.paid_amount = paid

    claim.updated_by = current_user.user_id
    await db.flush()

    return {
        "ok": True,
        "claim_id": str(claim.id),
        "local_status": claim.status,
        "claimflow_status": cf_status,
        "approved_amount": claim.approved_amount,
        "paid_amount": claim.paid_amount,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_claimflow_id(sha_reference: str | None) -> str | None:
    """Pull a ClaimFlow external id out of ``sha_reference`` (CF:<id>)."""
    if not sha_reference:
        return None
    if sha_reference.startswith("CF:"):
        return sha_reference[3:].strip() or None
    return None
