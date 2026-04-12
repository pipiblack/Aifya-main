import httpx
from jose import JWTError, jwt

from app.config import settings

# Cached JWKS (JSON Web Key Set) from Keycloak
_jwks_cache: dict[str, object] | None = None


async def get_keycloak_public_keys() -> dict[str, object]:
    """
    Fetch and cache Keycloak realm public keys for JWT verification.

    @returns JWKS dict
    """
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    certs_url = (
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        "/protocol/openid-connect/certs"
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(certs_url)
        response.raise_for_status()
        _jwks_cache = response.json()

    return _jwks_cache  # type: ignore[return-value]


async def decode_token(token: str) -> dict[str, object]:
    """
    Decode and validate a Keycloak JWT access token.

    @param token: Bearer token string
    @returns Decoded token payload
    @raises JWTError: If token is invalid or expired
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
