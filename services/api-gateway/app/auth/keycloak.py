import httpx
from jose import JWTError, jwt

from app.config import settings


class IdentityProviderUnreachableError(JWTError):
    """Raised when the JWKS endpoint is unreachable.

    Treated as an authentication failure (401) by callers — the client
    cannot prove identity if we cannot validate their token, so the
    correct behaviour is to deny access, not to crash with 500.
    """


# Cached JWKS (JSON Web Key Set) from Keycloak
_jwks_cache: dict[str, object] | None = None


async def get_keycloak_public_keys() -> dict[str, object]:
    """
    Fetch and cache Keycloak realm public keys for JWT verification.

    @returns JWKS dict
    @raises IdentityProviderUnreachableError: If the JWKS endpoint can't be reached
        (network error or HTTP non-2xx). Callers should translate this into a 401.
    """
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    certs_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(certs_url)
            response.raise_for_status()
            _jwks_cache = response.json()
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        raise IdentityProviderUnreachableError(
            f"Identity provider unreachable at {certs_url}"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise IdentityProviderUnreachableError(
            f"Identity provider returned {exc.response.status_code} from {certs_url}"
        ) from exc

    return _jwks_cache  # type: ignore[return-value]


async def decode_token(token: str) -> dict[str, object]:
    """
    Decode and validate a Keycloak JWT access token.

    @param token: Bearer token string
    @returns Decoded token payload
    @raises JWTError: If token is invalid or expired
    @raises IdentityProviderUnreachableError: If JWKS can't be fetched (treated as 401)
    """
    jwks = await get_keycloak_public_keys()

    # Keycloak issuer URL
    issuer = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"

    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
            issuer=issuer,
        )
    except JWTError:
        raise

    return payload  # type: ignore[return-value]


def invalidate_jwks_cache() -> None:
    """Clear the cached JWKS — call when Keycloak keys rotate."""
    global _jwks_cache
    _jwks_cache = None
