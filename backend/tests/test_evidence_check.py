"""ExtractionEvidenceChecker — citations are verified against the PDF text."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.schemas.extraction import DocumentExtractionLLMSchema
from app.services.evidence_check import ExtractionEvidenceChecker

PAGES = [
    # Page 1: the schedule, laid out the way PDF text layers usually come out.
    "IFFCO-TOKIO GENERAL INSURANCE CO. LTD.\n"
    "Private Car Package Policy - Schedule\n"
    "Policy No.: 1-2ABC34DE   Insured: Rohan\nGupta\n"
    "Period of Insurance: 15-Feb-2025 to 14-Feb-2026\n"
    "Insured Declared Value (IDV): ₹ 5,80,000\n"
    "Total Premium Payable: Rs. 11,200 (annual)",
    # Page 2: exclusions and add-ons.
    "Exclusions\n"
    "Damage caused while driving under the influence of alcohol or drugs.\n"
    "Consequential loss, wear and tear, mechanical break-\ndown.\n"
    "Add-on covers: Zero Depreciation Cover",
    # Page 3: a scanned page with no text layer.
    "",
]


def _extraction(**overrides: object) -> DocumentExtractionLLMSchema:
    payload: dict = {
        "policy_type": "Motor",
        "provider": "IFFCO-TOKIO GENERAL INSURANCE CO. LTD.",
        "policy_number": "1-2ABC34DE",
        "sum_insured": "580000",
        "premium_amount": "11200",
        "premium_frequency": "annual",
        "renewal_date": "2026-02-14",
        "evidence": {
            "policy_type": {"value": "Private Car", "source_page": 1,
                            "source_excerpt": "Private Car Package Policy", "confidence": 0.9},
            "provider": {"value": "IFFCO-TOKIO", "source_page": 1,
                         "source_excerpt": "IFFCO-TOKIO GENERAL INSURANCE CO. LTD.", "confidence": 0.95},
            "policy_number": {"value": "1-2ABC34DE", "source_page": 1,
                              "source_excerpt": "Policy No.: 1-2ABC34DE", "confidence": 0.95},
            "sum_insured": {"value": "₹ 5,80,000", "source_page": 1,
                            "source_excerpt": "Insured Declared Value (IDV): ₹ 5,80,000", "confidence": 0.95},
            "premium_amount": {"value": "Rs. 11,200", "source_page": 1,
                               "source_excerpt": "Total Premium Payable: Rs. 11,200", "confidence": 0.9},
            "premium_frequency": {"value": "annual", "source_page": 1,
                                  "source_excerpt": "Rs. 11,200 (annual)", "confidence": 0.9},
            "renewal_date": {"value": "14-Feb-2026", "source_page": 1,
                             "source_excerpt": "Period of Insurance: 15-Feb-2025 to 14-Feb-2026",
                             "confidence": 0.9},
        },
        "exclusions": [
            {"text": "Driving under the influence of alcohol or drugs", "source_page": 2},
        ],
        "riders": [{"name": "Zero Depreciation Cover", "source_page": 2}],
    }
    for key, value in overrides.items():
        if key.startswith("ev_"):
            payload["evidence"][key[3:]].update(value)  # type: ignore[arg-type]
        else:
            payload[key] = value
    return DocumentExtractionLLMSchema.model_validate(payload)


def _check(parsed: DocumentExtractionLLMSchema) -> DocumentExtractionLLMSchema:
    return ExtractionEvidenceChecker(PAGES).check(parsed)


def test_genuine_citations_are_verified() -> None:
    checked = _check(_extraction())
    assert {k: ev.verified for k, ev in checked.evidence.items()} == dict.fromkeys(
        checked.evidence, True
    )
    assert checked.exclusions[0].verified is True
    assert checked.riders[0].verified is True


def test_reflowed_text_still_matches() -> None:
    # The page breaks "Rohan\nGupta" across lines; the excerpt doesn't.
    checked = _check(_extraction(
        insured_name="Rohan Gupta",
        evidence={"insured_name": {"value": "Rohan Gupta", "source_page": 1,
                                   "source_excerpt": "Insured: Rohan Gupta", "confidence": 0.9}},
    ))
    assert checked.evidence["insured_name"].verified is True


def test_fabricated_excerpt_is_flagged_and_confidence_capped() -> None:
    checked = _check(_extraction(ev_sum_insured={
        "source_excerpt": "Sum Insured: Rs. 25,00,000 (Twenty-Five Lakhs only)", "confidence": 0.95,
    }))
    ev = checked.evidence["sum_insured"]
    assert ev.verified is False
    assert ev.confidence == ExtractionEvidenceChecker.UNVERIFIED_CONFIDENCE_CAP
    assert "not found" in (ev.verification_note or "")


def test_real_excerpt_that_does_not_support_the_value_is_flagged() -> None:
    # A genuine sentence from the policy, but the amount is wrong.
    checked = _check(_extraction(sum_insured="2500000"))
    assert checked.evidence["sum_insured"].verified is False
    assert "does not contain this value" in (checked.evidence["sum_insured"].verification_note or "")


def test_wrong_page_is_corrected() -> None:
    checked = _check(_extraction(ev_provider={"source_page": 2}))
    ev = checked.evidence["provider"]
    assert ev.verified is True
    assert ev.source_page == 1
    assert ev.verification_note == "Cited page 2; found on page 1."


def test_page_out_of_range_is_corrected_or_flagged() -> None:
    checked = _check(_extraction(ev_policy_number={"source_page": 40}))
    assert checked.evidence["policy_number"].verified is True
    assert checked.evidence["policy_number"].source_page == 1


def test_value_without_evidence_is_flagged() -> None:
    checked = _check(_extraction(insured_name="Rohan Gupta"))
    assert checked.evidence["insured_name"].verified is False
    assert checked.evidence["insured_name"].confidence == 0.0


def test_null_value_needs_no_check() -> None:
    checked = _check(_extraction(insured_name=None))
    assert "insured_name" not in checked.evidence or checked.evidence["insured_name"].verified is None


def test_shortened_excerpt_with_ellipsis_matches_in_order() -> None:
    checked = _check(_extraction(ev_renewal_date={
        "source_excerpt": "Period of Insurance: ... to 14-Feb-2026",
    }))
    assert checked.evidence["renewal_date"].verified is True


def test_invented_list_items_are_flagged() -> None:
    checked = _check(_extraction(
        exclusions=[
            {"text": "Wear and tear, mechanical breakdown", "source_page": 1},
            {"text": "Racing, speed testing and rallies", "source_page": 2},
        ],
        riders=[{"name": "Engine Protect", "source_page": 2}],
    ))
    assert checked.exclusions[0].verified is True
    assert checked.exclusions[0].source_page == 2  # corrected
    assert checked.exclusions[1].verified is False
    assert checked.riders[0].verified is False


def test_every_page_scanned_means_nothing_verifies() -> None:
    checked = ExtractionEvidenceChecker(["", ""]).check(_extraction())
    assert not any(ev.verified for ev in checked.evidence.values())


def test_amount_and_date_parsing() -> None:
    amounts = ExtractionEvidenceChecker.amounts_in("Sum insured Rs. 25 Lakhs; top-up 1.5 Crore; fee 2,500")
    assert {Decimal(2_500_000), Decimal(15_000_000), Decimal(2_500)} <= set(amounts)
    dates = ExtractionEvidenceChecker.dates_in(
        "valid 12/04/2026, renews 11-Apr-2026 or April 11, 2026 or 2026-04-11 or 11th April 2026"
    )
    assert dates == {date(2026, 4, 12), date(2026, 4, 11)}
