"""
AI Help Bot router — lightweight in-app navigation/help assistant.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.services.help_bot import AnswerResponse, answer_help_query

router = APIRouter()


class HelpAskRequest(BaseModel):
    """
    Request to ask the help bot.

    @param query: User question (1-1000 chars)
    """

    query: str = Field(..., min_length=1, max_length=1000)


@router.post("/ask", response_model=AnswerResponse)
async def ask_help_bot(
    data: HelpAskRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> AnswerResponse:
    """
    Ask the help bot a navigation / how-do-I question.
    Clinical questions are refused — the user is redirected to a clinician
    or to the Clinical Decision Support module.

    @param data: Help question
    @param current_user: Authenticated user from JWT (used for role + tenant)
    @returns Help bot answer with suggested links
    """
    role = current_user.roles[0] if current_user.roles else "staff"
    return await answer_help_query(
        query=data.query,
        user_role=role,
        facility_id=current_user.facility_id,
    )
