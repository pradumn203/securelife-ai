"""LeadRepository — all Lead-row queries used by the chat flow and broker-side CRUD.

This repository is consumed by:
  * `app.routers.chat` (chat path — create, read, update_from_chat)
  * `app.routers.documents` (upload — lead existence check)
  * `app.routers.leads` (list, get, patch, qualify, delete)
  * `app.services.analysis_orchestrator.AnalysisOrchestrator` (status advance)

Any new query a consumer needs goes here. Callers never issue raw SQL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_models.lead import CloseReason, Lead, LeadSource, LeadStatus


class LeadRepository:
    """SQLAlchemy query encapsulation for the Lead aggregate."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    async def create_lead(
        self,
        *,
        source: LeadSource = LeadSource.WEB,
        full_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        city: str | None = None,
    ) -> Lead:
        """Insert a brand-new lead row in NEW status with score 0."""
        lead = Lead(
            full_name=full_name,
            email=email,
            phone=phone,
            city=city,
            status=LeadStatus.NEW,
            source=source,
            qualification_score=0,
            extracted_fields={},
        )
        self._session.add(lead)
        await self._session.flush()
        return lead

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    async def get_by_id(self, lead_id: str) -> Lead | None:
        return await self._session.get(Lead, lead_id)

    async def list(
        self,
        *,
        status: LeadStatus | None = None,
        search: str | None = None,
        limit: int = 100,
        include_incomplete: bool = False,
    ) -> list[Lead]:
        """List leads for the broker view.

        By default (`include_incomplete=False`) hides prospects who have not yet
        shared the mandatory broker-view fields: `full_name` AND at least one of
        (`email`, `phone`). An in-flight chat lead with only a name but no
        contact details yet is intentionally invisible to the broker — these
        get surfaced the moment the prospect provides the missing field.
        """
        stmt = select(Lead).order_by(Lead.created_at.desc()).limit(limit)
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(
                (Lead.full_name.ilike(like))
                | (Lead.email.ilike(like))
                | (Lead.phone.ilike(like))
            )
        if not include_incomplete:
            stmt = stmt.where(
                Lead.full_name.isnot(None),
                Lead.full_name != "",
                (Lead.email.isnot(None) & (Lead.email != ""))
                | (Lead.phone.isnot(None) & (Lead.phone != "")),
            )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    async def delete(self, lead: Lead) -> None:
        """Hard-delete a lead; children (messages, documents, extractions,
        analyses) cascade via ORM `all, delete-orphan`.
        """
        await self._session.delete(lead)
        await self._session.flush()

    # ------------------------------------------------------------------
    # Update (chat path)
    # ------------------------------------------------------------------
    async def update_from_chat(
        self,
        lead: Lead,
        *,
        full_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        city: str | None = None,
        extracted_fields: dict[str, Any] | None = None,
        qualification_score: int | None = None,
        status: LeadStatus | None = None,
    ) -> Lead:
        """Merge a turn's new facts onto the lead.

        Semantics:
          * Scalar contact fields: non-None overwrites. Pass None to leave untouched.
          * `extracted_fields`: merged key-by-key. New non-None keys replace old.
          * `qualification_score`: overwrite if provided (caller clamps 0-100).
          * `status`: overwrite if provided (caller enforces transitions).

        Returns the mutated (and flushed) Lead; caller controls commit.
        """
        if full_name is not None and full_name.strip():
            lead.full_name = full_name.strip()
        if email is not None and email.strip():
            lead.email = email.strip()
        if phone is not None and phone.strip():
            lead.phone = phone.strip()
        if city is not None and city.strip():
            lead.city = city.strip()

        if extracted_fields:
            # SQLAlchemy JSON column requires a new dict for change detection.
            merged = dict(lead.extracted_fields or {})
            for key, value in extracted_fields.items():
                if value is None:
                    continue
                merged[key] = value
            lead.extracted_fields = merged

        if qualification_score is not None:
            lead.qualification_score = max(0, min(100, int(qualification_score)))

        if status is not None:
            lead.status = status

        lead.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return lead

    # ------------------------------------------------------------------
    # Update (broker-side PATCH)
    # ------------------------------------------------------------------
    async def patch(
        self,
        lead: Lead,
        *,
        full_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        city: str | None = None,
        status: LeadStatus | None = None,
        close_reason: CloseReason | None = None,
        close_note: str | None = None,
        conversation_summary: str | None = None,
        extracted_fields: dict[str, Any] | None = None,
    ) -> Lead:
        """Apply a broker-side PATCH. Empty strings are treated as 'clear this field'.

        `extracted_fields` is merged key-by-key; a None/empty value clears that key.
        Closure fields only live on CLOSED leads: re-opening a lead clears them.
        The caller validates that a CLOSED lead has a reason.
        """
        if extracted_fields:
            # SQLAlchemy JSON column requires a new dict for change detection.
            merged = dict(lead.extracted_fields or {})
            for key, value in extracted_fields.items():
                merged[key] = None if value in (None, "") else value
            lead.extracted_fields = merged
        if full_name is not None:
            lead.full_name = full_name or None
        if email is not None:
            lead.email = email or None
        if phone is not None:
            lead.phone = phone or None
        if city is not None:
            lead.city = city or None
        if status is not None:
            lead.status = status
        if lead.status == LeadStatus.CLOSED:
            if close_reason is not None:
                lead.close_reason = close_reason
            if close_note is not None:
                lead.close_note = close_note.strip() or None
        else:
            lead.close_reason = None
            lead.close_note = None
        if conversation_summary is not None:
            lead.conversation_summary = conversation_summary or None
        lead.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return lead

    # ------------------------------------------------------------------
    # Status-only touch (used after background jobs flip pipeline state)
    # ------------------------------------------------------------------
    async def touch_status(self, lead: Lead, status: LeadStatus) -> Lead:
        """Set status, bump updated_at, flush. No other mutations."""
        lead.status = status
        lead.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return lead
