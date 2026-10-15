"""AnalysisGrounding — savings and gap claims must rest on verified document facts."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from app.agents.analysis_agent import AnalysisAgent
from app.schemas.analysis import AnalysisLLMOutput
from app.services.analysis_grounding import AnalysisGrounding


def _extraction(
    *,
    premium: str | None = "11200",
    frequency: str | None = "annual",
    premium_verified: bool | None = True,
    exclusions: list[dict[str, Any]] | None = None,
) -> Any:
    evidence: dict[str, Any] = {}
    if premium_verified is not None:
        evidence["premium_amount"] = {"verified": premium_verified}
    return SimpleNamespace(
        policy_type="Motor",
        provider="IFFCO-TOKIO",
        policy_number=None,
        insured_name=None,
        sum_insured=None,
        premium_amount=Decimal(premium) if premium else None,
        premium_frequency=frequency,
        renewal_date=None,
        exclusions=exclusions or [],
        riders=[],
        evidence=evidence,
    )


def _output(annual_inr: int, *, basis: str = "confirmed_in_document") -> AnalysisLLMOutput:
    return AnalysisLLMOutput.model_validate({
        "coverage_gaps": [{"area": "IDV", "description": "IDV low.", "severity": "medium", "basis": basis}],
        "potential_savings": {"annual_inr": annual_inr, "rationale": "Drop the Rs. 1,200 rider."},
        "risk_flags": [],
        "recommended_action": "Review IDV at renewal.",
        "confidence": 70,
    })


def test_saving_backed_by_verified_premium_is_kept() -> None:
    savings = AnalysisGrounding([_extraction()]).apply(_output(1200)).potential_savings
    assert savings.annual_inr == 1200
    assert savings.basis == "verified_premium"


def test_saving_without_premium_is_dropped() -> None:
    savings = AnalysisGrounding([_extraction(premium=None)]).apply(_output(9600)).potential_savings
    assert savings.annual_inr == 0
    assert savings.basis == "not_quantified"
    assert savings.rationale == AnalysisGrounding.NO_PREMIUM


def test_saving_on_unverified_premium_is_dropped() -> None:
    grounding = AnalysisGrounding([_extraction(premium_verified=False)])
    assert grounding.apply(_output(1200)).potential_savings.annual_inr == 0


def test_saving_larger_than_premium_is_dropped() -> None:
    savings = AnalysisGrounding([_extraction(premium="900", frequency="monthly")]).apply(
        _output(20_000)
    ).potential_savings
    # 900 x 12 = 10,800 a year, so 20,000 can't be a saving.
    assert savings.annual_inr == 0
    assert savings.rationale == AnalysisGrounding.OVER_PREMIUM


def test_extraction_from_before_checking_still_counts() -> None:
    savings = AnalysisGrounding([_extraction(premium_verified=None)]).apply(_output(1200)).potential_savings
    assert savings.basis == "verified_premium"


def test_document_backed_gap_needs_checked_facts() -> None:
    unbacked = _extraction(premium_verified=False, exclusions=[{"text": "x", "verified": False}])
    unbacked.evidence["policy_type"] = {"verified": False}
    gap = AnalysisGrounding([unbacked]).apply(_output(0)).coverage_gaps[0]
    assert gap.basis == "not_captured"
    gap = AnalysisGrounding([_extraction()]).apply(_output(0)).coverage_gaps[0]
    assert gap.basis == "confirmed_in_document"


def test_unknown_gap_basis_defaults_to_not_captured() -> None:
    assert _output(0, basis="definitely").coverage_gaps[0].basis == "not_captured"


def test_analysis_input_marks_unverified_facts_and_drops_unverified_items() -> None:
    agent = AnalysisAgent.__new__(AnalysisAgent)
    ext = _extraction(
        premium_verified=False,
        exclusions=[{"text": "Racing", "verified": False}, {"text": "Drunk driving", "verified": True}],
    )
    fact = agent._fact_formatter(ext)
    assert "could not be verified" in fact("premium_amount", "Rs. 11200")
    assert fact("provider", "IFFCO-TOKIO") == "IFFCO-TOKIO"

    lines: list[str] = []
    agent._append_items(lines, "Exclusions", ext.exclusions)
    assert lines == ["- Exclusions:", "  - Drunk driving", "  (1 more could not be found in the document and were left out)"]

    lines = []
    agent._append_items(lines, "Riders", [])
    assert lines == ["- Riders: none captured (not confirmed absent)"]
