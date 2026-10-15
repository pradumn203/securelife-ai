"""PDF ingestion: validate uploads and persist them to local disk.

The ingestor is deliberately dumb — it validates shape, writes bytes, and
returns a receipt. Extraction (the LLM call) is a separate concern handled
by `app.agents.document_extractor_agent.DocumentExtractorAgent`.

Validation rules enforced here (also surfaced in `routers/documents.py` as 4xx):

- Must be a PDF (content-type `application/pdf` OR filename ends `.pdf`).
- Size must be ≤ `PdfIngestor.MAX_SIZE_BYTES` (20 MB).
- Must be openable by PyMuPDF.
- Must not be encrypted.
- Must have ≤ `PdfIngestor.MAX_PAGES` pages (100).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pymupdf

log = logging.getLogger(__name__)


class PdfValidationError(ValueError):
    """Base class for PDF ingestion validation failures.

    Carries an HTTP status so the router can round-trip the right 4xx code
    without a status→exception lookup table.
    """

    http_status: int = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)


class PdfNotAPdfError(PdfValidationError):
    http_status = 415


class PdfTooLargeError(PdfValidationError):
    http_status = 413


class PdfEncryptedError(PdfValidationError):
    http_status = 400


class PdfTooLongError(PdfValidationError):
    http_status = 400


class PdfUnreadableError(PdfValidationError):
    http_status = 400


@dataclass(slots=True)
class StoredPdf:
    """Receipt returned by `PdfIngestor.ingest`."""

    stored_path: Path
    original_filename: str
    page_count: int
    size_bytes: int
    mime_type: str


class PdfIngestor:
    """Validates and stores an uploaded PDF.

    Instantiated per-request with the target `upload_dir`; the directory must
    already exist (settings.upload_path ensures this).
    """

    MAX_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB
    # Full policy wordings commonly run 60+ pages. The model only ever sees
    # the first `groq_extraction_max_input_chars` of text, so this cap just
    # bounds PyMuPDF work, not LLM cost.
    MAX_PAGES: int = 100
    ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
        {"application/pdf", "application/octet-stream"}
    )

    def __init__(self, upload_dir: Path) -> None:
        self._upload_dir = upload_dir

    def ingest(
        self,
        *,
        file_bytes: bytes,
        original_filename: str,
        content_type: str | None,
    ) -> StoredPdf:
        """Validate + persist the bytes. Returns a `StoredPdf` on success."""
        self._validate_shape(
            filename=original_filename,
            content_type=content_type,
            size=len(file_bytes),
        )
        page_count = self._validate_pdf_structure(file_bytes)

        stored_path = self._upload_dir / f"{uuid4()}.pdf"
        stored_path.write_bytes(file_bytes)

        return StoredPdf(
            stored_path=stored_path,
            original_filename=original_filename,
            page_count=page_count,
            size_bytes=len(file_bytes),
            mime_type="application/pdf",
        )

    # --- validation helpers ---------------------------------------------------

    @classmethod
    def _validate_shape(
        cls, *, filename: str, content_type: str | None, size: int
    ) -> None:
        if size <= 0:
            raise PdfUnreadableError("Uploaded file is empty.")
        if size > cls.MAX_SIZE_BYTES:
            raise PdfTooLargeError(
                f"File too large: {size} bytes exceeds limit of {cls.MAX_SIZE_BYTES} bytes (20 MB)."
            )
        ct_ok = (content_type or "").lower() in cls.ALLOWED_CONTENT_TYPES
        name_ok = filename.lower().endswith(".pdf") if filename else False
        if not (ct_ok or name_ok):
            raise PdfNotAPdfError(
                "Only PDF uploads are accepted (content-type application/pdf or .pdf filename)."
            )

    @classmethod
    def _validate_pdf_structure(cls, file_bytes: bytes) -> int:
        """Open with PyMuPDF; return page count. Raises on structural problems."""
        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:  # pragma: no cover - pymupdf raises a lot of things
            # The PyMuPDF message is parser detail, not user copy — log it and
            # return a fixed sentence (this text becomes the HTTP 400 body).
            log.warning("PyMuPDF could not open upload: %s", exc)
            raise PdfUnreadableError(
                "This file could not be opened as a PDF. It may be damaged or not a real PDF."
            ) from exc

        try:
            if doc.is_encrypted:
                raise PdfEncryptedError("Encrypted PDFs are not supported.")
            page_count = int(doc.page_count)
            if page_count <= 0:
                raise PdfUnreadableError("PDF reports zero pages.")
            if page_count > cls.MAX_PAGES:
                raise PdfTooLongError(
                    f"Document too long (max {cls.MAX_PAGES} pages, got {page_count})."
                )
            return page_count
        finally:
            doc.close()
