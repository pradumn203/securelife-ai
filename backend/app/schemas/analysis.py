"""Analysis synthesis schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

GapBasis = Literal["confirmed_in_document", "not_captured", "client_profile"]
SavingsBasis = Literal["verified_premium", "not_quantified"]


class CoverageGap(BaseModel):
    model_config = ConfigDict(extra="allow")
    area: str = Field(description="e.g. 'critical illness', 'personal accident'")
    description: str
    severity: Literal["low", "medium", "high"] = "medium"
    # Where the gap comes from. "not_captured" means the extraction doesn't
    # mention it — the policy may still have it — so the broker confirms it
    # with the client rather than calling it absent.
    basis: GapBasis = "not_captured"

    @field_validator("basis", mode="before")
    @classmethod
    def _unknown_basis_is_not_captured(cls, v: Any) -> Any:
        allowed = ("confirmed_in_document", "not_captured", "client_profile")
        return v if v in allowed else "not_captured"


class PotentialSavings(BaseModel):
    model_config = ConfigDict(extra="allow")
    annual_inr: int = Field(default=0, ge=0)
    rationale: str = ""
    # Set by `AnalysisGrounding`, never by the model: a non-zero figure is only
    # kept when a verified premium in the documents can support it.
    basis: SavingsBasis = "not_quantified"


class RiskFlag(BaseModel):
    model_config = ConfigDict(extra="allow")
    flag: str = Field(description="Short label, e.g. 'under_insured'")
    description: str
    severity: Literal["low", "medium", "high"] = "medium"


class AnalysisLLMOutput(BaseModel):
    """Schema we require the model to produce for an analysis call."""

    model_config = ConfigDict(extra="allow")

    coverage_gaps: list[CoverageGap] = Field(default_factory=list)
    potential_savings: PotentialSavings = Field(default_factory=PotentialSavings)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    recommended_action: str = Field(
        description="One-to-two sentence next step for the broker."
    )
    confidence: int = Field(default=0, ge=0, le=100)


class AnalysisOut(BaseModel):
    """API-facing analysis resource."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: str
    lead_id: str
    coverage_gaps: list[CoverageGap] = Field(default_factory=list)
    potential_savings: PotentialSavings = Field(default_factory=PotentialSavings)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    recommended_action: str
    confidence: int
    model_name: str
    created_at: datetime


class AnalysisGenerateIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    lead_id: str
