"""Celery tasks for automated patient communication scheduling."""

from __future__ import annotations

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(name="comms.schedule_appointment_reminders")
def schedule_appointment_reminders() -> dict[str, int]:
    """
    Schedule appointment reminder messages.

    Runs daily via Celery Beat. Finds appointments in the next 24 hours
    that have not yet received a reminder, and queues SMS/WhatsApp messages
    for each patient based on their communication preferences.

    @returns Dict with count of reminders queued
    """
    # In production this would:
    # 1. Query appointments WHERE date BETWEEN now AND now+24h
    #    AND reminder_sent = false
    # 2. For each appointment, look up patient phone + preferences
    # 3. Call CommunicationService.send_message() with the appointment_reminder template
    # 4. Mark the appointment as reminder_sent = true
    logger.info("task_schedule_appointment_reminders_started")

    queued = 0
    # TODO: Wire to actual DB queries when appointment + patient models are connected
    # async for appointment in get_upcoming_appointments(hours=24):
    #     pref = await get_patient_preferences(appointment.patient_id, appointment.facility_id)
    #     channel = pref.preferred_channel if pref.consent_given else MessageChannel.sms
    #     template = resolve_template("appointment_reminder", channel, pref.language)
    #     params = {
    #         "patient_name": appointment.patient_name,
    #         "facility_name": appointment.facility_name,
    #         "date": appointment.date.isoformat(),
    #         "time": appointment.start_time.strftime("%H:%M"),
    #     }
    #     await service.send_message(...)
    #     queued += 1

    logger.info("task_schedule_appointment_reminders_completed", queued=queued)
    return {"reminders_queued": queued}


@shared_task(name="comms.schedule_anc_reminders")
def schedule_anc_reminders() -> dict[str, int]:
    """
    Schedule ANC visit reminder messages.

    Runs weekly via Celery Beat. Finds ANC patients with upcoming visits
    in the next 7 days and queues reminder messages.

    @returns Dict with count of reminders queued
    """
    logger.info("task_schedule_anc_reminders_started")

    queued = 0
    # TODO: Wire to MCH/ANC visit schedule queries
    # async for anc_visit in get_upcoming_anc_visits(days=7):
    #     params = {
    #         "patient_name": anc_visit.patient_name,
    #         "date": anc_visit.visit_date.isoformat(),
    #     }
    #     await service.send_message(...)
    #     queued += 1

    logger.info("task_schedule_anc_reminders_completed", queued=queued)
    return {"anc_reminders_queued": queued}


@shared_task(name="comms.schedule_immunization_reminders")
def schedule_immunization_reminders() -> dict[str, int]:
    """
    Schedule childhood immunization reminder messages.

    Runs weekly via Celery Beat. Finds children with vaccinations due
    in the next 7 days and queues reminder messages to their parents.

    @returns Dict with count of reminders queued
    """
    logger.info("task_schedule_immunization_reminders_started")

    queued = 0
    # TODO: Wire to MCH/immunization schedule queries
    # async for imm in get_upcoming_immunizations(days=7):
    #     params = {
    #         "patient_name": imm.parent_name,
    #         "child_name": imm.child_name,
    #         "vaccine_name": imm.vaccine_name,
    #         "date": imm.due_date.isoformat(),
    #         "facility_name": imm.facility_name,
    #     }
    #     await service.send_message(...)
    #     queued += 1

    logger.info("task_schedule_immunization_reminders_completed", queued=queued)
    return {"immunization_reminders_queued": queued}


@shared_task(name="comms.check_unsent_messages")
def check_unsent_messages() -> dict[str, int]:
    """
    Retry failed and queued messages.

    Runs every 5 minutes via Celery Beat. Picks up messages in 'failed'
    or 'queued' status and retries delivery (max 3 attempts per message).

    @returns Dict with count of messages retried
    """
    logger.info("task_check_unsent_messages_started")

    retried = 0
    # TODO: Wire to CommunicationService.retry_failed_messages()
    # This requires an async-to-sync bridge since Celery tasks are synchronous:
    # import asyncio
    # from app.database import async_session_factory
    # async def _retry():
    #     async with async_session_factory() as db:
    #         service = CommunicationService(db)
    #         return await service.retry_failed_messages(max_retries=3)
    # retried = asyncio.run(_retry())

    logger.info("task_check_unsent_messages_completed", retried=retried)
    return {"messages_retried": retried}


# ── Celery Beat Schedule (to be merged into the app's celeryconfig) ────────
#
# Example addition to services/api-gateway/celeryconfig.py:
#
# from celery.schedules import crontab
#
# beat_schedule = {
#     ...
#     "schedule-appointment-reminders": {
#         "task": "comms.schedule_appointment_reminders",
#         "schedule": crontab(hour=6, minute=0),  # Daily at 6 AM EAT
#     },
#     "schedule-anc-reminders": {
#         "task": "comms.schedule_anc_reminders",
#         "schedule": crontab(hour=7, minute=0, day_of_week="monday"),
#     },
#     "schedule-immunization-reminders": {
#         "task": "comms.schedule_immunization_reminders",
#         "schedule": crontab(hour=7, minute=30, day_of_week="monday"),
#     },
#     "check-unsent-messages": {
#         "task": "comms.check_unsent_messages",
#         "schedule": 300.0,  # Every 5 minutes
#     },
# }
