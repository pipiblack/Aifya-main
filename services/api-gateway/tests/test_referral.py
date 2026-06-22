import uuid

import pytest
from httpx import AsyncClient


# -- Helpers ------------------------------------------------------------------


async def _create_patient(client: AsyncClient) -> str:
    """Create a test patient and return their ID.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Referral",
            "last_name": "TestPatient",
            "date_of_birth": "1975-08-20",
            "gender": "male",
            "phone_number": "0711300400",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_referral(client: AsyncClient, patient_id: str) -> dict[str, object]:
    """Create a referral and return the full response body.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Referral response dict
    """
    response = await client.post(
        "/api/v1/referrals",
        json={
            "patient_id": patient_id,
            "direction": "outgoing",
            "referral_type": "external",
            "referring_facility_name": "County Hospital",
            "receiving_facility_name": "National Hospital",
            "reason": "Advanced cardiac care",
            "urgency": "urgent",
            "clinical_notes": "Patient with unstable angina",
        },
    )
    assert response.status_code == 201
    return response.json()


# -- Summary ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_referral_summary(client: AsyncClient) -> None:
    """Test fetching referral summary stats."""
    response = await client.get("/api/v1/referrals/summary")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert isinstance(data, dict)


# -- Referrals: empty list ----------------------------------------------------


@pytest.mark.asyncio
async def test_list_referrals_empty(client: AsyncClient) -> None:
    """Test listing referrals returns empty when none exist."""
    response = await client.get("/api/v1/referrals")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert isinstance(data, dict)


# -- Referrals: create --------------------------------------------------------


@pytest.mark.asyncio
async def test_create_referral(client: AsyncClient) -> None:
    """Test creating a patient referral."""
    patient_id = await _create_patient(client)

    response = await client.post(
        "/api/v1/referrals",
        json={
            "patient_id": patient_id,
            "direction": "outgoing",
            "referral_type": "external",
            "referring_facility_name": "County Hospital",
            "receiving_facility_name": "National Hospital",
            "reason": "Advanced cardiac care",
            "urgency": "urgent",
            "clinical_notes": "Patient with unstable angina",
        },
    )

    assert response.status_code == 201
    data: dict[str, object] = response.json()
    assert data["patient_id"] == patient_id
    assert data["direction"] == "outgoing"
    assert data["referral_type"] == "external"
    assert data["referring_facility_name"] == "County Hospital"
    assert data["receiving_facility_name"] == "National Hospital"
    assert data["reason"] == "Advanced cardiac care"
    assert data["urgency"] == "urgent"
    assert data["clinical_notes"] == "Patient with unstable angina"
    assert "id" in data
    assert "created_at" in data


# -- Referrals: get detail ----------------------------------------------------


@pytest.mark.asyncio
async def test_get_referral(client: AsyncClient) -> None:
    """Test fetching a single referral by ID."""
    patient_id = await _create_patient(client)
    referral = await _create_referral(client, patient_id)
    referral_id: str = referral["id"]  # type: ignore[assignment]

    response = await client.get(f"/api/v1/referrals/{referral_id}")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == referral_id
    assert data["reason"] == "Advanced cardiac care"


# -- Referrals: 404 -----------------------------------------------------------


@pytest.mark.asyncio
async def test_get_referral_not_found(client: AsyncClient) -> None:
    """Test 404 when fetching a non-existent referral."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/referrals/{fake_id}")

    assert response.status_code == 404


# -- Referrals: update status -------------------------------------------------


@pytest.mark.asyncio
async def test_update_referral_status(client: AsyncClient) -> None:
    """Test updating the status of a referral."""
    patient_id = await _create_patient(client)
    referral = await _create_referral(client, patient_id)
    referral_id: str = referral["id"]  # type: ignore[assignment]

    response = await client.post(
        f"/api/v1/referrals/{referral_id}/status",
        json={
            "status": "accepted",
            "response_notes": "Will review patient",
        },
    )

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == referral_id
