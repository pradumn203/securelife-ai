"""AnalysisRepository - persistence for synthesized broker analyses.

Used by:
  * `AnalysisOrchestrator` (create + fetch).
  * `app.routers.analysis` (fetch latest).

The repo stays thin: query encapsulation only, no LLM logic, no
status transitions on the parent Lead. The orchestrator owns the
cross-aggregate rules.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_models.analysis import Analysis
from app.data_models.lead import Lead
from app.schemas.analysis import AnalysisLLMOutput


class AnalysisRepository:
    """SQLAlchemy query encapsulation for the Analysis aggregate."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, analysis_id: str) -> Analysis | None:
        return await self._session.get(Analysis, analysis_id)

    async def latest_for_lead(self, lead_id: str) -> Analysis | None:
        """Return the most recent Analysis row for `lead_id`, or None."""
        stmt = (
            select(Analysis)
            .where(Analysis.lead_id == lead_id)
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_lead(self, lead_id: str, *, limit: int = 20) -> list[Analysis]:
        """Return all analyses for a lead, newest first."""
        stmt = (
            select(Analysis)
            .where(Analysis.lead_id == lead_id)
            .order_by(Analysis.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_from_output(
        self,
        lead: Lead,
        output: AnalysisLLMOutput,
        model_name: str,
    ) -> Analysis:
        """Persist a new Analysis row built from the LLM output.

        Caller is responsible for committing the transaction.
        """
        analysis = Analysis(
            lead_id=lead.id,
            coverage_gaps=[gap.model_dump() for gap in output.coverage_gaps],
            potential_savings=output.potential_savings.model_dump(),
            risk_flags=[flag.model_dump() for flag in output.risk_flags],
            recommended_action=output.recommended_action,
            confidence=max(0, min(100, int(output.confidence))),
            model_name=model_name,
            raw_llm_response=output.model_dump(mode="json"),
        )
        self._session.add(analysis)
        await self._session.flush()
        return analysis
