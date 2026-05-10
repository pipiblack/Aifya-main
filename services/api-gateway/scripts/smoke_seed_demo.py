"""
Smoke-test wrapper for `seed_demo.py` that runs against SQLite.

Production seeding still uses `python scripts/seed_demo.py` against
Postgres (after `alembic upgrade head`). This wrapper is for offline
verification — it loads the JSONB/UUID compile shims, creates the
schema from SQLAlchemy models, and then re-uses every public
function from seed_demo.py.

Usage:
    python scripts/smoke_seed_demo.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_API_GATEWAY_DIR = _THIS_DIR.parent
if str(_API_GATEWAY_DIR) not in sys.path:
    sys.path.insert(0, str(_API_GATEWAY_DIR))

# Force SQLite database URL before app.config loads.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_demo.db")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "test_secret_for_smoke_only_xxxxxxxxxxxxxxxxxxxx")

# Compile shims must be registered BEFORE any model is imported, otherwise
# SQLAlchemy will see JSONB/UUID and have no SQLite mapping.
from sqlalchemy.dialects.postgresql import JSONB, UUID  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402


@compiles(JSONB, "sqlite")  # type: ignore[misc, no-untyped-call]
def _compile_jsonb_sqlite(_type: object, _compiler: object, **_kw: object) -> str:
    return "JSON"


@compiles(UUID, "sqlite")  # type: ignore[misc, no-untyped-call]
def _compile_uuid_sqlite(_type: object, _compiler: object, **_kw: object) -> str:
    return "CHAR(36)"


# Now safe to import models / database
import app.database as database_module  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Replace engine + sessionmaker with SQLite-friendly versions for the smoke run.
engine = create_async_engine(
    os.environ["DATABASE_URL"],
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
async_session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
database_module.engine = engine
database_module.async_session = async_session_local

# Import all models so Base.metadata knows every table.
from app.models import *  # noqa: F401,F403,E402
from app.database import Base  # noqa: E402

# Import seed_demo AFTER patching, so it picks up the new async_session
import scripts.seed_demo as seed_demo  # noqa: E402

seed_demo.async_session = async_session_local  # ensure same session


async def main() -> int:
    print("Setting up SQLite schema from models...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Running seed_demo.main()...")
    return await seed_demo.main()


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc or 0)
