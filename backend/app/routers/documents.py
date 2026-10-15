"""Documents router — real implementation.

Flow:
    POST /api/documents (multipart lead_id + file)
        → 404 if the lead does not exist
        → PdfIngestor validates & writes to disk
        → DocumentRepository persists the row (status=UPLOADED)
        → return {document_id, status}

    POST /api/documents/{id}/extract (broker-triggered)
        → asyncio.create_task(extract_document_task(doc.id))
        → DocumentExtractorAgent runs in the background

    GET /api/documents/{id}
        → DocumentOut with embedded extraction when ready

    GET /api/documents?lead_id=...
        → list of DocumentOut for a lead

Why `asyncio.create_task` and not FastAPI `BackgroundTasks`: BackgroundTasks
runs after the response but with the request-scoped DB session, which is
closed by the time the ~30s extraction call returns → `DetachedInstanceError`.
See ARCHITECTURE.md §7.1.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.client import get_groq_client
from app.agents.document_extractor_agent import DocumentExtractorAgent, ExtractionFailed
from app.agents.errors import user_safe_message
from app.agents.prompts import get_prompt_library
from app.data_models.document import DocumentStatus
from app.db import get_db, session_dependency
from app.repositories.documents import DocumentRepository
from app.repositories.leads import LeadRepository
from app.schemas.document import DocumentOut, DocumentUploadResponse
from app.services.pdf_ingest import PdfIngestor, PdfValidationError
from app.services.pipeline import PipelineRules
from app.settings import Settings, get_settings

router = APIRouter()
log = logging.getLogger(__name__)


# --- POST /api/documents ------------------------------------------------------


@router.post("", response_model=DocumentUploadResponse)
async def upload_document(
    lead_id: str = Form(...),  # noqa: B008 — FastAPI DI
    file: UploadFile = File(...),  # noqa: B008 — FastAPI DI
    session: AsyncSession = Depends(session_dependency),  # noqa: B008 — FastAPI DI
) -> DocumentUploadResponse:
    """Validate + persist a PDF. Extraction waits for the broker to trigger it.

    A qualified lead moves to Documents pending review (`PipelineRules`).
    """
    leads = LeadRepository(session)
    lead = await leads.get_by_id(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found.")

    settings = get_settings()
    try:
        content = await file.read()
    except Exception as exc:  # pragma: no cover
        log.exception("Could not read upload body")
        raise HTTPException(status_code=400, detail="Could not read the uploaded file.") from exc

    ingestor = PdfIngestor(upload_dir=settings.upload_path)
    try:
        stored = ingestor.ingest(
            file_bytes=content,
            original_filename=file.filename or "upload.pdf",
            content_type=file.content_type,
        )
    except PdfValidationError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc

    repo = DocumentRepository(session)
    doc = await repo.create(
        lead_id=lead_id,
        original_filename=stored.original_filename,
        stored_path=str(stored.stored_path),
        mime_type=stored.mime_type,
        size_bytes=stored.size_bytes,
        page_count=stored.page_count,
    )

    await leads.touch_status(lead, PipelineRules.after_document_uploaded(lead.status))
    await session.commit()

    # DELIBERATE: extraction is NOT auto-started. The broker triggers it from
    # the dashboard via `POST /api/documents/{id}/extract` — see the function
    # below. This keeps the broker in control of when LLM tokens are spent and
    # when a document is actually processed.
    return DocumentUploadResponse(document_id=doc.id, status=DocumentStatus(doc.status))


# --- POST /api/documents/{id}/extract -----------------------------------------


@router.post("/{document_id}/extract", response_model=DocumentOut)
async def extract_document(
    document_id: str,
    session: AsyncSession = Depends(session_dependency),  # noqa: B008 — FastAPI DI
) -> DocumentOut:
    """Broker-triggered run of the document extractor agent.

    - UPLOADED / FAILED → kicks off a background extraction and returns the
      current row (status may transition to PROCESSING by the time the client
      next polls). FAILED is re-runnable so the broker can retry after a
      transient provider error; the stored PDF is still on disk.
    - PROCESSING → returns the row untouched (already running).
    - EXTRACTED → returns the row untouched.
    """
    repo = DocumentRepository(session)
    doc = await repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.status in (DocumentStatus.UPLOADED, DocumentStatus.FAILED):
        # Flip to PROCESSING before scheduling so a double-click can't start
        # two agent runs for the same document.
        doc.error_message = None
        await repo.update_status(doc, DocumentStatus.PROCESSING)
        task = asyncio.create_task(extract_document_task(doc.id))
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)

    return DocumentOut.model_validate(doc)


# --- GET /api/documents/{id} --------------------------------------------------


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    session: AsyncSession = Depends(session_dependency),  # noqa: B008 — FastAPI DI
) -> DocumentOut:
    repo = DocumentRepository(session)
    doc = await repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentOut.model_validate(doc)


# --- GET /api/documents?lead_id=... -------------------------------------------


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    lead_id: str,
    session: AsyncSession = Depends(session_dependency),  # noqa: B008 — FastAPI DI
) -> list[DocumentOut]:
    repo = DocumentRepository(session)
    rows = await repo.list_for_lead(lead_id)
    return [DocumentOut.model_validate(d) for d in rows]


# --- DELETE /api/documents/{id} -----------------------------------------------


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    session: AsyncSession = Depends(session_dependency),  # noqa: B008 — FastAPI DI
) -> None:
    """Hard-delete a document and its extraction, plus the PDF on disk.

    204 on success, 404 if the document does not exist. The analysis for the
    lead (if any) is NOT deleted — brokers often want to keep the generated
    recommendation even after the raw document is purged for privacy.
    """
    repo = DocumentRepository(session)
    doc = await repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    stored_path = Path(doc.stored_path) if doc.stored_path else None
    lead_id = doc.lead_id
    await repo.delete(doc)
    leads = LeadRepository(session)
    lead = await leads.get_by_id(lead_id)
    if lead is not None:
        remaining = await repo.count_for_lead(lead_id)
        await leads.touch_status(
            lead, PipelineRules.after_document_deleted(lead.status, remaining_documents=remaining)
        )
    await session.commit()
    if stored_path is not None:
        try:
            if stored_path.exists():
                stored_path.unlink()
        except OSError as exc:  # pragma: no cover - filesystem edge cases
            log.warning("Could not remove stored PDF %s: %s", stored_path, exc)


# --- Background extraction ----------------------------------------------------

# Strong refs for every live create_task() so the event loop doesn't collect them.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


async def extract_document_task(document_id: str) -> None:
    """Session-per-job: owns its lifecycle end-to-end.

    Transitions: PROCESSING (already set by the /extract endpoint)
    → EXTRACTED | FAILED.
    """
    log.info("extract_document_task start doc=%s", document_id)
    settings = get_settings()
    db = get_db()
    async with db.session() as session:
        repo = DocumentRepository(session)
        doc = await repo.get(document_id)
        if doc is None:
            log.warning("extract_document_task: doc %s vanished", document_id)
            return

        try:
            agent = _build_document_extractor_agent(settings)
            result = await agent.extract(doc, Path(doc.stored_path))

            await repo.persist_extraction(
                doc,
                result.parsed,
                model_name=agent.model_name,
                duration_ms=result.duration_ms,
            )
            await repo.update_status(doc, DocumentStatus.EXTRACTED)
            log.info(
                "extract_document_task done doc=%s duration_ms=%d",
                document_id,
                result.duration_ms,
            )
        except ExtractionFailed as exc:
            # Full exception (model, prompt, cause) in the server logs.
            # The DB column feeds the UI, so we store a user-safe copy.
            log.exception("extraction failed for doc %s", document_id)
            await repo.update_status(
                doc,
                DocumentStatus.FAILED,
                error_message=user_safe_message(exc),
            )
        except Exception as exc:  # noqa: BLE001 — ensure we never leak PROCESSING
            log.exception("extract_document_task error for doc %s", document_id)
            fresh = await repo.get(document_id)
            if fresh is not None:
                await repo.update_status(
                    fresh,
                    DocumentStatus.FAILED,
                    error_message=user_safe_message(exc),
                )


# --- construction helpers -----------------------------------------------------


def _build_document_extractor_agent(settings: Settings) -> DocumentExtractorAgent:
    """Wire up DocumentExtractorAgent from process-wide singletons."""
    return DocumentExtractorAgent(
        client=get_groq_client(),
        prompt_library=get_prompt_library(),
        model_name=settings.groq_model_extraction,
        timeout_s=settings.groq_timeout_extraction,
        max_tokens=settings.groq_max_tokens_extraction,
        max_input_chars=settings.groq_extraction_max_input_chars,
    )
