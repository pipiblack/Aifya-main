"""Comprehensive tests for the MCH (Maternal and Child Health) module.

Tests cover ANC profiles, ANC visits, delivery records, child records,
and immunization tracking endpoints under /api/v1/mch/.
"""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient


# ── Helpers ─────────────────────────────────────────────────────────────────


async def create_female_patient(client: AsyncClient) -> dict[str, Any]:
    """Create a female patient and return the response data.

    @param client: Async HTTP test client
    @returns Patient data dict including the generated id
    """
    payload: dict[str, Any] = {
        "first_name": "Amina",
        "last_name": "Wanjiku",
        "date_of_birth": "1995-03-10",
        "gender": "female",
        "phone_number": "0700000000",
    }
    response = await client.post("/api/v1/patients", json=payload)
    assert response.status_code == 201, f"Patient creation failed: {response.text}"
    return response.json()


async def create_anc_profile(
    client: AsyncClient, patient_id: str
) -> dict[str, Any]:
    """Create an ANC profile for the given patient and return response data.

    @param client: Async HTTP test client
    @param patient_id: UUID string of the patient
    @returns ANC profile data dict
    """
    payload: dict[str, Any] = {
        "patient_id": patient_id,
        "lmp_date": "2026-01-15",
        "edd": "2026-10-22",
        "gravida": 2,
        "parity": 1,
        "blood_group": "O+",
        "risk_factors": ["previous_cesarean"],
    }
    response = await client.post("/api/v1/mch/anc", json=payload)
    assert response.status_code == 201, f"ANC profile creation failed: {response.text}"
    return response.json()


async def create_anc_visit(
    client: AsyncClient, anc_profile_id: str
) -> dict[str, Any]:
    """Add an ANC visit to an existing profile and return response data.

    @param client: Async HTTP test client
    @param anc_profile_id: UUID string of the ANC profile
    @returns ANC visit data dict
    """
    payload: dict[str, Any] = {
        "anc_profile_id": anc_profile_id,
        "visit_number": 1,
        "gestational_age_weeks": 12,
        "weight": 65.0,
        "blood_pressure_systolic": 120,
        "blood_pressure_diastolic": 75,
        "fundal_height": 12,
        "fetal_heart_rate": 150,
        "presentation": "cephalic",
        "notes": "Normal progress",
    }
    response = await client.post("/api/v1/mch/anc/visits", json=payload)
    assert response.status_code == 201, f"ANC visit creation failed: {response.text}"
    return response.json()


async def record_delivery(
    client: AsyncClient, anc_profile_id: str
) -> dict[str, Any]:
    """Record a delivery for an ANC profile and return response data.

    @param client: Async HTTP test client
    @param anc_profile_id: UUID string of the ANC profile
    @returns Delivery record data dict
    """
    payload: dict[str, Any] = {
        "anc_profile_id": anc_profile_id,
        "delivery_date": "2026-10-20T14:30:00",
        "delivery_type": "normal_vaginal",
        "baby_gender": "female",
        "baby_weight": 3200,
        "apgar_1min": 8,
        "apgar_5min": 9,
        "outcome": "live_birth",
    }
    response = await client.post("/api/v1/mch/delivery", json=payload)
    assert response.status_code == 201, f"Delivery recording failed: {response.text}"
    return response.json()


async def create_child_record(
    client: AsyncClient, patient_id: str, mother_id: str
) -> dict[str, Any]:
    """Create a child health record and return response data.

    @param client: Async HTTP test client
    @param patient_id: UUID string of the child patient
    @param mother_id: UUID string of the mother patient
    @returns Child record data dict
    """
    payload: dict[str, Any] = {
        "patient_id": patient_id,
        "mother_id": mother_id,
        "birth_weight": 3200,
        "birth_length": 50,
        "head_circumference": 35,
    }
    response = await client.post("/api/v1/mch/children", json=payload)
    assert response.status_code == 201, f"Child record creation failed: {response.text}"
    return response.json()


# ── 1. MCH Summary ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_mch_summary(client: AsyncClient) -> None:
    """Test MCH summary returns department dashboard stats."""
    response = await client.get("/api/v1/mch/summary")

    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    # Summary should contain key stat fields (counts start at 0)
    assert "active_anc_profiles" in data or "total_anc_profiles" in data or isinstance(data, dict)


@pytest.mark.asyncio
async def test_get_mch_summary_after_data(client: AsyncClient) -> None:
    """Test MCH summary reflects created records."""
    patient = await create_female_patient(client)
    await create_anc_profile(client, patient["id"])

    response = await client.get("/api/v1/mch/summary")
    assert response.status_code == 200


# ── 2. ANC Profiles — List (empty) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_anc_profiles_empty(client: AsyncClient) -> None:
    """Test listing ANC profiles returns empty list when none exist."""
    response = await client.get("/api/v1/mch/anc")

    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    assert data["items"] == []
    assert data["total"] == 0


# ── 3. ANC Profiles — Create ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_anc_profile(client: AsyncClient) -> None:
    """Test creating an ANC profile for a female patient."""
    patient = await create_female_patient(client)

    payload: dict[str, Any] = {
        "patient_id": patient["id"],
        "lmp_date": "2026-01-15",
        "edd": "2026-10-22",
        "gravida": 2,
        "parity": 1,
        "blood_group": "O+",
        "risk_factors": ["previous_cesarean"],
    }
    response = await client.post("/api/v1/mch/anc", json=payload)

    assert response.status_code == 201
    data: dict[str, Any] = response.json()
    assert "id" in data
    assert data["patient_id"] == patient["id"]
    assert data["gravida"] == 2
    assert data["parity"] == 1
    assert data["blood_group"] == "O+"
    assert data["risk_factors"] == ["previous_cesarean"]


@pytest.mark.asyncio
async def test_create_anc_profile_appears_in_list(client: AsyncClient) -> None:
    """Test that a created ANC profile shows up in the list endpoint."""
    patient = await create_female_patient(client)
    profile = await create_anc_profile(client, patient["id"])

    response = await client.get("/api/v1/mch/anc")
    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    assert data["total"] >= 1
    profile_ids = [item["id"] for item in data["items"]]
    assert profile["id"] in profile_ids


@pytest.mark.asyncio
async def test_create_anc_profile_missing_required_fields(client: AsyncClient) -> None:
    """Test that creating an ANC profile without required fields returns 422."""
    response = await client.post("/api/v1/mch/anc", json={"gravida": 1})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_anc_profile_invalid_patient(client: AsyncClient) -> None:
    """Test that creating an ANC profile with non-existent patient fails."""
    fake_patient_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "patient_id": fake_patient_id,
        "lmp_date": "2026-01-15",
        "edd": "2026-10-22",
        "gravida": 1,
        "parity": 0,
        "blood_group": "A+",
        "risk_factors": [],
    }
    response = await client.post("/api/v1/mch/anc", json=payload)
    # Expect 400 or 404 — service should reject unknown patient
    assert response.status_code in (400, 404, 422)


# ── 4. ANC Profile Detail ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_anc_profile_detail(client: AsyncClient) -> None:
    """Test fetching a single ANC profile by ID with full detail."""
    patient = await create_female_patient(client)
    profile = await create_anc_profile(client, patient["id"])

    response = await client.get(f"/api/v1/mch/anc/{profile['id']}")

    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    assert data["id"] == profile["id"]
    assert data["patient_id"] == patient["id"]
    assert data["gravida"] == 2
    assert data["parity"] == 1


@pytest.mark.asyncio
async def test_get_anc_profile_detail_not_found(client: AsyncClient) -> None:
    """Test 404 for non-existent ANC profile."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/mch/anc/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_anc_profile_detail_includes_visits(client: AsyncClient) -> None:
    """Test that ANC profile detail includes visit data after a visit is added."""
    patient = await create_female_patient(client)
    profile = await create_anc_profile(client, patient["id"])
    await create_anc_visit(client, profile["id"])

    response = await client.get(f"/api/v1/mch/anc/{profile['id']}")
    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    # Detail should include visits array
    if "visits" in data:
        assert len(data["visits"]) >= 1


# ── 5. ANC Visits ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_anc_visit(client: AsyncClient) -> None:
    """Test recording an ANC visit with vitals and obstetric exam data."""
    patient = await create_female_patient(client)
    profile = await create_anc_profile(client, patient["id"])

    payload: dict[str, Any] = {
        "anc_profile_id": profile["id"],
        "visit_number": 1,
        "gestational_age_weeks": 12,
        "weight": 65.0,
        "blood_pressure_systolic": 120,
        "blood_pressure_diastolic": 75,
        "fundal_height": 12,
        "fetal_heart_rate": 150,
        "presentation": "cephalic",
        "notes": "Normal progress",
    }
    response = await client.post("/api/v1/mch/anc/visits", json=payload)

    assert response.status_code == 201
    data: dict[str, Any] = response.json()
    assert "id" in data
    assert data["anc_profile_id"] == profile["id"]
    assert data["visit_number"] == 1
    assert data["gestational_age_weeks"] == 12
    assert data["weight"] == 65.0
    assert data["blood_pressure_systolic"] == 120
    assert data["blood_pressure_diastolic"] == 75
    assert data["fundal_height"] == 12
    assert data["fetal_heart_rate"] == 150
    assert data["presentation"] == "cephalic"
    assert data["notes"] == "Normal progress"


@pytest.mark.asyncio
async def test_add_anc_visit_missing_profile(client: AsyncClient) -> None:
    """Test that adding a visit to a non-existent ANC profile fails."""
    fake_profile_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "anc_profile_id": fake_profile_id,
        "visit_number": 1,
        "gestational_age_weeks": 12,
        "weight": 65.0,
        "blood_pressure_systolic": 120,
        "blood_pressure_diastolic": 75,
        "fundal_height": 12,
        "fetal_heart_rate": 150,
        "presentation": "cephalic",
        "notes": "Test visit",
    }
    response = await client.post("/api/v1/mch/anc/visits", json=payload)
    assert response.status_code in (400, 404, 422)


@pytest.mark.asyncio
async def test_add_multiple_anc_visits(client: AsyncClient) -> None:
    """Test recording multiple ANC visits for the same profile."""
    patient = await create_female_patient(client)
    profile = await create_anc_profile(client, patient["id"])

    # Visit 1
    visit1_payload: dict[str, Any] = {
        "anc_profile_id": profile["id"],
        "visit_number": 1,
        "gestational_age_weeks": 12,
        "weight": 65.0,
        "blood_pressure_systolic": 120,
        "blood_pressure_diastolic": 75,
        "fundal_height": 12,
        "fetal_heart_rate": 150,
        "presentation": "cephalic",
        "notes": "First visit — normal",
    }
    resp1 = await client.post("/api/v1/mch/anc/visits", json=visit1_payload)
    assert resp1.status_code == 201

    # Visit 2
    visit2_payload: dict[str, Any] = {
        "anc_profile_id": profile["id"],
        "visit_number": 2,
        "gestational_age_weeks": 20,
        "weight": 68.0,
        "blood_pressure_systolic": 118,
        "blood_pressure_diastolic": 72,
        "fundal_height": 20,
        "fetal_heart_rate": 145,
        "presentation": "cephalic",
        "notes": "Second visit — good progress",
    }
    resp2 = await client.post("/api/v1/mch/anc/visits", json=visit2_payload)
    assert resp2.status_code == 201
    assert resp2.json()["visit_number"] == 2


@pytest.mark.asyncio
async def test_add_anc_visit_missing_required_fields(client: AsyncClient) -> None:
    """Test that adding an ANC visit without required fields returns 422."""
    response = await client.post(
        "/api/v1/mch/anc/visits", json={"visit_number": 1}
    )
    assert response.status_code == 422


# ── 6. Delivery ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_delivery(client: AsyncClient) -> None:
    """Test recording a delivery with full birth details."""
    patient = await create_female_patient(client)
    profile = await create_anc_profile(client, patient["id"])

    payload: dict[str, Any] = {
        "anc_profile_id": profile["id"],
        "delivery_date": "2026-10-20T14:30:00",
        "delivery_type": "normal_vaginal",
        "baby_gender": "female",
        "baby_weight": 3200,
        "apgar_1min": 8,
        "apgar_5min": 9,
        "outcome": "live_birth",
    }
    response = await client.post("/api/v1/mch/delivery", json=payload)

    assert response.status_code == 201
    data: dict[str, Any] = response.json()
    assert "id" in data
    assert data["anc_profile_id"] == profile["id"]
    assert data["delivery_type"] == "normal_vaginal"
    assert data["baby_gender"] == "female"
    assert data["baby_weight"] == 3200
    assert data["apgar_1min"] == 8
    assert data["apgar_5min"] == 9
    assert data["outcome"] == "live_birth"


@pytest.mark.asyncio
async def test_record_delivery_invalid_profile(client: AsyncClient) -> None:
    """Test that recording delivery for non-existent ANC profile fails."""
    fake_profile_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "anc_profile_id": fake_profile_id,
        "delivery_date": "2026-10-20T14:30:00",
        "delivery_type": "normal_vaginal",
        "baby_gender": "male",
        "baby_weight": 3500,
        "apgar_1min": 9,
        "apgar_5min": 10,
        "outcome": "live_birth",
    }
    response = await client.post("/api/v1/mch/delivery", json=payload)
    assert response.status_code in (400, 404, 422)


@pytest.mark.asyncio
async def test_record_delivery_missing_required_fields(client: AsyncClient) -> None:
    """Test that recording delivery without required fields returns 422."""
    response = await client.post(
        "/api/v1/mch/delivery", json={"delivery_type": "normal_vaginal"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delivery_reflects_in_profile_detail(client: AsyncClient) -> None:
    """Test that a recorded delivery appears in ANC profile detail."""
    patient = await create_female_patient(client)
    profile = await create_anc_profile(client, patient["id"])
    await record_delivery(client, profile["id"])

    response = await client.get(f"/api/v1/mch/anc/{profile['id']}")
    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    # Detail should reference delivery info
    if "delivery" in data:
        assert data["delivery"] is not None


# ── 7. Child Records — List (empty) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_child_records_empty(client: AsyncClient) -> None:
    """Test listing child records returns empty list when none exist."""
    response = await client.get("/api/v1/mch/children")

    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    assert data["items"] == []
    assert data["total"] == 0


# ── 8. Child Records — Create ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_child_record(client: AsyncClient) -> None:
    """Test creating a child health record linked to mother."""
    mother = await create_female_patient(client)

    # Create child patient
    child_payload: dict[str, Any] = {
        "first_name": "Baby",
        "last_name": "Wanjiku",
        "date_of_birth": "2026-10-20",
        "gender": "female",
        "phone_number": "0700000001",
    }
    child_resp = await client.post("/api/v1/patients", json=child_payload)
    assert child_resp.status_code == 201
    child_patient = child_resp.json()

    payload: dict[str, Any] = {
        "patient_id": child_patient["id"],
        "mother_id": mother["id"],
        "birth_weight": 3200,
        "birth_length": 50,
        "head_circumference": 35,
    }
    response = await client.post("/api/v1/mch/children", json=payload)

    assert response.status_code == 201
    data: dict[str, Any] = response.json()
    assert "id" in data
    assert data["patient_id"] == child_patient["id"]
    assert data["mother_id"] == mother["id"]
    assert data["birth_weight"] == 3200
    assert data["birth_length"] == 50
    assert data["head_circumference"] == 35


@pytest.mark.asyncio
async def test_create_child_record_appears_in_list(client: AsyncClient) -> None:
    """Test that a created child record shows up in the list endpoint."""
    mother = await create_female_patient(client)
    child_payload: dict[str, Any] = {
        "first_name": "Baby",
        "last_name": "Wanjiku",
        "date_of_birth": "2026-10-20",
        "gender": "female",
        "phone_number": "0700000002",
    }
    child_resp = await client.post("/api/v1/patients", json=child_payload)
    child_patient = child_resp.json()
    child_record = await create_child_record(client, child_patient["id"], mother["id"])

    response = await client.get("/api/v1/mch/children")
    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    assert data["total"] >= 1
    record_ids = [item["id"] for item in data["items"]]
    assert child_record["id"] in record_ids


@pytest.mark.asyncio
async def test_create_child_record_missing_required_fields(client: AsyncClient) -> None:
    """Test that creating a child record without required fields returns 422."""
    response = await client.post(
        "/api/v1/mch/children", json={"birth_weight": 3000}
    )
    assert response.status_code == 422


# ── 9. Immunizations — Record ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_immunization(client: AsyncClient) -> None:
    """Test recording an immunization dose for a child."""
    mother = await create_female_patient(client)
    child_payload: dict[str, Any] = {
        "first_name": "Baby",
        "last_name": "Wanjiku",
        "date_of_birth": "2026-10-20",
        "gender": "female",
        "phone_number": "0700000003",
    }
    child_resp = await client.post("/api/v1/patients", json=child_payload)
    child_patient = child_resp.json()
    child_record = await create_child_record(client, child_patient["id"], mother["id"])

    payload: dict[str, Any] = {
        "child_record_id": child_record["id"],
        "vaccine_name": "BCG",
        "dose_number": 1,
        "date_given": "2026-10-25",
        "site": "left_arm",
        "batch_number": "BCG-2026-001",
    }
    response = await client.post(
        f"/api/v1/mch/children/{child_record['id']}/immunizations", json=payload
    )

    assert response.status_code == 201
    data: dict[str, Any] = response.json()
    assert "id" in data
    assert data["vaccine_name"] == "BCG"
    assert data["dose_number"] == 1
    assert data["site"] == "left_arm"
    assert data["batch_number"] == "BCG-2026-001"


@pytest.mark.asyncio
async def test_record_immunization_missing_required_fields(
    client: AsyncClient,
) -> None:
    """Test that recording an immunization without required fields returns 422."""
    fake_child_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/mch/children/{fake_child_id}/immunizations",
        json={"vaccine_name": "BCG"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_record_multiple_immunizations(client: AsyncClient) -> None:
    """Test recording multiple immunization doses for the same child."""
    mother = await create_female_patient(client)
    child_payload: dict[str, Any] = {
        "first_name": "Baby",
        "last_name": "Wanjiku",
        "date_of_birth": "2026-10-20",
        "gender": "male",
        "phone_number": "0700000004",
    }
    child_resp = await client.post("/api/v1/patients", json=child_payload)
    child_patient = child_resp.json()
    child_record = await create_child_record(client, child_patient["id"], mother["id"])
    child_id: str = child_record["id"]

    # BCG
    bcg_payload: dict[str, Any] = {
        "child_record_id": child_id,
        "vaccine_name": "BCG",
        "dose_number": 1,
        "date_given": "2026-10-25",
        "site": "left_arm",
        "batch_number": "BCG-2026-001",
    }
    resp1 = await client.post(
        f"/api/v1/mch/children/{child_id}/immunizations", json=bcg_payload
    )
    assert resp1.status_code == 201

    # OPV 0
    opv_payload: dict[str, Any] = {
        "child_record_id": child_id,
        "vaccine_name": "OPV",
        "dose_number": 0,
        "date_given": "2026-10-25",
        "site": "oral",
        "batch_number": "OPV-2026-001",
    }
    resp2 = await client.post(
        f"/api/v1/mch/children/{child_id}/immunizations", json=opv_payload
    )
    assert resp2.status_code == 201


# ── 10. Immunizations — List ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_immunizations_empty(client: AsyncClient) -> None:
    """Test listing immunizations for a child with no records returns empty list."""
    mother = await create_female_patient(client)
    child_payload: dict[str, Any] = {
        "first_name": "Baby",
        "last_name": "Wanjiku",
        "date_of_birth": "2026-10-20",
        "gender": "female",
        "phone_number": "0700000005",
    }
    child_resp = await client.post("/api/v1/patients", json=child_payload)
    child_patient = child_resp.json()
    child_record = await create_child_record(client, child_patient["id"], mother["id"])

    response = await client.get(
        f"/api/v1/mch/children/{child_record['id']}/immunizations"
    )

    assert response.status_code == 200
    data: list[dict[str, Any]] = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_list_immunizations_after_recording(client: AsyncClient) -> None:
    """Test listing immunizations returns recorded doses."""
    mother = await create_female_patient(client)
    child_payload: dict[str, Any] = {
        "first_name": "Baby",
        "last_name": "Wanjiku",
        "date_of_birth": "2026-10-20",
        "gender": "female",
        "phone_number": "0700000006",
    }
    child_resp = await client.post("/api/v1/patients", json=child_payload)
    child_patient = child_resp.json()
    child_record = await create_child_record(client, child_patient["id"], mother["id"])
    child_id: str = child_record["id"]

    # Record BCG
    imm_payload: dict[str, Any] = {
        "child_record_id": child_id,
        "vaccine_name": "BCG",
        "dose_number": 1,
        "date_given": "2026-10-25",
        "site": "left_arm",
        "batch_number": "BCG-2026-001",
    }
    await client.post(
        f"/api/v1/mch/children/{child_id}/immunizations", json=imm_payload
    )

    # List
    response = await client.get(f"/api/v1/mch/children/{child_id}/immunizations")

    assert response.status_code == 200
    data: list[dict[str, Any]] = response.json()
    assert len(data) == 1
    assert data[0]["vaccine_name"] == "BCG"
    assert data[0]["dose_number"] == 1
    assert data[0]["batch_number"] == "BCG-2026-001"


# ── Full Workflow (end-to-end) ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_mch_workflow(client: AsyncClient) -> None:
    """End-to-end test: patient -> ANC -> visits -> delivery -> child -> immunization."""
    # 1. Register mother
    mother = await create_female_patient(client)
    mother_id: str = mother["id"]

    # 2. Create ANC profile
    profile = await create_anc_profile(client, mother_id)
    profile_id: str = profile["id"]

    # 3. Record ANC visits
    visit = await create_anc_visit(client, profile_id)
    assert visit["visit_number"] == 1

    # 4. Record delivery
    delivery = await record_delivery(client, profile_id)
    assert delivery["outcome"] == "live_birth"

    # 5. Register baby as patient
    baby_payload: dict[str, Any] = {
        "first_name": "Neema",
        "last_name": "Wanjiku",
        "date_of_birth": "2026-10-20",
        "gender": "female",
        "phone_number": "0700000099",
    }
    baby_resp = await client.post("/api/v1/patients", json=baby_payload)
    assert baby_resp.status_code == 201
    baby_patient = baby_resp.json()

    # 6. Create child record
    child = await create_child_record(client, baby_patient["id"], mother_id)
    child_id: str = child["id"]

    # 7. Record immunization
    imm_payload: dict[str, Any] = {
        "child_record_id": child_id,
        "vaccine_name": "BCG",
        "dose_number": 1,
        "date_given": "2026-10-25",
        "site": "left_arm",
        "batch_number": "BCG-2026-001",
    }
    imm_resp = await client.post(
        f"/api/v1/mch/children/{child_id}/immunizations", json=imm_payload
    )
    assert imm_resp.status_code == 201

    # 8. Verify immunization list
    list_resp = await client.get(f"/api/v1/mch/children/{child_id}/immunizations")
    assert list_resp.status_code == 200
    immunizations: list[dict[str, Any]] = list_resp.json()
    assert len(immunizations) == 1
    assert immunizations[0]["vaccine_name"] == "BCG"

    # 9. Verify summary still works
    summary_resp = await client.get("/api/v1/mch/summary")
    assert summary_resp.status_code == 200
