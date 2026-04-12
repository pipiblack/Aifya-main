"""
Patient Communication Hub router.
Endpoints for sending messages, managing templates, and patient preferences.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
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
    SendMessageRequest,
)
from app.services.comms.service import CommunicationService

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_module("communications"))])


# ── Send Messages ─────────────────────────────────────────────────────────────


@router.post(
    "/messages/send",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    data: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """
    Send a single message to a patient via SMS or WhatsApp.
    Checks consent before sending per Kenya DPA.

    @param data: Send message request
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Created message with delivery status
    """
    service = CommunicationService(db)

    # Look up patient phone from DB
    from app.models.patient import Patient
    from sqlalchemy import select

    result = await db.execute(
        select(Patient).where(
            Patient.id == data.patient_id,
            Patient.facility_id == current_user.facility_id,
            Patient.is_deleted == False,  # noqa: E712
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    if not patient.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient has no phone number on file",
        )

    try:
        msg = await service.send_message(
            facility_id=current_user.facility_id,
            request=data,
            recipient_phone=patient.phone,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return MessageResponse(message=msg)


@router.post(
    "/messages/bulk",
    response_model=list[MessageResponse],
    status_code=status.HTTP_201_CREATED,
)
async def send_bulk_messages(
    data: BulkMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> list[MessageResponse]:
    """
    Send bulk messages to multiple patients. Admin only.

    @param data: Bulk message request
    @param db: Database session
    @param current_user: Authenticated admin from JWT
    @returns List of created messages
    """
    service = CommunicationService(db)
    messages = await service.send_bulk_messages(
        facility_id=current_user.facility_id,
        request=data,
    )
    return [MessageResponse(message=m) for m in messages]


# ── Message History ───────────────────────────────────────────────────────────


@router.get(
    "/messages",
    response_model=MessageListResponse,
)
async def get_messages(
    patient_id: uuid.UUID | None = Query(None),
    channel: str | None = Query(None),
    message_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MessageListResponse:
    """
    Get paginated message history for the facility.

    @param patient_id: Optional patient filter
    @param channel: Optional channel filter
    @param message_status: Optional status filter
    @param page: Page number
    @param per_page: Items per page
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Paginated message list
    """
    service = CommunicationService(db)

    status_filter = MessageStatus(message_status) if message_status else None
    channel_filter = MessageChannel(channel) if channel else None

    return await service.get_message_history(
        facility_id=current_user.facility_id,
        patient_id=patient_id,
        page=page,
        per_page=per_page,
        status=status_filter,
        channel=channel_filter,
    )


@router.get(
    "/messages/{message_id}",
    response_model=MessageResponse,
)
async def get_message(
    message_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> MessageResponse:
    """
    Get a single message detail.

    @param message_id: Message UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Message detail
    """
    service = CommunicationService(db)
    msg = await service.get_message_detail(
        facility_id=current_user.facility_id,
        message_id=message_id,
    )
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )
    return msg


# ── Preferences ───────────────────────────────────────────────────────────────


@router.get(
    "/preferences/{patient_id}",
    response_model=CommunicationPreference,
)
async def get_preferences(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CommunicationPreference:
    """
    Get communication preferences for a patient.

    @param patient_id: Patient UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Communication preference record
    """
    service = CommunicationService(db)
    return await service.get_patient_preferences(
        patient_id=patient_id,
        facility_id=current_user.facility_id,
    )


@router.put(
    "/preferences/{patient_id}",
    response_model=CommunicationPreference,
)
async def update_preferences(
    patient_id: uuid.UUID,
    data: CommunicationPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CommunicationPreference:
    """
    Update communication preferences for a patient.

    @param patient_id: Patient UUID
    @param data: Preference fields to update
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Updated preferences
    """
    service = CommunicationService(db)
    return await service.update_patient_preferences(
        patient_id=patient_id,
        facility_id=current_user.facility_id,
        data=data,
    )


# ── Templates ─────────────────────────────────────────────────────────────────


@router.get(
    "/templates",
    response_model=list[MessageTemplate],
)
async def list_templates(
    language: str | None = Query(None),
    channel: str | None = Query(None),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[MessageTemplate]:
    """
    List available message templates.

    @param language: Optional language filter (en/sw)
    @param channel: Optional channel filter
    @param category: Optional category filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of active templates
    """
    service = CommunicationService(db)

    channel_filter = MessageChannel(channel) if channel else None
    category_filter = MessageCategory(category) if category else None

    return await service.list_templates(
        language=language,
        channel=channel_filter,
        category=category_filter,
    )


@router.post(
    "/templates",
    response_model=MessageTemplate,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    data: MessageTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> MessageTemplate:
    """
    Create a custom message template. Admin only.

    @param data: Template creation data
    @param db: Database session
    @param current_user: Authenticated admin from JWT
    @returns Created template
    """
    service = CommunicationService(db)
    return await service.create_template(
        facility_id=current_user.facility_id,
        data=data,
    )
