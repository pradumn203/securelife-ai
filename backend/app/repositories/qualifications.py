"""QualificationRepository - persistence for qualification agent runs.

Used by:
  * `QualificationOrchestrator` (create).
  * `app.routers.leads` (latest for the lead detail payload).

Query encapsulation only; verdict/score finalisation and lead status changes
belong to the orchestrator.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_models.qualification import Qualification
from app.schemas.qualification import Dealbreaker, DimensionAssessment


class QualificationRepository:
    """SQLAlchemy query encapsulation for the Qualification aggregate."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest_for_lead(self, lead_id: str) -> Qualification | None:
        """Return the most recent Qualification for `lead_id`, or None."""
        stmt = (
            select(Qualification)
            .where(Qualification.lead_id == lead_id)
            .order_by(Qualification.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def create(
        self,
        *,
        lead_id: str,
        verdict: str,
        score: int,
        dimensions: list[DimensionAssessment],
        dealbreakers: list[Dealbreaker],
        red_flags: list[str],
        follow_up_questions: list[str],
        missing_details: list[str],
        summary: str,
        model_name: str,
        raw_llm_response: dict,
    ) -> Qualification:
        """Persist a finalised qualification. Caller commits."""
        row = Qualification(
            lead_id=lead_id,
            verdict=verdict,
            score=score,
            dimensions=[d.model_dump(mode="json") for d in dimensions],
            dealbreakers=[d.model_dump(mode="json") for d in dealbreakers],
            red_flags=red_flags,
            follow_up_questions=follow_up_questions,
            missing_details=missing_details,
            summary=summary,
            model_name=model_name,
            raw_llm_response=raw_llm_response,
        )
        self._session.add(row)
        await self._session.flush()
        return row
