"""WhatsApp provider abstraction and Meta Cloud API integration."""

from __future__ import annotations

import abc
import os
from typing import Any, Final

import httpx
import structlog

logger = structlog.get_logger(__name__)

_WA_API_VERSION: Final[str] = "v20.0"


class WhatsAppProvider(abc.ABC):
    """Abstract base class for WhatsApp message delivery."""

    @abc.abstractmethod
    async def send_message(
        self,
        phone: str,
        message: str,
        template_name: str | None = None,
    ) -> bool:
        """
        Send a WhatsApp message to the given phone number.

        @param phone: E.164 phone number (e.g., +254712345678)
        @param message: Message text (used for free-form or as template fallback)
        @param template_name: Optional WhatsApp-approved template name
        @returns True if the message was accepted for delivery
        """


class WhatsAppCloudProvider(WhatsAppProvider):
    """
    Meta WhatsApp Business Cloud API provider.

    Requires environment variables:
    - WA_ACCESS_TOKEN: Meta Graph API access token
    - WA_PHONE_NUMBER_ID: WhatsApp Business phone number ID
    - WA_BUSINESS_ACCOUNT_ID: WhatsApp Business Account ID (optional)
    """

    def __init__(self) -> None:
        self._access_token: str = os.environ.get("WA_ACCESS_TOKEN", "")
        self._phone_number_id: str = os.environ.get("WA_PHONE_NUMBER_ID", "")
        self._base_url: str = (
            f"https://graph.facebook.com/{_WA_API_VERSION}"
            f"/{self._phone_number_id}/messages"
        )

    async def send_message(
        self,
        phone: str,
        message: str,
        template_name: str | None = None,
    ) -> bool:
        """
        Send a WhatsApp message via the Meta Cloud API.

        If template_name is provided, sends a template message; otherwise
        sends a free-form text message (requires 24-hour conversation window).

        @param phone: E.164 phone number
        @param message: Text message body
        @param template_name: Optional approved template name
        @returns True if the API accepted the message
        """
        if not self._access_token or not self._phone_number_id:
            logger.error(
                "whatsapp_not_configured",
                hint="Set WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID",
            )
            return False

        # Strip the leading '+' — WhatsApp Cloud API expects digits only
        clean_phone = phone.lstrip("+")

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any]
        if template_name:
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_phone,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": "en"},
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_phone,
                "type": "text",
                "text": {"body": message},
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._base_url,
                    headers=headers,
                    json=payload,
                )

            if response.status_code in (200, 201):
                data = response.json()
                wa_message_id = (
                    data.get("messages", [{}])[0].get("id")
                    if data.get("messages")
                    else None
                )
                logger.info(
                    "whatsapp_sent",
                    phone=phone,
                    provider="meta_cloud",
                    wa_message_id=wa_message_id,
                    template=template_name,
                )
                return True

            logger.error(
                "whatsapp_api_error",
                phone=phone,
                provider="meta_cloud",
                status_code=response.status_code,
                body=response.text[:500],
            )
            return False

        except httpx.HTTPError as exc:
            logger.error(
                "whatsapp_network_error",
                phone=phone,
                provider="meta_cloud",
                error=str(exc),
            )
            return False


class MockWhatsAppProvider(WhatsAppProvider):
    """
    Mock WhatsApp provider for development and testing.
    Logs messages via structlog instead of sending them.
    """

    async def send_message(
        self,
        phone: str,
        message: str,
        template_name: str | None = None,
    ) -> bool:
        """
        Log the WhatsApp message instead of sending it.

        @param phone: Target phone number
        @param message: Message body
        @param template_name: Optional template name
        @returns Always True
        """
        logger.info(
            "mock_whatsapp_sent",
            phone=phone,
            message=message[:100],
            template=template_name,
            provider="mock",
        )
        return True


def get_whatsapp_provider() -> WhatsAppProvider:
    """
    Factory: return the configured WhatsApp provider based on environment.

    @returns WhatsAppProvider instance (Meta Cloud or Mock)
    """
    if os.environ.get("WA_ACCESS_TOKEN"):
        return WhatsAppCloudProvider()
    logger.warning(
        "whatsapp_provider_fallback_to_mock",
        reason="WA_ACCESS_TOKEN not set",
    )
    return MockWhatsAppProvider()
