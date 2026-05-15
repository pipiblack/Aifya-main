import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool


# ── SQLite compatibility shims ───────────────────────────────────────────────
# Production runs on Postgres; tests fall back to SQLite when no real DB is
# available. Map JSONB → JSON and UUID → CHAR(36) at DDL-compile time so the
# test schema can be materialised without rewriting every model.
@compiles(JSONB, "sqlite")  # type: ignore[misc, no-untyped-call]
def _compile_jsonb_sqlite(_type: object, _compiler: object, **_kw: object) -> str:
    return "JSON"


@compiles(UUID, "sqlite")  # type: ignore[misc, no-untyped-call]
def _compile_uuid_sqlite(_type: object, _compiler: object, **_kw: object) -> str:
    return "CHAR(36)"


from app.auth.dependencies import CurrentUser, get_current_user  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

# Test DB URL: Postgres in CI (compile shims above let SQLite work locally too).
TEST_DATABASE_URL = (
    os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or "sqlite+aiosqlite:///:memory:"
)

# StaticPool keeps a single shared connection for in-memory SQLite so the
# schema seeded in setup_database is visible to test sessions.
_engine_kwargs: dict = {"echo": False}
if TEST_DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["poolclass"] = StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(TEST_DATABASE_URL, **_engine_kwargs)
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
        email="test@aifyahealth.co.ke",
        roles=["admin", "doctor"],
        name="Test User",
    )


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


@pytest_asyncio.fixture(autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Create and drop tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
