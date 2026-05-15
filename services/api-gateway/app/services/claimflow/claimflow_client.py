"""HTTP client for the ClaimFlow service.

ClaimFlow is the SHA-claims automation engine that runs in its own container
(`claimflow-api`, default port 8080). All communication is JSON over HTTP.

The client is intentionally defensive: any network or upstream failure is
translated to ``ClaimFlowUnavailableError`` so callers can surface a clear
user-friendly message instead of leaking 500s.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class ClaimFlowError(Exception):
    """Generic ClaimFlow domain error (validation, business logic, etc.)."""


class ClaimFlowUnavailableError(ClaimFlowError):
    """Raised when ClaimFlow service is unreachable or returns 5xx.

    Surface as a user-friendly 503 in the API layer.
    """


@dataclass(frozen=True)
class ClaimFlowResponse:
    """Normalised response from ClaimFlow.

    @param ok: True if the upstream request succeeded
    @param status_code: HTTP status from ClaimFlow
    @param data: JSON body (best-effort parsed; empty dict on parse failure)
    """

    ok: bool
    status_code: int
    data: dict[str, Any]


class ClaimFlowClient:
    """Thin async HTTP client for the ClaimFlow service."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.claimflow_api_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.claimflow_api_key
        self.timeout_seconds = float(timeout_seconds or settings.claimflow_timeout_seconds)

    # ── Internals ─────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Aifya/0.1 ClaimFlowClient",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> ClaimFlowResponse:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(
                    method=method, url=url, json=json, headers=self._headers()
                )
        except (httpx.TimeoutException, httpx.ConnectError, httpx.TransportError) as exc:
            logger.warning("ClaimFlow %s %s failed: %s", method, path, exc)
            raise ClaimFlowUnavailableError(
                "ClaimFlow service is unreachable. Please verify the service is "
                "running and try again."
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("ClaimFlow %s %s HTTP error: %s", method, path, exc)
            raise ClaimFlowUnavailableError(
                "Could not contact ClaimFlow service."
            ) from exc

        body: dict[str, Any] = {}
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                body = parsed
            else:
                body = {"result": parsed}
        except ValueError:
            body = {"raw": response.text}

        if response.status_code >= 500:
            logger.warning(
                "ClaimFlow %s %s returned %s: %s", method, path, response.status_code, body
            )
            raise ClaimFlowUnavailableError(
                "ClaimFlow service returned an internal error. Please retry later."
            )

        return ClaimFlowResponse(
            ok=200 <= response.status_code < 300,
            status_code=response.status_code,
            data=body,
        )

    # ── Public API ────────────────────────────────────────────────────────

    async def submit_claim(self, claim_data: dict[str, Any]) -> ClaimFlowResponse:
        """Submit a claim payload to ClaimFlow.

        @param claim_data: Aifya-side claim payload (claim_number, patient,
                           scheme, items, diagnosis codes, etc.)
        @returns Normalised response. ``data`` typically includes ``external_id``
                 and ``status`` on success.
        """
        return await self._request("POST", "/claims", json=claim_data)

    async def get_claim_status(self, external_id: str) -> ClaimFlowResponse:
        """Pull the latest status for a previously submitted claim."""
        return await self._request("GET", f"/claims/{external_id}")

    async def approve_claim(self, external_id: str) -> ClaimFlowResponse:
        """Approve a claim in ClaimFlow."""
        return await self._request("POST", f"/claims/{external_id}/approve")

    async def reject_claim(
        self, external_id: str, reason: str
    ) -> ClaimFlowResponse:
        """Reject a claim in ClaimFlow with a reason."""
        return await self._request(
            "POST", f"/claims/{external_id}/reject", json={"reason": reason}
        )


def get_claimflow_client() -> ClaimFlowClient:
    """FastAPI dependency factory — returns a fresh client per request."""
    return ClaimFlowClient()


__all__ = [
    "ClaimFlowClient",
    "ClaimFlowError",
    "ClaimFlowResponse",
    "ClaimFlowUnavailableError",
    "get_claimflow_client",
]
