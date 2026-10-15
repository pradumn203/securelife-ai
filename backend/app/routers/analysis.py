"""Analysis router - real DB-backed implementation."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.agents.analysis_agent import AnalysisAgent
from app.agents.client import get_groq_client
from app.agents.errors import user_safe_message
from app.agents.prompts import get_prompt_library
from app.db import get_db
from app.repositories.analyses import AnalysisRepository
from app.schemas.analysis import AnalysisGenerateIn, AnalysisOut
from app.services.analysis_orchestrator import (
    AnalysisNotPossibleError,
    AnalysisOrchestrator,
    LeadNotFoundError,
)
from app.settings import get_settings

logger = logging.getLogger("securelife.analysis")

router = APIRouter()


def _build_orchestrator() -> AnalysisOrchestrator:
    """Compose the orchestrator from process-wide singletons.

    The LLM client is passed as a factory so lead-not-found / no-extractions
    paths still return clean 404s / 400s when the API key hasn't been set yet
    in a dev environment.
    """
    settings = get_settings()
    agent = AnalysisAgent(
        client=get_groq_client,  # lazy; raises only when actually invoked
        model_name=settings.groq_model_analysis,
        timeout_s=settings.groq_timeout_analysis,
        max_tokens=settings.groq_max_tokens_analysis,
        prompts=get_prompt_library(),
    )
    return AnalysisOrchestrator(agent=agent)


@router.post("/generate", response_model=AnalysisOut)
async def generate_analysis(body: AnalysisGenerateIn) -> AnalysisOut:
    """Run the analysis agent and persist the resulting Analysis."""
    orchestrator = _build_orchestrator()
    try:
        analysis = await orchestrator.generate_for_lead(body.lead_id)
    except LeadNotFoundError:
        raise HTTPException(status_code=404, detail="Lead not found") from None
    except AnalysisNotPossibleError as exc:
        # Business-rule 400 — user-safe by construction (e.g. "no documents yet").
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        # Any provider / infra failure — full detail in the log, UI gets a
        # short safe sentence routed by HTTP status (429 → rate limited, etc).
        logger.exception("Analysis generation failed for lead %s", body.lead_id)
        raise HTTPException(status_code=502, detail=user_safe_message(exc)) from None
    return AnalysisOut.model_validate(analysis)


@router.get("", response_model=AnalysisOut | None)
async def get_latest_analysis(
    lead_id: str = Query(..., description="Lead whose latest analysis to fetch"),  # noqa: B008
) -> AnalysisOut | None:
    """Return the most recent Analysis for a lead, or null if none exists."""
    async with get_db().session() as session:
        repo = AnalysisRepository(session)
        analysis = await repo.latest_for_lead(lead_id)
    if analysis is None:
        return None
    return AnalysisOut.model_validate(analysis)
