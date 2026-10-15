"""Leads router - broker-facing CRUD backed by `LeadRepository`.

The detail payload is a single-round-trip `LeadDetailOut` that
embeds messages, documents, the latest qualification and the latest
analysis so the frontend LeadDetailPage renders in one request.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.agents.client import get_groq_client
from app.agents.errors import user_safe_message
from app.agents.prompts import get_prompt_library
from app.agents.qualification_agent import QualificationAgent
from app.db import get_db
from app.repositories.analyses import AnalysisRepository
from app.repositories.conversations import ConversationMessageRepository
from app.repositories.documents import DocumentRepository
from app.repositories.leads import LeadRepository
from app.repositories.qualifications import QualificationRepository
from app.schemas.analysis import AnalysisOut
from app.schemas.chat import ChatMessageOut
from app.schemas.document import DocumentOut
from app.schemas.enums import LeadStatus
from app.schemas.lead import LeadDetailOut, LeadOut, LeadUpdate, ensure_lead_detail_rebuilt
from app.schemas.qualification import QualificationBlockedDetail, QualificationOut
from app.services.qualification import (
    LeadNotFoundError,
    QualificationBlocked,
    QualificationNotAllowed,
    QualificationOrchestrator,
    QualificationScorer,
)
from app.settings import get_settings

# Resolve forward refs on `LeadDetailOut` (it depends on ChatMessageOut,
# DocumentOut, QualificationOut, AnalysisOut which can't be imported during
# lead.py's own module execution without a cycle).
ensure_lead_detail_rebuilt()

log = logging.getLogger("securelife.router.leads")

# Computed on LeadOut; dropped before re-validating into LeadDetailOut,
# which recomputes them.
_COMPUTED_FIELDS = {"profile_checklist", "profile_completeness"}

router = APIRouter()


@router.get("", response_model=list[LeadOut])
async def list_leads(
    status: LeadStatus | None = Query(default=None),  # noqa: B008
    search: str | None = Query(default=None, max_length=200),  # noqa: B008
    limit: int = Query(default=100, ge=1, le=500),  # noqa: B008
    include_incomplete: bool = Query(  # noqa: B008
        default=False,
        description=(
            "Include leads missing name OR contact (email/phone). "
            "Default false — the broker view hides in-flight prospects "
            "until they've shared mandatory fields."
        ),
    ),
) -> list[LeadOut]:
    """List leads for the broker dashboard."""
    async with get_db().session() as session:
        repo = LeadRepository(session)
        leads = await repo.list(
            status=status,
            search=search,
            limit=limit,
            include_incomplete=include_incomplete,
        )
    return [LeadOut.model_validate(lead) for lead in leads]


@router.get("/{lead_id}", response_model=LeadDetailOut)
async def get_lead(lead_id: str) -> LeadDetailOut:
    """Lead detail: lead + messages + documents + latest analysis.

    One round-trip for the LeadDetailPage. `latest_qualification` and
    `latest_analysis` are `null` until the respective agent has run.
    """
    async with get_db().session() as session:
        lead_repo = LeadRepository(session)
        conv_repo = ConversationMessageRepository(session)
        analysis_repo = AnalysisRepository(session)

        lead = await lead_repo.get_by_id(lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")

        messages = await conv_repo.list_for_lead(lead_id, include_system=False)
        documents = await DocumentRepository(session).list_for_lead(lead_id)
        latest_qualification = await QualificationRepository(session).latest_for_lead(lead_id)
        latest_analysis = await analysis_repo.latest_for_lead(lead_id)

    # Pydantic can't walk the ORM relationships lazily once the session is
    # closed, so we validate each piece explicitly inside the `async with`.
    payload = LeadOut.model_validate(lead).model_dump(exclude=_COMPUTED_FIELDS)
    payload["messages"] = [ChatMessageOut.model_validate(m).model_dump() for m in messages]
    payload["documents"] = [DocumentOut.model_validate(d).model_dump(mode="json") for d in documents]
    payload["latest_qualification"] = (
        QualificationOut.model_validate(latest_qualification).model_dump(mode="json")
        if latest_qualification is not None
        else None
    )
    payload["latest_analysis"] = (
        AnalysisOut.model_validate(latest_analysis).model_dump(mode="json")
        if latest_analysis is not None
        else None
    )
    return LeadDetailOut.model_validate(payload)


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: str) -> None:
    """Hard-delete a lead and all its children (messages, documents,
    extractions, analyses).

    204 on success, 404 if the lead does not exist. There is no
    confirmation gate on the server side — the UI shows a confirmation
    dialog before issuing the request.
    """
    async with get_db().session() as session:
        repo = LeadRepository(session)
        lead = await repo.get_by_id(lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")
        await repo.delete(lead)
        await session.commit()


@router.post(
    "/{lead_id}/qualify",
    response_model=QualificationOut,
    responses={
        400: {"model": QualificationBlockedDetail, "description": "Name, contact or insurance type missing"},
        409: {"description": "Lead is already past qualification"},
        502: {"description": "The qualification agent failed"},
    },
)
async def qualify_lead(lead_id: str) -> QualificationOut:
    """Run the qualification agent ("Run qualification agent").

    Sets the lead to QUALIFIED / DISQUALIFIED, or leaves it NEW when the
    verdict is NEEDS_MORE_INFO. Returns 400 with a `missing` list (and spends
    no tokens) until name, contact and insurance type are captured.
    """
    orchestrator = QualificationOrchestrator(
        agent_factory=_build_qualification_agent,
        scorer=QualificationScorer(),
    )
    try:
        qualification = await orchestrator.qualify(lead_id)
    except LeadNotFoundError:
        raise HTTPException(status_code=404, detail="Lead not found") from None
    except QualificationNotAllowed as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except QualificationBlocked as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc), "missing": list(exc.missing)},
        ) from None
    except Exception as exc:
        log.exception("Qualification agent failed for lead %s", lead_id)
        raise HTTPException(status_code=502, detail=user_safe_message(exc)) from None
    return QualificationOut.model_validate(qualification)


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(lead_id: str, patch: LeadUpdate) -> LeadOut:
    """Broker-side update: contact, stage, closure, notes and captured fields.

    Closing a lead (status CLOSED) requires a reason — disqualified,
    purchased or other — plus an optional note. Moving it to any other stage
    re-opens it and clears the closure.
    """
    async with get_db().session() as session:
        repo = LeadRepository(session)
        lead = await repo.get_by_id(lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")
        closing = (patch.status or lead.status) == LeadStatus.CLOSED
        if closing and (patch.close_reason or lead.close_reason) is None:
            raise HTTPException(
                status_code=400,
                detail="Choose why this prospect is closed: disqualified, purchased, or other.",
            )
        await repo.patch(
            lead,
            full_name=patch.full_name,
            email=patch.email,
            phone=patch.phone,
            city=patch.city,
            status=patch.status,
            close_reason=patch.close_reason,
            close_note=patch.close_note,
            conversation_summary=patch.conversation_summary,
            extracted_fields=patch.extracted_fields,
        )
        await session.commit()
        await session.refresh(lead)
        return LeadOut.model_validate(lead)


def _build_qualification_agent() -> QualificationAgent:
    """Wire up QualificationAgent from process-wide singletons."""
    settings = get_settings()
    return QualificationAgent(
        client=get_groq_client(),
        prompt_library=get_prompt_library(),
        model_name=settings.groq_model_qualification,
        timeout_s=settings.groq_timeout_qualification,
        max_tokens=settings.groq_max_tokens_qualification,
    )
