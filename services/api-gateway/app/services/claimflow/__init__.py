"""ClaimFlow integration package.

Provides a thin HTTP client to the external ClaimFlow service so claim
submission, status polling, approval, and rejection can all be driven
from inside Aifya without users having to switch tools.
"""

from app.services.claimflow.claimflow_client import (
    ClaimFlowClient,
    ClaimFlowError,
    ClaimFlowResponse,
    ClaimFlowUnavailableError,
    get_claimflow_client,
)

__all__ = [
    "ClaimFlowClient",
    "ClaimFlowError",
    "ClaimFlowResponse",
    "ClaimFlowUnavailableError",
    "get_claimflow_client",
]
