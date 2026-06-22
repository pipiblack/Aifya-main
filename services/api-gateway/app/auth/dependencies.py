import uuid
from dataclasses import dataclass

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.keycloak import decode_token
from app.config import settings

security = HTTPBearer(auto_error=False)
LOCAL_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
LOCAL_FACILITY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class CurrentUser:
    """
    Authenticated user extracted from Keycloak JWT.
    Contains facility_id for multi-tenant query scoping.
    """

    user_id: uuid.UUID
    facility_id: uuid.UUID
    email: str
    roles: list[str]
    name: str


def _local_demo_user() -> CurrentUser:
    """Return a stable local user for Docker pre-deploy runs."""
    return CurrentUser(
        user_id=LOCAL_USER_ID,
        facility_id=LOCAL_FACILITY_ID,
        email="admin@aifya.local",
        roles=["system_admin", "facility_admin", "doctor", "nurse"],
        name="Aifya Local Admin",
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """
    FastAPI dependency: extract and validate the current user from JWT.
    Reads token from Authorization header first, falls back to httpOnly cookie.
    Every query MUST use the returned facility_id — no cross-facility data leaks.

    @param request: Incoming HTTP request (for cookie access)
    @param credentials: Bearer token from Authorization header
    @returns CurrentUser with user_id, facility_id, roles
    @raises HTTPException 401: If token is missing or invalid
    """
    # Try Authorization header first, then httpOnly cookie
    token: str | None = None
    if credentials is not None:
        token = credentials.credentials
    else:
        token = request.cookies.get("access_token")

    if token is None:
        if settings.local_auth_bypass:
            return _local_demo_user()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = await decode_token(token)
    except JWTError:
        if settings.local_auth_bypass:
            return _local_demo_user()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract Keycloak claims
    user_id_str = payload.get("sub")
    if not user_id_str or not isinstance(user_id_str, str):
        if settings.local_auth_bypass:
            return _local_demo_user()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    # facility_id is a custom claim added to Keycloak tokens via protocol mapper
    facility_id_str = payload.get("facility_id")
    if not facility_id_str or not isinstance(facility_id_str, str):
        if settings.local_auth_bypass:
            return _local_demo_user()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing facility_id claim",
        )

    # Extract realm roles
    realm_access = payload.get("realm_access", {})
    roles: list[str] = []
    if isinstance(realm_access, dict):
        roles = realm_access.get("roles", [])  # type: ignore[assignment]

    email = str(payload.get("email", ""))
    name = str(payload.get("name", payload.get("preferred_username", "")))

    return CurrentUser(
        user_id=uuid.UUID(str(user_id_str)),
        facility_id=uuid.UUID(str(facility_id_str)),
        email=email,
        roles=roles,
        name=name,
    )


def require_roles(*required_roles: str):
    """
    Factory for role-based access control dependency.
    Usage: Depends(require_roles("doctor", "admin"))

    @param required_roles: One or more role names — user must have at least one
    @returns Dependency function that validates roles
    """

    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        """
        Check that the current user has at least one of the required roles.

        @param current_user: Authenticated user
        @returns CurrentUser if authorized
        @raises HTTPException 403: If user lacks required roles
        """
        if not any(role in current_user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(required_roles)}",
            )
        return current_user

    return role_checker
