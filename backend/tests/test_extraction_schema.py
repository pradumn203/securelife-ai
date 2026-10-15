"""Round-trip a canned LLM-shaped payload through DocumentExtractionLLMSchema.

Guards against future schema drift that would silently drop evidence or
mis-parse the LLM response. Also exercises the Decimal/date coercion helpers
in the DocumentRepository so an evolving extraction model doesn't quietly
break persistence.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from app.repositories.documents import _to_decimal, _to_iso_date
from app.schemas.extraction import DocumentExtractionLLMSchema

CANNED_LLM_JSON = """
{
  "policy_type": "Health",
  "provider": "HDFC ERGO General Insurance",
  "policy_number": "H-2026-0098712",
  "insured_name": "Priya Sharma",
  "sum_insured": "2500000",
  "premium_amount": "28400",
  "premium_frequency": "annual",
  "renewal_date": "2026-11-30",
  "exclusions": [
    {"text": "Any treatment arising from war or war-like operations.", "source_page": 7},
    {"text": "Cosmetic or aesthetic surgery.", "source_page": 7}
  ],
  "riders": [
    {"name": "Critical Illness Rider", "description": "Covers 20 critical illnesses.", "source_page": 3},
    {"name": "Hospital Cash", "description": null, "source_page": 3}
  ],
  "evidence": {
    "policy_type": {
      "value": "Health",
      "source_page": 1,
      "source_excerpt": "Product: Optima Secure (Health Insurance)",
      "confidence": 0.98
    },
    "provider": {
      "value": "HDFC ERGO General Insurance Company Ltd.",
      "source_page": 1,
      "source_excerpt": "HDFC ERGO General Insurance Company Ltd.",
      "confidence": 0.99
    },
    "policy_number": {
      "value": "H-2026-0098712",
      "source_page": 1,
      "source_excerpt": "Policy No.: H-2026-0098712",
      "confidence": 0.97
    },
    "insured_name": {
      "value": "Priya Sharma",
      "source_page": 1,
      "source_excerpt": "Primary Insured: Priya Sharma",
      "confidence": 0.95
    },
    "sum_insured": {
      "value": "Rs. 25,00,000",
      "source_page": 2,
      "source_excerpt": "Sum Insured: Rs. 25,00,000 (Twenty-Five Lakhs)",
      "confidence": 0.96
    },
    "premium_amount": {
      "value": "28,400",
      "source_page": 2,
      "source_excerpt": "Annual Premium: Rs. 28,400 (incl. GST)",
      "confidence": 0.92
    },
    "premium_frequency": {
      "value": "annual",
      "source_page": 2,
      "source_excerpt": "Premium Frequency: Yearly",
      "confidence": 0.9
    },
    "renewal_date": {
      "value": "30-Nov-2026",
      "source_page": 1,
      "source_excerpt": "Policy Period: 01-Dec-2025 to 30-Nov-2026",
      "confidence": 0.93
    }
  }
}
"""


def test_round_trips_canned_payload() -> None:
    payload = json.loads(CANNED_LLM_JSON)
    parsed = DocumentExtractionLLMSchema.model_validate(payload)

    assert parsed.policy_type == "Health"
    assert parsed.provider == "HDFC ERGO General Insurance"
    assert parsed.policy_number == "H-2026-0098712"
    assert parsed.insured_name == "Priya Sharma"
    assert parsed.sum_insured == "2500000"
    assert parsed.premium_amount == "28400"
    assert parsed.premium_frequency == "annual"
    assert parsed.renewal_date == "2026-11-30"
    assert len(parsed.exclusions) == 2
    assert parsed.exclusions[0].text.startswith("Any treatment")
    assert parsed.exclusions[0].source_page == 7
    assert len(parsed.riders) == 2
    assert parsed.riders[0].name == "Critical Illness Rider"
    assert parsed.riders[1].description is None

    ev = parsed.evidence
    assert set(ev.keys()) >= {
        "policy_type",
        "provider",
        "policy_number",
        "insured_name",
        "sum_insured",
        "premium_amount",
        "premium_frequency",
        "renewal_date",
    }
    si = ev["sum_insured"]
    assert si.source_page == 2
    assert si.confidence == 0.96
    assert "25,00,000" in si.source_excerpt


def test_null_fields_pass_through_cleanly() -> None:
    # Mimics a scanned PDF where several fields were not confidently readable.
    payload = {
        "policy_type": None,
        "provider": "Star Health",
        "policy_number": None,
        "insured_name": None,
        "sum_insured": None,
        "premium_amount": None,
        "premium_frequency": None,
        "renewal_date": None,
        "exclusions": [],
        "riders": [],
        "evidence": {
            "provider": {
                "value": "Star Health",
                "source_page": 1,
                "source_excerpt": "Star Health",
                "confidence": 0.6,
            },
            "policy_type": {
                "value": None,
                "source_page": None,
                "source_excerpt": "",
                "confidence": 0.0,
            },
        },
    }
    parsed = DocumentExtractionLLMSchema.model_validate(payload)
    assert parsed.provider == "Star Health"
    assert parsed.policy_type is None
    assert parsed.evidence["policy_type"].confidence == 0.0
    assert parsed.evidence["policy_type"].source_excerpt == ""


def test_tolerates_common_model_slips() -> None:
    # Observed live: the model cites page 0 for a field it couldn't find and
    # returns bare numbers for amounts. Neither should discard the extraction.
    payload = {
        "policy_type": "Health",
        "sum_insured": 2500000,
        "exclusions": [{"text": "Cosmetic surgery", "source_page": 0}],
        "riders": [{"name": "OPD cover", "source_page": "3"}],
        "evidence": {
            "sum_insured": {
                "value": 2500000,
                "source_page": 2,
                "source_excerpt": "x" * 900,
                "confidence": 1.4,
            },
            "policy_number": {
                "value": None,
                "source_page": 0,
                "source_excerpt": "",
                "confidence": 0.0,
            },
        },
    }
    parsed = DocumentExtractionLLMSchema.model_validate(payload)
    assert parsed.sum_insured == "2500000"
    assert parsed.exclusions[0].source_page is None
    assert parsed.riders[0].source_page == 3
    assert parsed.evidence["sum_insured"].value == "2500000"
    assert len(parsed.evidence["sum_insured"].source_excerpt) == 600
    assert parsed.evidence["sum_insured"].confidence == 1.0
    assert parsed.evidence["policy_number"].source_page is None


def test_decimal_normalization() -> None:
    assert _to_decimal("2500000") == Decimal("2500000")
    assert _to_decimal("25,00,000") == Decimal("2500000")
    assert _to_decimal("Rs. 28,400.50") == Decimal("28400.50")
    assert _to_decimal("") is None
    assert _to_decimal(None) is None
    assert _to_decimal("not a number") is None


def test_iso_date_normalization() -> None:
    assert _to_iso_date("2026-11-30") == date(2026, 11, 30)
    assert _to_iso_date("30-Nov-2026") is None  # not ISO → stays None
    assert _to_iso_date("") is None
    assert _to_iso_date(None) is None
