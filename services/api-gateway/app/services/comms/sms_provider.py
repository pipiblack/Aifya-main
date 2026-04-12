"""SMS provider abstraction and Africa's Talking integration."""

from __future__ import annotations

import abc
import os
from typing import Final

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Africa's Talking API endpoint
_AT_SMS_URL: Final[str] = "https://api.africastalking.com/version1/messaging"
_AT_SANDBOX_URL: Final[str] = (
    "https://api.sandbox.africastalking.com/version1/messaging"
)


class SMSProvider(abc.ABC):
    """Abstract base class for SMS delivery providers."""

    @abc.abstractmethod
    async def send_sms(self, phone: str, message: str) -> bool:
        """
        Send an SMS message to the given phone number.

        @param phone: E.164 phone number (e.g., +254712345678)
        @param message: Message body (max 160 chars for single SMS)
        @returns True if the SMS was accepted for delivery
        """


class AfricasTalkingProvider(SMSProvider):
    """
    Africa's Talking SMS provider — the most popular SMS gateway in Kenya.

    Requires environment variables:
    - AT_API_KEY: Africa's Talking API key
    - AT_USERNAME: Africa's Talking username
    - AT_SENDER_ID: Optional sender ID (alphanumeric, registered with AT)
    - AT_SANDBOX: Set to "true" for sandbox mode
    """

    def __init__(self) -> None:
        self._api_key: str = os.environ.get("AT_API_KEY", "")
        self._username: str = os.environ.get("AT_USERNAME", "")
        self._sender_id: str | None = os.environ.get("AT_SENDER_ID")
        self._sandbox: bool = os.environ.get("AT_SANDBOX", "false").lower() == "true"
        self._base_url: str = _AT_SANDBOX_URL if self._sandbox else _AT_SMS_URL

    async def send_sms(self, phone: str, message: str) -> bool:
        """
        Send SMS via Africa's Talking HTTP API.

        @param phone: E.164 phone number (e.g., +254712345678)
        @param message: SMS body text
        @returns True if the API accepted the message for delivery
        """
        if not self._api_key or not self._username:
            logger.error(
                "africas_talking_not_configured",
                hint="Set AT_API_KEY and AT_USERNAME environment variables",
            )
            return False

        headers = {
            "apiKey": self._api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        payload: dict[str, str] = {
            "username": self._username,
            "to": phone,
            "message": message,
        }
        if self._sender_id:
            payload["from"] = self._sender_id

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._base_url,
                    headers=headers,
                    data=payload,
                )

            if response.status_code == 201:
                data = response.json()
                recipients = (
                    data.get("SMSMessageData", {}).get("Recipients", [])
                )
                if recipients:
                    status_code = recipients[0].get("statusCode", 0)
                    if status_code in (100, 101):
                        logger.info(
                            "sms_sent",
                            phone=phone,
                            provider="africas_talking",
                            at_status=status_code,
                        )
                        return True

                logger.warning(
                    "sms_rejected",
                    phone=phone,
                    provider="africas_talking",
                    response=data,
                )
                return False

            logger.error(
                "sms_api_error",
                phone=phone,
                provider="africas_talking",
                status_code=response.status_code,
                body=response.text[:500],
            )
            return False

        except httpx.HTTPError as exc:
            logger.error(
                "sms_network_error",
                phone=phone,
                provider="africas_talking",
                error=str(exc),
            )
            return False


class MockSMSProvider(SMSProvider):
    """
    Mock SMS provider for development and testing.
    Logs messages via structlog instead of sending them.
    """

    async def send_sms(self, phone: str, message: str) -> bool:
        """
        Log the SMS message instead of sending it.

        @param phone: Target phone number
        @param message: Message body
        @returns Always True
        """
        logger.info(
            "mock_sms_sent",
            phone=phone,
            message=message[:100],
            provider="mock",
        )
        return True


def get_sms_provider() -> SMSProvider:
    """
    Factory: return the configured SMS provider based on environment.

    @returns SMSProvider instance (Africa's Talking or Mock)
    """
    if os.environ.get("AT_API_KEY"):
        return AfricasTalkingProvider()
    logger.warning("sms_provider_fallback_to_mock", reason="AT_API_KEY not set")
    return MockSMSProvider()
