"""Pipeline rules — the single owner of lead stage transitions.

Each stage is one dashboard tab:

    NEW            New leads: chatting, qualification agent not run yet
    IN_PROGRESS    In progress: qualification agent has run, no documents yet
                   (or the verdict was Not qualified, so documents wait)
    DOCS_PENDING   Documents pending review: qualified and documents uploaded
    ANALYZED       Completed analyses: analysis agent has run
    CLOSED         Closed by the broker, with a reason (disqualified /
                   purchased / other) and a note

A NOT_QUALIFIED verdict never closes a lead by itself (closing is the
broker's call), but it does stop the lead advancing: its documents don't
move it into review and the analysis agent won't run for it.

Routers and orchestrators call these methods at each event instead of
setting `status` themselves, so the lifecycle lives in one tested place.
Pure functions over statuses — no I/O.
"""
from __future__ import annotations

from app.data_models.lead import LeadStatus

# Stages the qualification agent may (re-)run from. Once analysed or closed,
# re-qualifying would rewrite history the broker has already acted on.
QUALIFIABLE_STATUSES: frozenset[LeadStatus] = frozenset(
    {LeadStatus.NEW, LeadStatus.IN_PROGRESS, LeadStatus.DOCS_PENDING}
)

NOT_QUALIFIED = "NOT_QUALIFIED"


class PipelineRules:
    """Stage transitions for a lead, one method per pipeline event."""

    @staticmethod
    def can_qualify(status: LeadStatus) -> bool:
        return status in QUALIFIABLE_STATUSES

    @staticmethod
    def after_qualification(
        status: LeadStatus, *, has_documents: bool, verdict: str | None = None
    ) -> LeadStatus:
        """Qualification agent ran → the broker is now working the lead.

        Documents the prospect shared before qualification go straight to
        review, unless the verdict was Not qualified: that lead stays In
        progress until the broker closes it or a re-run changes the verdict.
        """
        if not PipelineRules.can_qualify(status):
            return status
        if has_documents and verdict != NOT_QUALIFIED:
            return LeadStatus.DOCS_PENDING
        return LeadStatus.IN_PROGRESS

    @staticmethod
    def after_document_uploaded(status: LeadStatus, *, verdict: str | None = None) -> LeadStatus:
        """A document arrived (from the prospect or the broker).

        Qualified leads move to review; a new document on an analysed lead
        re-opens review. NEW leads stay NEW until the broker qualifies them,
        Not-qualified leads stay where they are, and CLOSED leads stay closed.
        """
        if verdict == NOT_QUALIFIED:
            return status
        if status in (LeadStatus.IN_PROGRESS, LeadStatus.ANALYZED):
            return LeadStatus.DOCS_PENDING
        return status

    @staticmethod
    def after_document_deleted(status: LeadStatus, *, remaining_documents: int) -> LeadStatus:
        """The last pending document was removed → back to In progress."""
        if status == LeadStatus.DOCS_PENDING and remaining_documents == 0:
            return LeadStatus.IN_PROGRESS
        return status

    @staticmethod
    def analysis_blocked_reason(status: LeadStatus, *, verdict: str | None = None) -> str | None:
        """Why the analysis agent can't run for this lead, or None if it can.

        Analysis needs a qualification verdict that isn't Not qualified, so
        advice is only ever produced for a prospect the broker can act on.
        Needs more info is allowed: the broker sees the gaps alongside it.
        """
        if status == LeadStatus.CLOSED:
            return "This prospect is closed. Re-open it (Edit → Status) to run a new analysis."
        if status == LeadStatus.NEW or verdict is None:
            return "Run the qualification agent before the analysis agent."
        if verdict == NOT_QUALIFIED:
            return (
                "The qualification agent marked this prospect Not qualified. Close them as "
                "disqualified, or correct their details (Edit) and re-run qualification."
            )
        return None

    @staticmethod
    def after_analysis(status: LeadStatus) -> LeadStatus:
        """Analysis agent ran → Completed analyses (closed leads stay closed)."""
        if status == LeadStatus.CLOSED:
            return status
        return LeadStatus.ANALYZED
