"""Qualification agent schemas.

`QualificationLLMOutput` is what the agent returns under JSON mode.
`QualificationOut` is the persisted, server-finalised result the API returns:
the overall score and the final verdict are computed by
`QualificationOrchestrator`, never taken verbatim from the model.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Verdict = Literal["QUALIFIED", "NOT_QUALIFIED", "NEEDS_MORE_INFO"]

# The five dimensions every qualification is scored on, with broker-facing labels.
DIMENSIONS: dict[str, str] = {
    "need_clarity": "Need clarity",
    "urgency": "Urgency",
    "budget_fit": "Budget fit",
    "coverage_gap": "Coverage gap",
    "engagement": "Engagement",
}
MAX_DIMENSION_SCORE = 5


class DimensionAssessment(BaseModel):
    """One dimension of the qualification, scored 0-5 with cited evidence."""

    model_config = ConfigDict(extra="allow")

    key: str
    score: int = Field(default=0, ge=0, le=MAX_DIMENSION_SCORE)
    rationale: str = ""
    evidence_quote: str | None = Field(
        default=None,
        description="Verbatim words from the prospect's own messages supporting the score.",
    )
    evidence_verified: bool = Field(
        default=False,
        description="Set server-side: True only if the quote really appears in the transcript.",
    )

    @field_validator("score", mode="before")
    @classmethod
    def _clamp_score(cls, v: Any) -> int:
        try:
            return max(0, min(MAX_DIMENSION_SCORE, round(float(v))))
        except (TypeError, ValueError):
            return 0

    @field_validator("evidence_quote", mode="before")
    @classmethod
    def _blank_quote_is_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class Dealbreaker(BaseModel):
    """Something the prospect said that makes them unsuitable regardless of score.

    Must quote the prospect verbatim; the server drops any it can't verify.
    """

    model_config = ConfigDict(extra="allow")

    reason: str
    evidence_quote: str | None = None
    evidence_verified: bool = Field(
        default=False,
        description="Set server-side: True only if the quote really appears in the transcript.",
    )

    @field_validator("evidence_quote", mode="before")
    @classmethod
    def _blank_quote_is_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


class QualificationLLMOutput(BaseModel):
    """Schema the qualification agent must return under JSON mode."""

    model_config = ConfigDict(extra="allow")

    verdict: Verdict = "NEEDS_MORE_INFO"
    dimensions: list[DimensionAssessment] = Field(default_factory=list)
    dealbreakers: list[Dealbreaker] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    summary: str = ""

    @field_validator("verdict", mode="before")
    @classmethod
    def _normalise_verdict(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().upper().replace(" ", "_").replace("-", "_")
        return v


class QualificationOut(BaseModel):
    """API-facing qualification result."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: str
    lead_id: str
    verdict: Verdict
    score: int
    dimensions: list[DimensionAssessment] = Field(default_factory=list)
    dealbreakers: list[Dealbreaker] = Field(
        default_factory=list,
        description="Verified dealbreakers only; any one makes the verdict NOT_QUALIFIED.",
    )
    red_flags: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    missing_details: list[str] = Field(default_factory=list)
    summary: str = ""
    model_name: str
    created_at: datetime


class QualificationBlockedDetail(BaseModel):
    """400 body when name, contact or insurance type is missing — the agent is not called."""

    message: str
    missing: list[str]
