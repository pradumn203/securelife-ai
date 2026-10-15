"""Pydantic schemas for the Lead resource."""
from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, computed_field, field_validator

from app.schemas.enums import CloseReason, LeadSource, LeadStatus
from app.services.question_plan import QuestionPlan

if TYPE_CHECKING:
    from app.schemas.analysis import AnalysisOut
    from app.schemas.chat import ChatMessageOut
    from app.schemas.document import DocumentOut
    from app.schemas.qualification import QualificationOut


class LeadExtractedFields(BaseModel):
    """Structured fields the chat extractor agent captures incrementally.

    Which of these the chat agent actually asks for depends on the prospect's
    `insurance_type` — see `app.services.question_plan.PLANS`.
    """

    model_config = ConfigDict(extra="allow")

    # --- Insurance intent ---
    insurance_type: str | None = Field(
        default=None,
        description=(
            "What product category they're looking for. "
            "One of: health | life_term | life_whole | motor | home | travel | "
            "investment_linked | multiple | other"
        ),
    )
    intent: str | None = Field(
        default=None, description="new_policy | review_existing | claim_help | other"
    )
    timeline: str | None = Field(
        default=None, description="now | lt_3mo | gt_3mo | undecided"
    )

    # --- Demographics / household ---
    age: int | None = None
    dependents: int | None = None
    occupation: str | None = Field(
        default=None, description="Free-text job title / profession"
    )
    income_band: str | None = Field(
        default=None, description="e.g. '<5L', '5-15L', '15-30L', '>30L' (INR per annum)"
    )

    # --- Health & lifestyle (material for life / health underwriting) ---
    smoker: bool | None = Field(
        default=None, description="True if the prospect uses tobacco in any form."
    )
    health_conditions: str | None = Field(
        default=None,
        description=(
            "Short free-text of relevant conditions (e.g. 'diabetes, hypertension'), "
            "or the literal string 'none' when the prospect explicitly denies any."
        ),
    )

    # --- Risk & existing cover ---
    existing_cover: str | None = Field(
        default=None, description="Free-text summary of current coverage"
    )
    risk_appetite: str | None = Field(default=None, description="low | medium | high")

    # --- Type-specific plan answers (free text, in the prospect's terms) ---
    members_to_cover: str | None = Field(default=None, description="health / multiple: who to cover + ages")
    budget: str | None = Field(default=None, description="Premium budget or target cover, INR")
    goal: str | None = Field(default=None, description="life_whole / investment_linked: what the money is for")
    horizon: str | None = Field(default=None, description="life_whole / investment_linked: years invested")
    vehicle: str | None = Field(default=None, description="motor: make, model, year")
    policy_expiry: str | None = Field(default=None, description="motor: 'new vehicle' or current expiry date")
    recent_claims: str | None = Field(default=None, description="motor: claims in the last policy year")
    home_ownership: str | None = Field(default=None, description="home: own | rent")
    property_value: str | None = Field(default=None, description="home: property type + rough value")
    contents_value: str | None = Field(default=None, description="home: rough value of contents")
    destination: str | None = Field(default=None, description="travel: destination")
    trip_dates: str | None = Field(default=None, description="travel: dates / duration")
    travellers: str | None = Field(default=None, description="travel: number + ages")
    products_wanted: str | None = Field(default=None, description="multiple: products + priority")
    need_description: str | None = Field(default=None, description="other: what they need covered")

    @field_validator("*", mode="before")
    @classmethod
    def _lenient_scalars(cls, v: Any, info: ValidationInfo) -> Any:
        """Absorb predictable model slips instead of discarding the whole turn:
        a number for a text field (`25000` → `"25000"`), or prose for a count
        (`"2 kids"` → `2`, `"none"` → `None`)."""
        field = cls.model_fields.get(info.field_name or "")
        if field is None:
            return v
        if field.annotation == (str | None) and isinstance(v, (int, float)) and not isinstance(v, bool):
            return str(v)
        if field.annotation == (int | None) and isinstance(v, str):
            match = re.search(r"\d+", v)
            return int(match.group()) if match else None
        return v

    # --- Conversation-flow flags (not scored) ---
    wants_to_upload: bool | None = Field(
        default=None,
        description=(
            "True after the user has been invited to upload existing policy PDFs "
            "AND has affirmed. False only if they explicitly declined. Null "
            "otherwise. Drives whether the prospect UI reveals the upload card."
        ),
    )


class ProfileChecklistItem(BaseModel):
    """One fact from the prospect's question plan and whether it's captured."""

    model_config = ConfigDict(extra="allow")

    key: str
    label: str
    group: Literal["core", "details"]
    value: str | None = None
    captured: bool


class LeadOut(BaseModel):
    """Lead resource as returned by the API."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: str
    created_at: datetime
    updated_at: datetime
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    status: LeadStatus
    source: LeadSource
    qualification_score: int = Field(
        description="0-100 score from the latest qualification agent run; 0 until it has run."
    )
    qualification_verdict: Literal["QUALIFIED", "NOT_QUALIFIED", "NEEDS_MORE_INFO"] | None = Field(
        default=None, description="Verdict of the latest qualification agent run; null until it has run."
    )
    close_reason: CloseReason | None = Field(
        default=None, description="Why the broker closed the lead. Set only when status is CLOSED."
    )
    close_note: str | None = Field(
        default=None, description="Broker's free-text note on the closure."
    )
    extracted_fields: LeadExtractedFields = Field(default_factory=LeadExtractedFields)
    conversation_summary: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def profile_checklist(self) -> list[ProfileChecklistItem]:
        """The prospect's question plan (core + insurance-type details)."""
        return [
            ProfileChecklistItem(
                key=item.key,
                label=item.label,
                group=item.group,  # type: ignore[arg-type]
                value=item.value,
                captured=item.captured,
            )
            for item in QuestionPlan.for_lead(self).checklist()
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def profile_completeness(self) -> int:
        """Percent of the question plan captured so far (0-100)."""
        return QuestionPlan.for_lead(self).completeness()


class LeadUpdate(BaseModel):
    """PATCH payload for a lead (broker-side edits)."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    status: LeadStatus | None = None
    close_reason: CloseReason | None = Field(
        default=None,
        description="Required when moving a lead to CLOSED (unless it already has one).",
    )
    close_note: str | None = Field(default=None, description="Why it was closed, in the broker's words.")
    conversation_summary: str | None = None
    extracted_fields: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Merged key-by-key into the lead's extracted fields, so the broker can "
            "correct what the chat captured (e.g. insurance_type, intent, timeline). "
            "A null or empty-string value clears that field."
        ),
    )


class LeadDetailOut(LeadOut):
    """`LeadOut` plus the collections the LeadDetailPage renders.

    This is a strict superset of `LeadOut` so a client that only
    knows about `LeadOut` keeps working.
    """

    model_config = ConfigDict(from_attributes=True, extra="allow")

    messages: list[ChatMessageOut] = Field(default_factory=list)
    documents: list[DocumentOut] = Field(default_factory=list)
    latest_qualification: QualificationOut | None = None
    latest_analysis: AnalysisOut | None = None


_lead_detail_rebuilt = False


def ensure_lead_detail_rebuilt() -> None:
    """Resolve forward refs on `LeadDetailOut`. Idempotent.

    Separate function (rather than module-top-level) because
    `app.schemas.chat` depends on `LeadExtractedFields` defined in
    this module, so importing it during this module's own execution
    would be a circular dependency. Callers that intend to validate
    into `LeadDetailOut` import this helper and call it first.
    """
    global _lead_detail_rebuilt
    if _lead_detail_rebuilt:
        return
    from app.schemas.analysis import AnalysisOut
    from app.schemas.chat import ChatMessageOut
    from app.schemas.document import DocumentOut
    from app.schemas.qualification import QualificationOut

    globals()["AnalysisOut"] = AnalysisOut
    globals()["ChatMessageOut"] = ChatMessageOut
    globals()["DocumentOut"] = DocumentOut
    globals()["QualificationOut"] = QualificationOut
    LeadDetailOut.model_rebuild(force=True)
    _lead_detail_rebuilt = True
