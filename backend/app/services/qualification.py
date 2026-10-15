"""Qualification — deterministic guardrails around the qualification agent.

The broker clicks "Run qualification agent". The flow:

1. **Gate (no tokens spent).** Name, email/phone and insurance type must be
   captured (`REQUIRED_TO_QUALIFY`), else `QualificationBlocked` (HTTP 400
   with the missing labels). Intent and timeline don't block: the agent sees
   them as NOT CAPTURED and judges urgency from the transcript. Analysed or
   closed leads raise `QualificationNotAllowed` (HTTP 409).
2. **Agent.** `QualificationAgent` scores five dimensions 0-5, each with a
   verbatim quote from the prospect, and proposes a verdict.
3. **Finalise (`QualificationScorer`).**
   * Every quote is checked against the prospect's own messages; an
     unverifiable quote is dropped and that dimension is capped at
     `UNVERIFIED_SCORE_CAP` — the model can't earn points it can't cite.
   * The overall 0-100 score is computed here from the dimension scores,
     never taken from the model.
   * A QUALIFIED verdict is downgraded to NEEDS_MORE_INFO when the score is
     under the threshold or insurance-type details are still missing.
   * Dealbreakers (guaranteed returns, refusing any premium, …) are checked
     the same way; any verified dealbreaker makes the verdict NOT_QUALIFIED,
     an unverifiable one is dropped. Models hedge on obvious bad fits, so
     the agent only has to *spot* the problem — the code decides.
   * A NEEDS_MORE_INFO verdict also becomes NOT_QUALIFIED when the score is
     under `qualification_reject_below` and the agent raised red flags.
4. **Persist.** A `Qualification` row is stored, the lead's score and verdict
   are updated, and `PipelineRules.after_qualification` moves the lead to
   In progress (or straight to Documents pending review if the prospect has
   already shared documents). The verdict never closes a lead by itself —
   closing as disqualified is the broker's call.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.agents.qualification_agent import QualificationAgent
from app.data_models.conversation_message import MessageRole
from app.data_models.qualification import Qualification
from app.db import get_db
from app.repositories.conversations import ConversationMessageRepository
from app.repositories.documents import DocumentRepository
from app.repositories.leads import LeadRepository
from app.repositories.qualifications import QualificationRepository
from app.schemas.qualification import (
    DIMENSIONS,
    MAX_DIMENSION_SCORE,
    Dealbreaker,
    DimensionAssessment,
    QualificationLLMOutput,
    Verdict,
)
from app.services.pipeline import PipelineRules
from app.services.question_plan import QuestionPlan
from app.settings import get_settings

_MAX_RED_FLAGS = 5
_MAX_FOLLOW_UPS = 3


class QualificationBlocked(RuntimeError):
    """Name, contact or insurance type is missing; the agent is not called."""

    def __init__(self, missing: tuple[str, ...]) -> None:
        super().__init__(
            "The prospect hasn't shared enough to qualify yet — missing: " + ", ".join(missing)
        )
        self.missing = missing


class QualificationNotAllowed(RuntimeError):
    """The lead is already past the qualification step."""


class LeadNotFoundError(LookupError):
    """The lead id doesn't resolve."""


@dataclass(frozen=True)
class FinalQualification:
    verdict: Verdict
    score: int
    dimensions: list[DimensionAssessment]
    dealbreakers: list[Dealbreaker]
    red_flags: list[str]
    follow_up_questions: list[str]
    missing_details: list[str]
    summary: str


class QualificationScorer:
    """Pure post-processing of the agent's output. No I/O; unit-tested."""

    UNVERIFIED_SCORE_CAP = 3

    def __init__(self, threshold: int | None = None, reject_below: int | None = None) -> None:
        settings = get_settings()
        self._threshold = threshold if threshold is not None else settings.qualification_threshold
        self._reject_below = (
            reject_below if reject_below is not None else settings.qualification_reject_below
        )

    @property
    def threshold(self) -> int:
        return self._threshold

    def finalize(
        self,
        output: QualificationLLMOutput,
        *,
        prospect_text: str,
        missing_details: list[str],
    ) -> FinalQualification:
        dimensions = self._verified_dimensions(output.dimensions, prospect_text)
        dealbreakers = self._verified_dealbreakers(output.dealbreakers, prospect_text)
        score = round(
            100 * sum(d.score for d in dimensions) / (MAX_DIMENSION_SCORE * len(DIMENSIONS))
        )

        red_flags = _clean_list(output.red_flags, _MAX_RED_FLAGS)
        verdict: Verdict = output.verdict
        if verdict == "QUALIFIED" and (score < self._threshold or missing_details):
            verdict = "NEEDS_MORE_INFO"
        if verdict == "NEEDS_MORE_INFO" and score < self._reject_below and red_flags:
            verdict = "NOT_QUALIFIED"
        if dealbreakers:
            verdict = "NOT_QUALIFIED"

        follow_ups = _clean_list(output.follow_up_questions, _MAX_FOLLOW_UPS)
        if verdict == "NEEDS_MORE_INFO" and not follow_ups:
            follow_ups = [
                f"Ask the prospect about: {label.lower()}."
                for label in missing_details[:_MAX_FOLLOW_UPS]
            ]

        return FinalQualification(
            verdict=verdict,
            score=score,
            dimensions=dimensions,
            dealbreakers=dealbreakers,
            red_flags=red_flags,
            follow_up_questions=follow_ups,
            missing_details=list(missing_details),
            summary=output.summary.strip() or self._fallback_summary(verdict, dimensions),
        )

    @staticmethod
    def _fallback_summary(verdict: Verdict, dimensions: list[DimensionAssessment]) -> str:
        """Deterministic one-liner when the model omits `summary`."""
        strongest = max(dimensions, key=lambda d: d.score)
        weakest = min(dimensions, key=lambda d: d.score)
        return (
            f"{verdict.replace('_', ' ').capitalize()}. "
            f"Strongest signal: {DIMENSIONS[strongest.key].lower()} ({strongest.score}/5); "
            f"weakest: {DIMENSIONS[weakest.key].lower()} ({weakest.score}/5)."
        )

    def _verified_dealbreakers(
        self, proposed: list[Dealbreaker], prospect_text: str
    ) -> list[Dealbreaker]:
        """Keep only dealbreakers whose quote really is the prospect's words."""
        haystack = self.normalize(prospect_text)
        verified: list[Dealbreaker] = []
        for item in proposed:
            quote = item.evidence_quote
            if item.reason.strip() and quote and self.normalize(quote) in haystack:
                verified.append(
                    Dealbreaker(reason=item.reason.strip(), evidence_quote=quote, evidence_verified=True)
                )
        return verified[:_MAX_RED_FLAGS]

    def _verified_dimensions(
        self, proposed: list[DimensionAssessment], prospect_text: str
    ) -> list[DimensionAssessment]:
        """Exactly one assessment per known dimension, in canonical order."""
        haystack = self.normalize(prospect_text)
        by_key: dict[str, DimensionAssessment] = {}
        for item in proposed:
            if item.key in DIMENSIONS and item.key not in by_key:
                by_key[item.key] = item

        result: list[DimensionAssessment] = []
        for key in DIMENSIONS:
            item = by_key.get(key)
            if item is None:
                result.append(
                    DimensionAssessment(key=key, score=0, rationale="Not assessed by the agent.")
                )
                continue
            quote = item.evidence_quote
            verified = bool(quote) and self.normalize(quote) in haystack
            score = item.score if verified else min(item.score, self.UNVERIFIED_SCORE_CAP)
            result.append(
                DimensionAssessment(
                    key=key,
                    score=score,
                    rationale=item.rationale.strip(),
                    evidence_quote=quote if verified else None,
                    evidence_verified=verified,
                )
            )
        return result

    @staticmethod
    def normalize(text: str) -> str:
        """Case/whitespace/quote-insensitive form for substring matching."""
        text = text.lower()
        text = text.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'}))
        text = re.sub(r"\s+", " ", text)
        return text.strip(" \"'.,!?…")


class QualificationOrchestrator:
    """Gate → agent → scorer → persist."""

    def __init__(
        self,
        *,
        agent_factory: Callable[[], QualificationAgent],
        scorer: QualificationScorer,
    ) -> None:
        # A factory, so the gate's 400/409 responses work even when the
        # Groq client can't be built (e.g. no API key in a dev setup).
        self._agent_factory = agent_factory
        self._scorer = scorer

    async def qualify(self, lead_id: str) -> Qualification:
        async with get_db().session() as session:
            leads = LeadRepository(session)
            lead = await leads.get_by_id(lead_id)
            if lead is None:
                raise LeadNotFoundError(lead_id)
            if not PipelineRules.can_qualify(lead.status):
                raise QualificationNotAllowed(
                    "Qualification can't be re-run once a prospect is analysed or closed."
                )

            plan = QuestionPlan.for_lead(lead)
            missing_required = plan.missing_required_to_qualify()
            if missing_required:
                raise QualificationBlocked(tuple(item.label for item in missing_required))

            messages = await ConversationMessageRepository(session).list_for_lead(
                lead_id, include_system=False
            )
            agent = self._agent_factory()
            output = await agent.assess(lead, messages)

            prospect_text = "\n".join(m.content for m in messages if m.role == MessageRole.USER)
            final = self._scorer.finalize(
                output,
                prospect_text=prospect_text,
                missing_details=[item.label for item in plan.missing_details()],
            )

            row = await QualificationRepository(session).create(
                lead_id=lead.id,
                verdict=final.verdict,
                score=final.score,
                dimensions=final.dimensions,
                dealbreakers=final.dealbreakers,
                red_flags=final.red_flags,
                follow_up_questions=final.follow_up_questions,
                missing_details=final.missing_details,
                summary=final.summary,
                model_name=agent.model_name,
                raw_llm_response=output.model_dump(mode="json"),
            )
            lead.qualification_score = final.score
            lead.qualification_verdict = final.verdict
            has_documents = await DocumentRepository(session).count_for_lead(lead_id) > 0
            await leads.touch_status(
                lead,
                PipelineRules.after_qualification(
                    lead.status, has_documents=has_documents, verdict=final.verdict
                ),
            )
            await session.commit()
            await session.refresh(row)
            return row


def _clean_list(items: list[str], limit: int) -> list[str]:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return cleaned[:limit]
