# ruff: noqa: E402
import os
import uuid
from collections.abc import AsyncGenerator

os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["AIFYA_TESTING"] = "true"
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://aifya_user:change_me_in_production"
    "@127.0.0.1:55432/aifya_test"
)
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    DEFAULT_TEST_DATABASE_URL,
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.facility import Facility
from app.models.staff import Staff

engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

FACILITY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Test DB session override."""
    async with test_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def override_get_current_user() -> CurrentUser:
    """Mock auth for tests — returns a test user."""
    return CurrentUser(
        user_id=USER_ID,
        facility_id=FACILITY_ID,
        email="test@aifya.health",
        roles=["admin", "doctor"],
        name="Test User",
    )


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


@pytest_asyncio.fixture(autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Create and drop tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with test_session() as session:
        session.add(
            Facility(
                id=FACILITY_ID,
                name="Test Facility",
                code="TEST",
                facility_type="hospital",
            )
        )
        session.add(
            Staff(
                id=USER_ID,
                facility_id=FACILITY_ID,
                keycloak_user_id=USER_ID,
                employee_number="DOC-001",
                first_name="Test",
                last_name="Doctor",
                role="doctor",
                email="test@aifya.health",
                created_by=USER_ID,
                updated_by=USER_ID,
            )
        )
        await session.commit()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_patient_data() -> dict:
    """Sample patient registration payload."""
    return {
        "first_name": "Wanjiku",
        "middle_name": "Njeri",
        "last_name": "Kamau",
        "date_of_birth": "1990-05-15",
        "gender": "female",
        "national_id": "29384756",
        "phone_number": "0712345678",
        "county": "Nairobi",
        "sub_county": "Westlands",
        "ward": "Parklands",
        "next_of_kin_name": "John Kamau",
        "next_of_kin_phone": "0723456789",
        "next_of_kin_relationship": "Spouse",
        "sha_number": "SHA-1234567",
        "blood_group": "O+",
        "allergies": ["Penicillin"],
        "chronic_conditions": ["Hypertension"],
    }
