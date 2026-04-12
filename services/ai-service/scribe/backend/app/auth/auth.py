from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from structlog import get_logger

from app.config import get_settings
from app.models import UserRole

logger = get_logger(__name__)
settings = get_settings()

# Use bcrypt with salt rounds=12
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# OAuth2 scheme for dependency injection in FastAPI routers
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_str}/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(
    subject: str,
    role: str,
    facility_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a short-lived access token with specific scopes/roles.

    @param subject: User ID to encode as the JWT subject claim.
    @param role: User role string (e.g. 'clinician', 'superadmin').
    @param facility_id: Optional facility ID for multi-tenancy filtering.
    @param expires_delta: Optional custom expiration duration.
    @returns: Encoded JWT access token string.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    if facility_id:
        to_encode["facility_id"] = facility_id

    encoded_jwt: str = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token(subject: str) -> str:
    """Create a long-lived refresh token.

    @param subject: User ID to encode as the JWT subject claim.
    @returns: Encoded JWT refresh token string.
    """
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode: Dict[str, Any] = {
        "sub": subject,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    encoded_jwt: str = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt

async def get_current_user_token_payload(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """Validate an access token from the request and return the decoded payload.

    Only tokens with type='access' (or legacy tokens without a type claim) are
    accepted. Refresh tokens are explicitly rejected to prevent token-type
    confusion attacks.

    @param token: Bearer token extracted via OAuth2 scheme.
    @returns: Decoded JWT payload dictionary.
    @raises HTTPException: 401 if the token is invalid, expired, or is a refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: Dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # Reject refresh tokens used as access tokens
        token_type: str = payload.get("type", "access")
        if token_type != "access":
            logger.warning("wrong_token_type", expected="access", got=token_type, user_id=user_id)
            raise credentials_exception

        return payload
    except JWTError as e:
        logger.warning("invalid_token", error=str(e))
        raise credentials_exception


async def verify_refresh_token(token: str) -> Dict[str, Any]:
    """Decode and validate a refresh token, ensuring it has type='refresh'.

    @param token: Raw JWT refresh token string.
    @returns: Decoded JWT payload dictionary.
    @raises HTTPException: 401 if the token is invalid, expired, or not a refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: Dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        token_type: str = payload.get("type", "")
        if token_type != "refresh":
            logger.warning("wrong_token_type", expected="refresh", got=token_type, user_id=user_id)
            raise credentials_exception

        return payload
    except JWTError as e:
        logger.warning("invalid_refresh_token", error=str(e))
        raise credentials_exception

class RoleChecker:
    """
    Dependency injection class to enforce proper Role Based Access Control (RBAC) matrix.
    Usage: Depends(RoleChecker([UserRole.CLINICIAN, UserRole.SUPERADMIN]))
    """
    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    async def __call__(self, payload: Dict[str, Any] = Depends(get_current_user_token_payload)):
        role_str = payload.get("role")
        if not role_str:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role claim missing in token")
            
        try:
            user_role = UserRole(role_str)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role in token")

        if user_role not in self.allowed_roles:
            logger.warning("auth_forbidden", user_id=payload.get("sub"), attempted_role=user_role, required_roles=[r.value for r in self.allowed_roles])
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operation not permitted")
            
        return payload
