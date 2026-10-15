"""AnalysisOrchestrator - end-to-end analysis flow.

Loads context (lead + extractions), runs the AnalysisAgent, and
persists the Analysis + moves the lead to Completed analyses. Owns its own DB
session so it can be called from a request handler or (later) a
background task without the request-scoped session being torn
down mid-call.

See ARCHITECTURE.md section 7.1 for the session-per-job rule.
"""
from __future__ import annotations

from app.agents.analysis_agent import AnalysisAgent
from app.data_models.analysis import Analysis
from app.db import get_db
from app.repositories.analyses import AnalysisRepository
from app.repositories.documents import DocumentRepository
from app.repositories.leads import LeadRepository
from app.services.pipeline import PipelineRules


class AnalysisNotPossibleError(RuntimeError):
    """Raised when a lead has no extractions to analyse."""


class LeadNotFoundError(LookupError):
    """Raised when the lead id doesn't resolve."""


class AnalysisOrchestrator:
    """Compose the lead-load + agent call + persistence + status-advance step."""

    def __init__(self, agent: AnalysisAgent) -> None:
        self._agent = agent

    async def generate_for_lead(self, lead_id: str) -> Analysis:
        """Create and persist a new Analysis for `lead_id`.

        Raises:
            LeadNotFoundError: no such lead.
            AnalysisNotPossibleError: lead not qualified yet, closed, or has no
                extracted documents.
        """
        async with get_db().session() as session:
            lead_repo = LeadRepository(session)
            analysis_repo = AnalysisRepository(session)

            lead = await lead_repo.get_by_id(lead_id)
            if lead is None:
                raise LeadNotFoundError(lead_id)

            blocked = PipelineRules.analysis_blocked_reason(lead.status)
            if blocked:
                raise AnalysisNotPossibleError(blocked)

            extractions = await DocumentRepository(session).list_extractions_for_lead(lead_id)
            if not extractions:
                raise AnalysisNotPossibleError(
                    "Upload at least one document before running the analysis agent."
                )

            output = await self._agent.synthesize(lead, extractions)
            analysis = await analysis_repo.create_from_output(
                lead, output, self._agent.model_name
            )

            await lead_repo.touch_status(lead, PipelineRules.after_analysis(lead.status))

            await session.commit()
            await session.refresh(analysis)
            return analysis
