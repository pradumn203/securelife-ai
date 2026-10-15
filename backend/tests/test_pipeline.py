"""PipelineRules — every lead stage transition, pure and table-driven."""
from __future__ import annotations

import pytest

from app.data_models.lead import LeadStatus as S
from app.services.pipeline import PipelineRules


@pytest.mark.parametrize(
    ("status", "has_documents", "expected"),
    [
        (S.NEW, False, S.IN_PROGRESS),
        # The prospect shared a policy before the broker qualified them.
        (S.NEW, True, S.DOCS_PENDING),
        (S.IN_PROGRESS, False, S.IN_PROGRESS),
        (S.DOCS_PENDING, True, S.DOCS_PENDING),
        # Never re-qualify analysed or closed work.
        (S.ANALYZED, True, S.ANALYZED),
        (S.CLOSED, False, S.CLOSED),
    ],
)
def test_after_qualification(status: S, has_documents: bool, expected: S) -> None:
    assert PipelineRules.after_qualification(status, has_documents=has_documents) == expected


def test_not_qualified_lead_with_documents_stays_in_progress() -> None:
    rules = PipelineRules
    assert rules.after_qualification(S.NEW, has_documents=True, verdict="NOT_QUALIFIED") == S.IN_PROGRESS
    # A re-run that demotes a lead under review takes it back out of review…
    assert rules.after_qualification(S.DOCS_PENDING, has_documents=True, verdict="NOT_QUALIFIED") == S.IN_PROGRESS
    # …and one that promotes it sends its waiting documents to review.
    assert rules.after_qualification(S.IN_PROGRESS, has_documents=True, verdict="QUALIFIED") == S.DOCS_PENDING
    assert rules.after_qualification(S.NEW, has_documents=True, verdict="NEEDS_MORE_INFO") == S.DOCS_PENDING


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        # Unqualified leads wait for the broker; documents don't skip qualification.
        (S.NEW, S.NEW),
        (S.IN_PROGRESS, S.DOCS_PENDING),
        (S.DOCS_PENDING, S.DOCS_PENDING),
        # A new document re-opens review on an analysed lead.
        (S.ANALYZED, S.DOCS_PENDING),
        (S.CLOSED, S.CLOSED),
    ],
)
def test_after_document_uploaded(status: S, expected: S) -> None:
    assert PipelineRules.after_document_uploaded(status) == expected


def test_document_on_not_qualified_lead_does_not_start_review() -> None:
    assert PipelineRules.after_document_uploaded(S.IN_PROGRESS, verdict="NOT_QUALIFIED") == S.IN_PROGRESS
    assert PipelineRules.after_document_uploaded(S.IN_PROGRESS, verdict="NEEDS_MORE_INFO") == S.DOCS_PENDING


def test_deleting_last_pending_document_returns_to_in_progress() -> None:
    assert PipelineRules.after_document_deleted(S.DOCS_PENDING, remaining_documents=0) == S.IN_PROGRESS
    assert PipelineRules.after_document_deleted(S.DOCS_PENDING, remaining_documents=1) == S.DOCS_PENDING
    assert PipelineRules.after_document_deleted(S.ANALYZED, remaining_documents=0) == S.ANALYZED


@pytest.mark.parametrize(
    ("status", "expected"),
    [(S.NEW, S.ANALYZED), (S.IN_PROGRESS, S.ANALYZED), (S.DOCS_PENDING, S.ANALYZED), (S.CLOSED, S.CLOSED)],
)
def test_after_analysis(status: S, expected: S) -> None:
    assert PipelineRules.after_analysis(status) == expected


def test_can_qualify() -> None:
    assert {s for s in S if PipelineRules.can_qualify(s)} == {S.NEW, S.IN_PROGRESS, S.DOCS_PENDING}


def test_analysis_needs_a_qualified_open_lead() -> None:
    blocked = PipelineRules.analysis_blocked_reason
    assert blocked(S.NEW) is not None
    assert blocked(S.CLOSED, verdict="QUALIFIED") is not None
    # Qualification must actually have run, and not said Not qualified.
    assert blocked(S.IN_PROGRESS) is not None
    assert blocked(S.DOCS_PENDING, verdict="NOT_QUALIFIED") is not None
    for status in (S.IN_PROGRESS, S.DOCS_PENDING, S.ANALYZED):
        for verdict in ("QUALIFIED", "NEEDS_MORE_INFO"):
            assert blocked(status, verdict=verdict) is None
