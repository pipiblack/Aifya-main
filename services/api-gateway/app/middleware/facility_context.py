"""
Middleware to set PostgreSQL session variable for Row-Level Security.
Sets `app.current_facility_id` so RLS policies can filter rows at the DB level.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_facility_context(db: AsyncSession, facility_id: str) -> None:
    """
    Set the facility context for the current DB session.
    This enables RLS policies to filter rows by facility.

    @param db: Async database session
    @param facility_id: Facility UUID string from JWT
    """
    await db.execute(
        text("SET LOCAL app.current_facility_id = :fid"),
        {"fid": facility_id},
    )
