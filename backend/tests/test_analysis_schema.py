"""Round-trip test: canned analysis JSON <-> AnalysisLLMOutput."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.schemas.analysis import (
    AnalysisLLMOutput,
    CoverageGap,
    PotentialSavings,
    RiskFlag,
)

CANNED_ANALYSIS_JSON = {
    "coverage_gaps": [
        {
            "area": "critical illness",
            "description": (
                "No critical-illness cover on either policy. For a 34-year-old "
                "sole earner supporting two dependents, this is a material gap."
            ),
            "severity": "high",
        },
        {
            "area": "family floater",
            "description": "Health floater sum insured is only Rs. 5 lakh.",
            "severity": "high",
        },
    ],
    "potential_savings": {
        "annual_inr": 8400,
        "rationale": (
            "Switch to a family-floater and drop riders duplicating the base plan."
        ),
    },
    "risk_flags": [
        {
            "flag": "renewal_soon",
            "description": "Star Health floater renews on 12 Jan 2026.",
            "severity": "high",
        }
    ],
    "recommended_action": (
        "Before the 12 Jan renewal, recommend raising the Star Health floater "
        "to Rs. 20L and adding a critical-illness rider."
    ),
    "confidence": 78,
}


def test_canned_analysis_parses_cleanly() -> None:
    parsed = AnalysisLLMOutput.model_validate(CANNED_ANALYSIS_JSON)

    assert len(parsed.coverage_gaps) == 2
    assert all(isinstance(gap, CoverageGap) for gap in parsed.coverage_gaps)
    assert parsed.coverage_gaps[0].area == "critical illness"
    assert parsed.coverage_gaps[0].severity == "high"

    assert isinstance(parsed.potential_savings, PotentialSavings)
    assert parsed.potential_savings.annual_inr == 8400

    assert len(parsed.risk_flags) == 1
    assert isinstance(parsed.risk_flags[0], RiskFlag)
    assert parsed.risk_flags[0].flag == "renewal_soon"

    assert "renewal" in parsed.recommended_action
    assert 0 <= parsed.confidence <= 100


def test_round_trip_json_is_idempotent() -> None:
    """Dump -> parse -> dump produces the same shape."""
    parsed = AnalysisLLMOutput.model_validate(CANNED_ANALYSIS_JSON)
    dumped = parsed.model_dump(mode="json")

    reparsed = AnalysisLLMOutput.model_validate(dumped)
    redumped = reparsed.model_dump(mode="json")

    assert dumped == redumped
    # And the critical semantic fields survive round-tripping.
    assert redumped["coverage_gaps"][0]["area"] == "critical illness"
    assert redumped["potential_savings"]["annual_inr"] == 8400
    assert redumped["recommended_action"].startswith("Before the 12 Jan")


def test_rejects_confidence_out_of_range() -> None:
    bad = dict(CANNED_ANALYSIS_JSON)
    bad["confidence"] = 150
    with pytest.raises(ValidationError):
        AnalysisLLMOutput.model_validate(bad)


def test_accepts_minimal_output() -> None:
    """The schema should tolerate an LLM that returns the required field only."""
    minimal = AnalysisLLMOutput.model_validate(
        {"recommended_action": "Review in 30 days."}
    )
    assert minimal.recommended_action == "Review in 30 days."
    assert minimal.coverage_gaps == []
    assert minimal.risk_flags == []
    assert minimal.potential_savings.annual_inr == 0
    assert minimal.confidence == 0


def test_canned_payload_serializes_to_valid_json_string() -> None:
    """model_dump_json produces output that re-parses via json.loads."""
    parsed = AnalysisLLMOutput.model_validate(CANNED_ANALYSIS_JSON)
    text = parsed.model_dump_json()
    loaded = json.loads(text)
    assert loaded["coverage_gaps"][1]["area"] == "family floater"
