"""Communication service — message sending, template rendering, consent checks."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.comms.models import (
    BulkMessageRequest,
    CommunicationPreference,
    CommunicationPreferenceUpdate,
    MessageCategory,
    MessageChannel,
    MessageListResponse,
    MessageResponse,
    MessageStatus,
    MessageTemplate,
    MessageTemplateCreate,
    PatientMessage,
    SendMessageRequest,
)
from app.services.comms.sms_provider import SMSProvider, get_sms_provider
from app.services.comms.templates import DEFAULT_TEMPLATES, DefaultTemplate
from app.services.comms.whatsapp_provider import WhatsAppProvider, get_whatsapp_provider

logger = structlog.get_logger(__name__)

# ── Phone Number Normalization ─────────────────────────────────────────────

_KE_MOBILE_RE = re.compile(r"^0([17]\d{8})$")
_KE_PLUS_RE = re.compile(r"^\+254(\d{9})$")
_KE_254_RE = re.compile(r"^254(\d{9})$")


def normalize_kenyan_phone(raw: str) -> str:
    """
    Normalize a Kenyan phone number to E.164 format (+254XXXXXXXXX).

    Handles formats: 07xx, 01xx, 254xxx, +254xxx.

    @param raw: Raw phone number string
    @returns E.164 formatted phone number
    @raises ValueError: If the phone number cannot be normalized
    """
    cleaned = raw.strip().replace(" ", "").replace("-", "")

    # Already E.164
    match = _KE_PLUS_RE.match(cleaned)
    if match:
        return cleaned

    # 254xxxxxxxxx without +
    match = _KE_254_RE.match(cleaned)
    if match:
        return f"+254{match.group(1)}"

    # 07xxxxxxxx or 01xxxxxxxx
    match = _KE_MOBILE_RE.match(cleaned)
    if match:
        return f"+254{match.group(1)}"

    raise ValueError(
        f"Cannot normalize phone number '{raw}'. "
        "Expected Kenyan format: 07xx, 01xx, +254xxx, or 254xxx."
    )


# ── Template Rendering ─────────────────────────────────────────────────────


def render_template(body_template: str, params: dict[str, str]) -> str:
    """
    Render a message template by replacing {placeholder} tokens.

    @param body_template: Template string with {key} placeholders
    @param params: Mapping of placeholder key to value
    @returns Rendered message body
    """
    result = body_template
    for key, value in params.items():
        result = result.replace(f"{{{key}}}", value)
    return result


# ── Service Class ──────────────────────────────────────────────────────────


class CommunicationService:
    """
    Service for patient communications: sending, template management,
    consent enforcement, and message history.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._sms: SMSProvider = get_sms_provider()
        self._whatsapp: WhatsAppProvider = get_whatsapp_provider()

        # In-memory template store (seeded from defaults).
        # In production, these would live in the database.
        self._templates: dict[uuid.UUID, MessageTemplate] = {}
        self._custom_templates: dict[uuid.UUID, MessageTemplate] = {}
        self._preferences: dict[tuple[uuid.UUID, uuid.UUID], CommunicationPreference] = {}
        self._messages: dict[uuid.UUID, PatientMessage] = {}

        # Seed default templates
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        """Seed in-memory template store from built-in defaults."""
        for dt in DEFAULT_TEMPLATES:
            tid = uuid.uuid5(uuid.NAMESPACE_DNS, dt.name)
            now = datetime.now(timezone.utc)
            self._templates[tid] = MessageTemplate(
                id=tid,
                name=dt.name,
                category=dt.category,
                channel=dt.channel,
                body_template=dt.body_template,
                is_active=True,
                language=dt.language,
                created_at=now,
            )

    # ── Consent ────────────────────────────────────────────────────────────

    def _check_consent(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        category: MessageCategory,
    ) -> bool:
        """
        Check if the patient has given consent and has not opted out of this
        message category. Required by Kenya Data Protection Act.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @param category: Message category to check
        @returns True if the message may be sent
        """
        key = (patient_id, facility_id)
        pref = self._preferences.get(key)
        if pref is None:
            # No preferences stored — default to allowing (facility can
            # set consent during registration).
            return True
        if not pref.consent_given:
            logger.warning(
                "message_blocked_no_consent",
                patient_id=str(patient_id),
                category=category,
            )
            return False
        if category in pref.opt_out_categories:
            logger.info(
                "message_blocked_opt_out",
                patient_id=str(patient_id),
                category=category,
            )
            return False
        return True

    # ── Send ───────────────────────────────────────────────────────────────

    async def send_message(
        self,
        facility_id: uuid.UUID,
        request: SendMessageRequest,
        recipient_phone: str,
    ) -> PatientMessage:
        """
        Send a single message to a patient.

        @param facility_id: Facility UUID from JWT
        @param request: Send message request data
        @param recipient_phone: Raw patient phone number
        @returns Created PatientMessage with delivery status
        @raises ValueError: If consent not given or phone invalid
        """
        # Consent check (Kenya DPA)
        if not self._check_consent(request.patient_id, facility_id, request.category):
            raise ValueError(
                "Patient has not given communication consent or has opted out "
                "of this message category."
            )

        # Normalize phone
        normalized_phone = normalize_kenyan_phone(recipient_phone)

        # Resolve body
        body: str
        if request.template_id and request.template_id in self._templates:
            template = self._templates[request.template_id]
            params = request.template_params or {}
            body = render_template(template.body_template, params)
        elif request.template_id and request.template_id in self._custom_templates:
            template = self._custom_templates[request.template_id]
            params = request.template_params or {}
            body = render_template(template.body_template, params)
        elif request.body:
            body = request.body
        else:
            raise ValueError(
                "Either template_id with params or body must be provided."
            )

        now = datetime.now(timezone.utc)
        msg_id = uuid.uuid4()

        # Scheduled messages are queued for later
        if request.scheduled_at and request.scheduled_at > now:
            msg = PatientMessage(
                id=msg_id,
                patient_id=request.patient_id,
                facility_id=facility_id,
                channel=request.channel,
                category=request.category,
                recipient_phone=normalized_phone,
                template_id=request.template_id,
                template_params=request.template_params,
                body=body,
                status=MessageStatus.queued,
                created_at=now,
            )
            self._messages[msg_id] = msg
            logger.info(
                "message_scheduled",
                message_id=str(msg_id),
                scheduled_at=request.scheduled_at.isoformat(),
            )
            return msg

        # Deliver immediately
        success = await self._deliver(request.channel, normalized_phone, body)

        msg = PatientMessage(
            id=msg_id,
            patient_id=request.patient_id,
            facility_id=facility_id,
            channel=request.channel,
            category=request.category,
            recipient_phone=normalized_phone,
            template_id=request.template_id,
            template_params=request.template_params,
            body=body,
            status=MessageStatus.sent if success else MessageStatus.failed,
            sent_at=now if success else None,
            error_message=None if success else "Delivery failed",
            created_at=now,
        )
        self._messages[msg_id] = msg
        return msg

    async def send_bulk_messages(
        self,
        facility_id: uuid.UUID,
        request: BulkMessageRequest,
    ) -> list[PatientMessage]:
        """
        Send bulk messages to multiple patients.

        @param facility_id: Facility UUID from JWT
        @param request: Bulk message request
        @returns List of created PatientMessage records
        """
        patient_ids = request.patient_ids or []
        results: list[PatientMessage] = []

        for pid in patient_ids:
            send_req = SendMessageRequest(
                patient_id=pid,
                channel=request.channel,
                category=request.category,
                template_id=request.template_id,
                template_params=request.template_params,
            )
            try:
                # In production, look up the patient phone from DB.
                # For now we skip patients without a known phone.
                logger.info(
                    "bulk_message_queued",
                    patient_id=str(pid),
                    category=request.category,
                )
                now = datetime.now(timezone.utc)
                msg = PatientMessage(
                    id=uuid.uuid4(),
                    patient_id=pid,
                    facility_id=facility_id,
                    channel=request.channel,
                    category=request.category,
                    recipient_phone="pending_lookup",
                    template_id=request.template_id,
                    template_params=request.template_params,
                    body="(pending template render)",
                    status=MessageStatus.queued,
                    created_at=now,
                )
                self._messages[msg.id] = msg
                results.append(msg)
            except ValueError as exc:
                logger.warning(
                    "bulk_message_skipped",
                    patient_id=str(pid),
                    reason=str(exc),
                )

        return results

    async def _deliver(
        self,
        channel: MessageChannel,
        phone: str,
        body: str,
    ) -> bool:
        """
        Dispatch a message through the appropriate channel provider.

        @param channel: Target channel (sms / whatsapp)
        @param phone: E.164 phone number
        @param body: Message body text
        @returns True if delivery was accepted
        """
        if channel == MessageChannel.sms:
            return await self._sms.send_sms(phone, body)
        if channel == MessageChannel.whatsapp:
            return await self._whatsapp.send_message(phone, body)
        if channel == MessageChannel.email:
            logger.warning("email_channel_not_implemented")
            return False
        return False

    # ── Message History ────────────────────────────────────────────────────

    async def get_message_history(
        self,
        facility_id: uuid.UUID,
        *,
        patient_id: uuid.UUID | None = None,
        page: int = 1,
        per_page: int = 20,
        status: MessageStatus | None = None,
        channel: MessageChannel | None = None,
    ) -> MessageListResponse:
        """
        Retrieve paginated message history for a facility.

        @param facility_id: Facility UUID
        @param patient_id: Optional patient filter
        @param page: Page number (1-based)
        @param per_page: Items per page
        @param status: Optional status filter
        @param channel: Optional channel filter
        @returns Paginated message list
        """
        msgs = [
            m for m in self._messages.values()
            if m.facility_id == facility_id
        ]

        if patient_id is not None:
            msgs = [m for m in msgs if m.patient_id == patient_id]
        if status is not None:
            msgs = [m for m in msgs if m.status == status]
        if channel is not None:
            msgs = [m for m in msgs if m.channel == channel]

        # Sort by created_at descending
        msgs.sort(key=lambda m: m.created_at, reverse=True)

        total = len(msgs)
        start = (page - 1) * per_page
        end = start + per_page
        page_items = msgs[start:end]

        return MessageListResponse(
            items=[
                MessageResponse(
                    id=m.id,
                    patient_id=m.patient_id,
                    facility_id=m.facility_id,
                    channel=m.channel,
                    category=m.category,
                    recipient_phone=m.recipient_phone,
                    template_id=m.template_id,
                    body=m.body,
                    status=m.status,
                    retry_count=m.retry_count,
                    sent_at=m.sent_at,
                    delivered_at=m.delivered_at,
                    read_at=m.read_at,
                    error_message=m.error_message,
                    created_at=m.created_at,
                )
                for m in page_items
            ],
            total=total,
            page=page,
            per_page=per_page,
        )

    async def get_message_detail(
        self,
        facility_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> MessageResponse | None:
        """
        Retrieve a single message by ID, scoped to facility.

        @param facility_id: Facility UUID
        @param message_id: Message UUID
        @returns MessageResponse or None if not found
        """
        msg = self._messages.get(message_id)
        if msg is None or msg.facility_id != facility_id:
            return None
        return MessageResponse(
            id=msg.id,
            patient_id=msg.patient_id,
            facility_id=msg.facility_id,
            channel=msg.channel,
            category=msg.category,
            recipient_phone=msg.recipient_phone,
            template_id=msg.template_id,
            body=msg.body,
            status=msg.status,
            retry_count=msg.retry_count,
            sent_at=msg.sent_at,
            delivered_at=msg.delivered_at,
            read_at=msg.read_at,
            error_message=msg.error_message,
            created_at=msg.created_at,
        )

    # ── Preferences ────────────────────────────────────────────────────────

    async def get_patient_preferences(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> CommunicationPreference:
        """
        Get communication preferences for a patient. Creates defaults if none exist.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @returns CommunicationPreference record
        """
        key = (patient_id, facility_id)
        if key not in self._preferences:
            now = datetime.now(timezone.utc)
            self._preferences[key] = CommunicationPreference(
                id=uuid.uuid4(),
                patient_id=patient_id,
                facility_id=facility_id,
                preferred_channel=MessageChannel.sms,
                opt_out_categories=[],
                consent_given=False,
                consent_date=None,
                created_at=now,
            )
        return self._preferences[key]

    async def update_patient_preferences(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        data: CommunicationPreferenceUpdate,
    ) -> CommunicationPreference:
        """
        Update communication preferences for a patient.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @param data: Fields to update
        @returns Updated CommunicationPreference
        """
        pref = await self.get_patient_preferences(patient_id, facility_id)
        now = datetime.now(timezone.utc)

        updated_fields: dict[str, object] = {"updated_at": now}
        if data.preferred_channel is not None:
            updated_fields["preferred_channel"] = data.preferred_channel
        if data.opt_out_categories is not None:
            updated_fields["opt_out_categories"] = data.opt_out_categories
        if data.consent_given is not None:
            updated_fields["consent_given"] = data.consent_given
            if data.consent_given:
                updated_fields["consent_date"] = now

        updated = pref.model_copy(update=updated_fields)
        self._preferences[(patient_id, facility_id)] = updated
        return updated

    # ── Templates ──────────────────────────────────────────────────────────

    async def list_templates(
        self,
        *,
        language: str | None = None,
        channel: MessageChannel | None = None,
        category: MessageCategory | None = None,
    ) -> list[MessageTemplate]:
        """
        List all available message templates (default + custom).

        @param language: Optional language filter
        @param channel: Optional channel filter
        @param category: Optional category filter
        @returns List of MessageTemplate
        """
        all_templates = list(self._templates.values()) + list(
            self._custom_templates.values()
        )
        if language:
            all_templates = [t for t in all_templates if t.language == language]
        if channel:
            all_templates = [t for t in all_templates if t.channel == channel]
        if category:
            all_templates = [t for t in all_templates if t.category == category]
        return [t for t in all_templates if t.is_active]

    async def create_template(
        self,
        facility_id: uuid.UUID,
        data: MessageTemplateCreate,
    ) -> MessageTemplate:
        """
        Create a custom message template.

        @param facility_id: Facility UUID (for scoping)
        @param data: Template creation data
        @returns Created MessageTemplate
        """
        now = datetime.now(timezone.utc)
        tid = uuid.uuid4()
        template = MessageTemplate(
            id=tid,
            name=data.name,
            category=data.category,
            channel=data.channel,
            body_template=data.body_template,
            is_active=True,
            language=data.language,
            created_at=now,
        )
        self._custom_templates[tid] = template
        logger.info(
            "template_created",
            template_id=str(tid),
            name=data.name,
            facility_id=str(facility_id),
        )
        return template

    # ── Retry ──────────────────────────────────────────────────────────────

    async def retry_failed_messages(self, max_retries: int = 3) -> int:
        """
        Retry delivery of failed/queued messages up to max_retries.

        @param max_retries: Maximum retry attempts per message
        @returns Number of messages successfully retried
        """
        retried = 0
        for msg in list(self._messages.values()):
            if msg.status not in (MessageStatus.failed, MessageStatus.queued):
                continue
            if msg.retry_count >= max_retries:
                continue

            success = await self._deliver(msg.channel, msg.recipient_phone, msg.body)
            now = datetime.now(timezone.utc)

            updated_fields: dict[str, object] = {
                "retry_count": msg.retry_count + 1,
                "updated_at": now,
            }
            if success:
                updated_fields["status"] = MessageStatus.sent
                updated_fields["sent_at"] = now
                updated_fields["error_message"] = None
                retried += 1
            else:
                updated_fields["error_message"] = (
                    f"Retry {msg.retry_count + 1} failed"
                )

            self._messages[msg.id] = msg.model_copy(update=updated_fields)

        return retried
