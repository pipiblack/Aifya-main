import uuid

import pytest
from httpx import AsyncClient

# ── Helpers ──────────────────────────────────────────────────────────────────


async def _create_patient(client: AsyncClient) -> str:
    """Create a test patient and return their ID.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Amina",
            "last_name": "Ochieng",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "phone_number": "0700000000",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_encounter(client: AsyncClient, patient_id: str) -> str:
    """Create an IPD encounter for a patient and return the encounter ID.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Encounter UUID string
    """
    response = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "ipd",
            "chief_complaint": "Severe pneumonia requiring admission",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_ward(client: AsyncClient) -> dict:
    """Create a test ward and return the response data.

    @param client: Async HTTP test client
    @returns Ward response dict with id, name, ward_type, capacity
    """
    response = await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "General Ward A",
            "ward_type": "general",
            "capacity": 20,
        },
    )
    assert response.status_code == 201
    return response.json()


async def _create_bed(client: AsyncClient, ward_id: str) -> dict:
    """Create a test bed in a ward and return the response data.

    @param client: Async HTTP test client
    @param ward_id: Ward UUID string
    @returns Bed response dict with id, bed_number, bed_type, ward_id
    """
    response = await client.post(
        "/api/v1/ipd/beds",
        json={
            "ward_id": ward_id,
            "bed_number": "A-101",
            "bed_type": "standard",
        },
    )
    assert response.status_code == 201
    return response.json()


async def _create_admission(client: AsyncClient) -> dict:
    """Create a full admission (patient + encounter + ward + bed + admit).

    @param client: Async HTTP test client
    @returns Dict with admission data and supporting IDs
    """
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    ward = await _create_ward(client)
    bed = await _create_bed(client, ward["id"])

    response = await client.post(
        "/api/v1/ipd/admissions",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "bed_id": bed["id"],
            "admitting_diagnosis": "Pneumonia",
            "admission_type": "emergency",
        },
    )
    assert response.status_code == 201
    data = response.json()
    return {
        "admission": data,
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "ward_id": ward["id"],
        "bed_id": bed["id"],
    }


# ── Ward Board Summary ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ward_board_summary_empty(client: AsyncClient) -> None:
    """Test ward board summary returns zeroed stats when no data exists."""
    response = await client.get("/api/v1/ipd/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_beds" in data
    assert "occupied_beds" in data
    assert "available_beds" in data
    assert "active_admissions" in data


# ── Ward Management ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_wards_empty(client: AsyncClient) -> None:
    """Test listing wards returns empty list when none exist."""
    response = await client.get("/api/v1/ipd/wards")
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_create_ward(client: AsyncClient) -> None:
    """Test creating a new ward with valid data."""
    response = await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "ICU Ward",
            "ward_type": "icu",
            "capacity": 10,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "ICU Ward"
    assert data["ward_type"] == "icu"
    assert data["capacity"] == 10
    assert "id" in data


@pytest.mark.asyncio
async def test_create_ward_general(client: AsyncClient) -> None:
    """Test creating a general ward."""
    response = await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "General Ward B",
            "ward_type": "general",
            "capacity": 30,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ward_type"] == "general"


@pytest.mark.asyncio
async def test_create_ward_maternity(client: AsyncClient) -> None:
    """Test creating a maternity ward."""
    response = await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "Maternity Wing",
            "ward_type": "maternity",
            "capacity": 15,
        },
    )
    assert response.status_code == 201
    assert response.json()["ward_type"] == "maternity"


@pytest.mark.asyncio
async def test_create_ward_pediatric(client: AsyncClient) -> None:
    """Test creating a pediatric ward."""
    response = await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "Pediatric Ward",
            "ward_type": "pediatric",
            "capacity": 12,
        },
    )
    assert response.status_code == 201
    assert response.json()["ward_type"] == "pediatric"


@pytest.mark.asyncio
async def test_create_ward_private(client: AsyncClient) -> None:
    """Test creating a private ward."""
    response = await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "Private Rooms",
            "ward_type": "private",
            "capacity": 5,
        },
    )
    assert response.status_code == 201
    assert response.json()["ward_type"] == "private"


@pytest.mark.asyncio
async def test_create_ward_invalid_type(client: AsyncClient) -> None:
    """Test validation rejects invalid ward type."""
    response = await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "Bad Ward",
            "ward_type": "invalid_type",
            "capacity": 10,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_ward_missing_name(client: AsyncClient) -> None:
    """Test validation rejects missing required fields."""
    response = await client.post(
        "/api/v1/ipd/wards",
        json={
            "ward_type": "general",
            "capacity": 10,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_wards_after_creation(client: AsyncClient) -> None:
    """Test listing wards returns created wards."""
    await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "Ward 1",
            "ward_type": "general",
            "capacity": 20,
        },
    )
    await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "Ward 2",
            "ward_type": "icu",
            "capacity": 8,
        },
    )

    response = await client.get("/api/v1/ipd/wards")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


# ── Bed Management ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_beds_empty(client: AsyncClient) -> None:
    """Test listing beds returns empty list when none exist."""
    response = await client.get("/api/v1/ipd/beds")
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_create_bed_standard(client: AsyncClient) -> None:
    """Test creating a standard bed in a ward."""
    ward = await _create_ward(client)

    response = await client.post(
        "/api/v1/ipd/beds",
        json={
            "ward_id": ward["id"],
            "bed_number": "B-001",
            "bed_type": "standard",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["bed_number"] == "B-001"
    assert data["bed_type"] == "standard"
    assert data["ward_id"] == ward["id"]
    assert "id" in data


@pytest.mark.asyncio
async def test_create_bed_electric(client: AsyncClient) -> None:
    """Test creating an electric bed."""
    ward = await _create_ward(client)

    response = await client.post(
        "/api/v1/ipd/beds",
        json={
            "ward_id": ward["id"],
            "bed_number": "B-002",
            "bed_type": "electric",
        },
    )
    assert response.status_code == 201
    assert response.json()["bed_type"] == "electric"


@pytest.mark.asyncio
async def test_create_bed_icu(client: AsyncClient) -> None:
    """Test creating an ICU bed."""
    ward = await _create_ward(client)

    response = await client.post(
        "/api/v1/ipd/beds",
        json={
            "ward_id": ward["id"],
            "bed_number": "ICU-001",
            "bed_type": "icu",
        },
    )
    assert response.status_code == 201
    assert response.json()["bed_type"] == "icu"


@pytest.mark.asyncio
async def test_create_bed_invalid_type(client: AsyncClient) -> None:
    """Test validation rejects invalid bed type."""
    ward = await _create_ward(client)

    response = await client.post(
        "/api/v1/ipd/beds",
        json={
            "ward_id": ward["id"],
            "bed_number": "X-001",
            "bed_type": "waterbed",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_bed_missing_ward(client: AsyncClient) -> None:
    """Test validation rejects bed creation without ward_id."""
    response = await client.post(
        "/api/v1/ipd/beds",
        json={
            "bed_number": "B-001",
            "bed_type": "standard",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_beds_after_creation(client: AsyncClient) -> None:
    """Test listing beds returns created beds."""
    ward = await _create_ward(client)
    await client.post(
        "/api/v1/ipd/beds",
        json={
            "ward_id": ward["id"],
            "bed_number": "C-001",
            "bed_type": "standard",
        },
    )
    await client.post(
        "/api/v1/ipd/beds",
        json={
            "ward_id": ward["id"],
            "bed_number": "C-002",
            "bed_type": "electric",
        },
    )

    response = await client.get("/api/v1/ipd/beds")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_beds_filter_by_ward(client: AsyncClient) -> None:
    """Test filtering beds by ward_id query parameter."""
    ward1 = await _create_ward(client)
    ward2_resp = await client.post(
        "/api/v1/ipd/wards",
        json={
            "name": "Ward 2",
            "ward_type": "icu",
            "capacity": 5,
        },
    )
    ward2 = ward2_resp.json()

    await client.post(
        "/api/v1/ipd/beds",
        json={
            "ward_id": ward1["id"],
            "bed_number": "W1-001",
            "bed_type": "standard",
        },
    )
    await client.post(
        "/api/v1/ipd/beds",
        json={
            "ward_id": ward2["id"],
            "bed_number": "W2-001",
            "bed_type": "icu",
        },
    )

    response = await client.get("/api/v1/ipd/beds", params={"ward_id": ward1["id"]})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ward_id"] == ward1["id"]


# ── Admissions ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_admissions_empty(client: AsyncClient) -> None:
    """Test listing admissions returns empty when none exist."""
    response = await client.get("/api/v1/ipd/admissions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_admit_patient(client: AsyncClient) -> None:
    """Test full admission flow: create patient, encounter, ward, bed, then admit."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    ward = await _create_ward(client)
    bed = await _create_bed(client, ward["id"])

    response = await client.post(
        "/api/v1/ipd/admissions",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "bed_id": bed["id"],
            "admitting_diagnosis": "Pneumonia",
            "admission_type": "emergency",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["patient_id"] == patient_id
    assert data["encounter_id"] == encounter_id
    assert data["bed_id"] == bed["id"]
    assert data["admitting_diagnosis"] == "Pneumonia"
    assert data["admission_type"] == "emergency"
    assert "id" in data
    assert "admitted_at" in data


@pytest.mark.asyncio
async def test_admit_patient_missing_fields(client: AsyncClient) -> None:
    """Test validation rejects admission with missing required fields."""
    response = await client.post(
        "/api/v1/ipd/admissions",
        json={
            "admitting_diagnosis": "Pneumonia",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admit_patient_with_idempotency_key(client: AsyncClient) -> None:
    """Test admission accepts X-Idempotency-Key header."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    ward = await _create_ward(client)
    bed = await _create_bed(client, ward["id"])

    response = await client.post(
        "/api/v1/ipd/admissions",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "bed_id": bed["id"],
            "admitting_diagnosis": "Malaria",
            "admission_type": "emergency",
        },
        headers={"X-Idempotency-Key": "ipd-admit-001"},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_get_admission_detail(client: AsyncClient) -> None:
    """Test fetching a single admission by ID."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.get(f"/api/v1/ipd/admissions/{admission_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == admission_id
    assert data["patient_id"] == result["patient_id"]
    assert data["admitting_diagnosis"] == "Pneumonia"


@pytest.mark.asyncio
async def test_get_admission_not_found(client: AsyncClient) -> None:
    """Test 404 for non-existent admission."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/ipd/admissions/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_admissions_after_admit(client: AsyncClient) -> None:
    """Test listing admissions includes the newly created admission."""
    await _create_admission(client)

    response = await client.get("/api/v1/ipd/admissions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


# ── Nursing Notes ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_nursing_note_assessment(client: AsyncClient) -> None:
    """Test adding an assessment nursing note to an admission."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/notes",
        json={
            "note_type": "assessment",
            "content": "Patient alert and oriented. Temp 38.2C. Lungs: bilateral crackles.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["note_type"] == "assessment"
    assert "bilateral crackles" in data["content"]
    assert "id" in data


@pytest.mark.asyncio
async def test_add_nursing_note_intervention(client: AsyncClient) -> None:
    """Test adding an intervention nursing note."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/notes",
        json={
            "note_type": "intervention",
            "content": "Administered IV ceftriaxone 2g as prescribed. Patient tolerated well.",
        },
    )
    assert response.status_code == 201
    assert response.json()["note_type"] == "intervention"


@pytest.mark.asyncio
async def test_add_nursing_note_progress(client: AsyncClient) -> None:
    """Test adding a progress nursing note."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/notes",
        json={
            "note_type": "progress",
            "content": "Fever subsiding. Appetite improving. SpO2 96% on room air.",
        },
    )
    assert response.status_code == 201
    assert response.json()["note_type"] == "progress"


@pytest.mark.asyncio
async def test_add_nursing_note_invalid_type(client: AsyncClient) -> None:
    """Test validation rejects invalid note type."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/notes",
        json={
            "note_type": "invalid_type",
            "content": "Some note",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_add_nursing_note_missing_content(client: AsyncClient) -> None:
    """Test validation rejects nursing note without content."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/notes",
        json={
            "note_type": "assessment",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_nursing_notes_empty(client: AsyncClient) -> None:
    """Test listing notes returns empty list when none exist for admission."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.get(f"/api/v1/ipd/admissions/{admission_id}/notes")
    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_list_nursing_notes_after_creation(client: AsyncClient) -> None:
    """Test listing notes returns all notes for an admission."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/notes",
        json={
            "note_type": "assessment",
            "content": "Initial assessment: vitals stable.",
        },
    )
    await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/notes",
        json={
            "note_type": "intervention",
            "content": "IV fluids started.",
        },
    )
    await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/notes",
        json={
            "note_type": "progress",
            "content": "Patient resting comfortably.",
        },
    )

    response = await client.get(f"/api/v1/ipd/admissions/{admission_id}/notes")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


# ── Discharge ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discharge_patient_normal(client: AsyncClient) -> None:
    """Test normal discharge flow."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/discharge",
        json={
            "discharge_type": "normal",
            "discharge_summary": "Patient recovered from pneumonia. Completed 5-day IV antibiotics.",
            "follow_up_instructions": "Review in OPD after 7 days. Continue oral amoxicillin 500mg TDS x 5 days.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == admission_id
    assert "discharged_at" in data or "discharge_type" in data


@pytest.mark.asyncio
async def test_discharge_patient_lama(client: AsyncClient) -> None:
    """Test discharge against medical advice (LAMA)."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/discharge",
        json={
            "discharge_type": "lama",
            "discharge_summary": "Patient insisted on leaving. Risks explained and documented.",
            "follow_up_instructions": "Urgent: Return immediately if symptoms worsen.",
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_discharge_patient_death(client: AsyncClient) -> None:
    """Test discharge type death."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/discharge",
        json={
            "discharge_type": "death",
            "discharge_summary": "Patient succumbed to complications. Time of death 14:30.",
            "follow_up_instructions": "N/A",
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_discharge_invalid_type(client: AsyncClient) -> None:
    """Test validation rejects invalid discharge type."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/discharge",
        json={
            "discharge_type": "invalid",
            "discharge_summary": "Test",
            "follow_up_instructions": "Test",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_discharge_not_found(client: AsyncClient) -> None:
    """Test 404 when discharging non-existent admission."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/ipd/admissions/{fake_id}/discharge",
        json={
            "discharge_type": "normal",
            "discharge_summary": "Test discharge",
            "follow_up_instructions": "Follow up in 7 days",
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_discharge_missing_summary(client: AsyncClient) -> None:
    """Test validation rejects discharge without required summary."""
    result = await _create_admission(client)
    admission_id = result["admission"]["id"]

    response = await client.post(
        f"/api/v1/ipd/admissions/{admission_id}/discharge",
        json={
            "discharge_type": "normal",
        },
    )
    assert response.status_code == 422


# ── Ward Board Summary After Activity ───────────────────────────────────────


@pytest.mark.asyncio
async def test_ward_board_summary_reflects_admission(client: AsyncClient) -> None:
    """Test ward board summary updates after admission."""
    await _create_admission(client)

    response = await client.get("/api/v1/ipd/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["active_admissions"] >= 1
    assert data["occupied_beds"] >= 1
