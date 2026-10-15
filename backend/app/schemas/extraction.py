"""Document extraction schemas.

Two flavors:
- `DocumentExtractionLLMSchema` is what the model is instructed to return under JSON mode.
- `DocumentExtractionOut` is what the API returns to the frontend (includes id + timestamps).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MAX_EXCERPT_CHARS = 600


# --- Lenient coercion for LLM output -----------------------------------------
# The document extractor agent's JSON is validated against the models below.
# Small, predictable model slips (a page of 0 for "not found", a number where a
# string was asked for, an over-long excerpt) must not discard an otherwise
# good extraction, so they are normalised here instead of rejected.


def _page_or_none(value: Any) -> int | None:
    """Pages are 1-indexed; anything that isn't a positive int means 'unknown'."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page >= 1 else None


def _str_or_none(value: Any) -> Any:
    """Accept numbers where a string was asked for (`2500000` → `"2500000"`)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return value


class FieldEvidence(BaseModel):
    """Where a single extracted value came from in the source PDF."""

    model_config = ConfigDict(extra="allow")

    value: str | None = Field(default=None, description="The raw string the LLM saw/returned.")
    source_page: int | None = Field(default=None, ge=1)
    source_excerpt: str | None = Field(
        default=None,
        max_length=_MAX_EXCERPT_CHARS,
        description="A short verbatim excerpt proving the value.",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    # Set by `ExtractionEvidenceChecker`, never by the model: True when the
    # excerpt was found in the PDF text (and supports the value), False when
    # it wasn't, None when there is no value to check.
    verified: bool | None = None
    verification_note: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _coerce_value(cls, v: Any) -> Any:
        return _str_or_none(v)

    @field_validator("source_page", mode="before")
    @classmethod
    def _coerce_page(cls, v: Any) -> int | None:
        return _page_or_none(v)

    @field_validator("source_excerpt", mode="before")
    @classmethod
    def _truncate_excerpt(cls, v: Any) -> Any:
        if isinstance(v, str) and len(v) > _MAX_EXCERPT_CHARS:
            return v[:_MAX_EXCERPT_CHARS]
        return v

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v: Any) -> float:
        try:
            return min(1.0, max(0.0, float(v)))
        except (TypeError, ValueError):
            return 0.0


class ExclusionItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    text: str
    source_page: int | None = Field(default=None, ge=1)
    verified: bool | None = None

    @field_validator("source_page", mode="before")
    @classmethod
    def _coerce_page(cls, v: Any) -> int | None:
        return _page_or_none(v)


class RiderItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    description: str | None = None
    source_page: int | None = Field(default=None, ge=1)
    verified: bool | None = None

    @field_validator("source_page", mode="before")
    @classmethod
    def _coerce_page(cls, v: Any) -> int | None:
        return _page_or_none(v)


class DocumentExtractionLLMSchema(BaseModel):
    """The exact schema we require the model to return under JSON mode.

    Every scalar field is nullable; a missing field returns null + 0.0 confidence
    rather than a guessed value. See prompts/document_extractor_agent.md.
    """

    model_config = ConfigDict(extra="allow")

    @field_validator(
        "policy_type",
        "provider",
        "policy_number",
        "insured_name",
        "sum_insured",
        "premium_amount",
        "premium_frequency",
        "renewal_date",
        mode="before",
    )
    @classmethod
    def _coerce_scalars(cls, v: Any) -> Any:
        return _str_or_none(v)

    policy_type: str | None = Field(
        default=None, description="e.g. Health, Life, Motor, Travel"
    )
    provider: str | None = Field(default=None, description="Insurance company")
    policy_number: str | None = None
    insured_name: str | None = None
    sum_insured: str | None = Field(
        default=None, description="Numeric amount as string, e.g. '2500000' or '25,00,000'"
    )
    premium_amount: str | None = None
    premium_frequency: str | None = Field(
        default=None, description="monthly | quarterly | half_yearly | annual | single"
    )
    renewal_date: str | None = Field(
        default=None, description="ISO date YYYY-MM-DD if present"
    )
    exclusions: list[ExclusionItem] = Field(default_factory=list)
    riders: list[RiderItem] = Field(default_factory=list)
    evidence: dict[str, FieldEvidence] = Field(
        default_factory=dict,
        description="Keyed by field name above (e.g. 'policy_type', 'sum_insured').",
    )


class DocumentExtractionOut(BaseModel):
    """API-facing extraction result."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: str
    document_id: str
    policy_type: str | None = None
    provider: str | None = None
    policy_number: str | None = None
    insured_name: str | None = None
    sum_insured: Decimal | None = None
    premium_amount: Decimal | None = None
    premium_frequency: str | None = None
    renewal_date: date | None = None
    exclusions: list[dict] = Field(default_factory=list)
    riders: list[dict] = Field(default_factory=list)
    evidence: dict[str, FieldEvidence] = Field(default_factory=dict)
    model_name: str
    extraction_duration_ms: int
    created_at: datetime
