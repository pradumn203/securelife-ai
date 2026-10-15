"""Document + DocumentExtraction repository.

Thin SQLAlchemy wrapper. Business logic (status transitions, extraction) lives
one layer up in services / background tasks. See `app.routers.documents` for
the HTTP contract and `app.agents.document_extractor_agent` for the LLM call.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.data_models.document import Document, DocumentStatus
from app.data_models.document_extraction import DocumentExtraction
from app.schemas.extraction import DocumentExtractionLLMSchema


class DocumentRepository:
    """CRUD for `Document` + `DocumentExtraction`.

    Caller owns the session lifecycle; repo methods never commit implicitly
    except where documented (`persist_extraction`, which commits so the
    background task can observe its own writes).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Document reads -------------------------------------------------------

    async def get(self, document_id: str) -> Document | None:
        """Return a `Document` eagerly loading its extraction, or None."""
        stmt = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.extraction))
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_for_lead(self, lead_id: str) -> list[Document]:
        """All documents for a lead, newest first, with their extractions."""
        stmt = (
            select(Document)
            .where(Document.lead_id == lead_id)
            .options(selectinload(Document.extraction))
            .order_by(Document.created_at.desc())
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def count_for_lead(self, lead_id: str) -> int:
        """Number of documents attached to a lead (any status)."""
        stmt = select(func.count()).select_from(Document).where(Document.lead_id == lead_id)
        return int((await self._session.execute(stmt)).scalar_one())

    async def list_extractions_for_lead(self, lead_id: str) -> list[DocumentExtraction]:
        """Every `DocumentExtraction` attached to a lead's documents, newest first."""
        stmt = (
            select(DocumentExtraction)
            .join(Document, Document.id == DocumentExtraction.document_id)
            .where(Document.lead_id == lead_id)
            .order_by(DocumentExtraction.created_at.desc())
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # --- Document writes ------------------------------------------------------

    async def create(
        self,
        *,
        lead_id: str,
        original_filename: str,
        stored_path: str,
        mime_type: str,
        size_bytes: int,
        page_count: int | None,
    ) -> Document:
        """Insert a new Document row in UPLOADED state and flush its id."""
        doc = Document(
            lead_id=lead_id,
            original_filename=original_filename,
            stored_path=stored_path,
            mime_type=mime_type,
            size_bytes=size_bytes,
            page_count=page_count,
            status=DocumentStatus.UPLOADED,
        )
        self._session.add(doc)
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(doc)
        return doc

    async def update_status(
        self,
        doc: Document,
        status: DocumentStatus,
        *,
        error_message: str | None = None,
    ) -> None:
        """Transition the document to `status` and commit."""
        doc.status = status
        if error_message is not None:
            doc.error_message = error_message[:1000]
        await self._session.commit()

    # --- Extraction writes ----------------------------------------------------

    async def persist_extraction(
        self,
        doc: Document,
        parsed: DocumentExtractionLLMSchema,
        *,
        model_name: str,
        duration_ms: int,
    ) -> DocumentExtraction:
        """Create (or replace) the `DocumentExtraction` row for a document.

        Converts `sum_insured` / `premium_amount` strings to `Decimal` if
        parseable, and `renewal_date` to a `date` if it is ISO `YYYY-MM-DD`.
        On parse failure the field is left `None` — the raw string is still
        preserved in `evidence` and `raw_llm_response` for debugging.
        """
        # If an extraction already exists (retry path), replace it.
        existing = await self._session.execute(
            select(DocumentExtraction).where(
                DocumentExtraction.document_id == doc.id
            )
        )
        prev = existing.scalar_one_or_none()
        if prev is not None:
            await self._session.delete(prev)
            await self._session.flush()

        raw_dump = parsed.model_dump(mode="json")

        row = DocumentExtraction(
            document_id=doc.id,
            policy_type=parsed.policy_type,
            provider=parsed.provider,
            policy_number=parsed.policy_number,
            insured_name=parsed.insured_name,
            sum_insured=_to_decimal(parsed.sum_insured),
            premium_amount=_to_decimal(parsed.premium_amount),
            premium_frequency=parsed.premium_frequency,
            renewal_date=_to_iso_date(parsed.renewal_date),
            exclusions=[ex.model_dump(mode="json") for ex in parsed.exclusions],
            riders=[rd.model_dump(mode="json") for rd in parsed.riders],
            evidence={k: v.model_dump(mode="json") for k, v in parsed.evidence.items()},
            raw_llm_response=raw_dump,
            model_name=model_name,
            extraction_duration_ms=duration_ms,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(row)
        return row

    # --- Delete ---------------------------------------------------------------

    async def delete(self, doc: Document) -> None:
        """Hard-delete a Document and its extraction.

        The `DocumentExtraction` child cascades via ORM `all, delete-orphan`.
        The raw PDF on disk (`doc.stored_path`) is NOT removed by this method
        — the router unlinks it after the DB delete commits, so we never
        orphan a DB row behind a missing file.
        """
        await self._session.delete(doc)
        await self._session.flush()

    # --- Orphan sweep ---------------------------------------------------------

    async def sweep_orphaned_processing(self, older_than_seconds: int = 600) -> int:
        """Mark `PROCESSING` rows older than N seconds as `FAILED`.

        Called once at startup from `main.lifespan` (see ARCHITECTURE §7.1).
        """
        cutoff = datetime.now(UTC).timestamp() - older_than_seconds
        stmt = select(Document).where(Document.status == DocumentStatus.PROCESSING)
        res = await self._session.execute(stmt)
        count = 0
        for doc in res.scalars().all():
            if doc.updated_at.timestamp() < cutoff:
                doc.status = DocumentStatus.FAILED
                doc.error_message = "Orphaned by server restart."
                count += 1
        if count:
            await self._session.commit()
        return count


# --- normalization helpers ----------------------------------------------------


def _to_decimal(raw: str | None) -> Decimal | None:
    """Best-effort parse of the 'numeric string' the model returns.

    Accepts digits with commas, decimal point, optional currency prefix. Returns
    None if not parseable (the raw string is preserved in evidence anyway).
    """
    if raw is None:
        return None
    import re

    text = str(raw).strip()
    if not text:
        return None
    # Extract the first number-like substring (handles 'Rs. 28,400.50', '₹25,00,000', etc.).
    match = re.search(r"-?[0-9][0-9,]*(?:\.[0-9]+)?", text)
    if not match:
        return None
    cleaned = match.group(0).replace(",", "")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _to_iso_date(raw: str | None) -> date | None:
    """Parse ISO YYYY-MM-DD. Returns None on anything else."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


__all__ = ["DocumentRepository"]
