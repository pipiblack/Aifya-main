"""
Aifya in-app AI help bot.
Lightweight assistant for navigation, "how do I…" questions, and FAQs.
Routes through the central ai-service to Qwen 72B (port 8002).

Per CLAUDE.md:
- All LLM calls go through ai-service — never call vLLM directly
- Routing: simple → Qwen 72B (8002)
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Final

import httpx
from pydantic import BaseModel
from structlog import get_logger

logger = get_logger(__name__)

_AI_SERVICE_URL: Final[str] = os.getenv("AI_SERVICE_URL", "http://ai-service:8001")

_SYSTEM_PROMPT: Final[str] = (
    "You are Aifya's help assistant for hospital staff in Kenya. "
    "Answer questions about how to use the system, navigate modules, "
    "and find features. Be concise (max 4 short paragraphs). "
    "If asked clinical questions (drug doses, diagnosis, treatment), "
    "do NOT answer — instead politely redirect the user to the clinician "
    "or to the Clinical Decision Support module. "
    "When you suggest a feature, mention the module name in lowercase, "
    "for example: 'open the finance module' or 'go to /pharmacy'. "
    "Never make up features that don't exist."
)

# Map keywords in user query → suggested in-app routes (best-effort).
_ROUTE_KEYWORDS: dict[str, list[str]] = {
    "/finance/payroll": ["payroll", "salary", "salaries", "payslip", "paye", "nssf"],
    "/finance": ["finance", "ledger", "account", "expense", "revenue", "p&l", "pnl"],
    "/billing": ["bill", "invoice", "payment", "receipt", "charge"],
    "/patients": ["patient", "register patient", "add patient", "demographics"],
    "/appointments": ["appointment", "booking", "schedule", "calendar"],
    "/pharmacy": ["pharmacy", "drug", "medication", "dispense", "prescription"],
    "/laboratory": ["lab", "laboratory", "test", "specimen"],
    "/radiology": ["x-ray", "xray", "ct", "mri", "ultrasound", "imaging"],
    "/ipd": ["admission", "ward", "bed", "ipd", "inpatient", "discharge"],
    "/emergency": ["emergency", "triage", "er ", "casualty"],
    "/mch": ["anc", "mch", "antenatal", "immunization", "vaccine", "child"],
    "/hr": ["hr ", "leave", "attendance", "shift"],
    "/insurance": ["insurance", "sha", "claim", "preauth", "pre-authorization"],
    "/referrals": ["referral", "refer "],
    "/communications": ["sms", "whatsapp", "message", "notify", "communication"],
    "/inventory": ["stock", "inventory", "supplier", "purchase order"],
    "/reports": ["report", "dhis2", "statistics"],
    "/dental": ["dental", "tooth", "teeth", "odontogram"],
    "/theatre": ["theatre", "theater", "operation", "surgery", "ot "],
    "/performance": ["kpi", "performance", "metrics", "dashboard"],
}


class SuggestedLink(BaseModel):
    """A suggested in-app navigation link returned to the UI."""

    label: str
    href: str


class AnswerResponse(BaseModel):
    """
    Help bot answer.

    @param answer: Free-text answer
    @param suggested_links: In-app routes the user might want to open
    @param confidence: 0-1 self-reported confidence (heuristic)
    @param model: Backing model name
    """

    answer: str
    suggested_links: list[SuggestedLink] = []
    confidence: float = 0.5
    model: str = "qwen-72b"


def _suggest_links(query: str) -> list[SuggestedLink]:
    """
    Suggest navigation links from the user's query using keyword matching.

    @param query: User question
    @returns Up to 3 suggested links
    """
    q = query.lower()
    matches: list[tuple[str, str]] = []
    for href, keywords in _ROUTE_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                # Build a label from the path
                label = href.strip("/").replace("/", " › ").title() or href
                matches.append((label, href))
                break
    seen: set[str] = set()
    out: list[SuggestedLink] = []
    for label, href in matches:
        if href in seen:
            continue
        seen.add(href)
        out.append(SuggestedLink(label=label, href=href))
        if len(out) >= 3:
            break
    return out


_CLINICAL_RED_FLAGS = re.compile(
    r"\b(dose|dosage|treat|treatment|prescribe|prescription|"
    r"diagnos|differential|interaction|contraindicat|antibiotic|"
    r"chemo|chemotherapy|insulin|warfarin|paracetamol)\b",
    re.IGNORECASE,
)


async def answer_help_query(
    query: str,
    user_role: str = "staff",
    facility_id: uuid.UUID | None = None,
) -> AnswerResponse:
    """
    Answer a help / how-do-I query via the AI service.

    @param query: The user question
    @param user_role: Role hint for the LLM (e.g. "doctor", "nurse")
    @param facility_id: Tenant facility UUID (for telemetry)
    @returns AnswerResponse
    """
    suggested = _suggest_links(query)

    # Hard guardrail: never answer clinical questions through the help bot
    if _CLINICAL_RED_FLAGS.search(query):
        return AnswerResponse(
            answer=(
                "This looks like a clinical question. For safety, the help "
                "assistant does not provide medical advice. Please consult "
                "the attending clinician, or open the Clinical Decision "
                "Support module for evidence-based guidance."
            ),
            suggested_links=[
                SuggestedLink(label="Clinical Decision Support", href="/cds"),
            ],
            confidence=0.95,
            model="guardrail",
        )

    payload = {
        "model": "qwen-72b",
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"[role={user_role}] {query.strip()}",
            },
        ],
        "max_tokens": 512,
        "temperature": 0.2,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{_AI_SERVICE_URL.rstrip('/')}/v1/chat/completions",
                json=payload,
            )
        if response.status_code == 200:
            data = response.json()
            text = data["choices"][0]["message"]["content"].strip()
            return AnswerResponse(
                answer=text,
                suggested_links=suggested,
                confidence=0.7,
                model="qwen-72b",
            )
        logger.warning(
            "help_bot_ai_error",
            status_code=response.status_code,
            body=response.text[:200],
        )
    except httpx.HTTPError as exc:
        logger.warning("help_bot_ai_unavailable", error=str(exc))

    # Fallback when AI service is unavailable
    return AnswerResponse(
        answer=(
            "I can't reach the AI service right now. Try the suggested links "
            "below, or ask your facility administrator. You can also press "
            "Cmd+K to open the command palette and search the system."
        ),
        suggested_links=suggested,
        confidence=0.3,
        model="fallback",
    )
