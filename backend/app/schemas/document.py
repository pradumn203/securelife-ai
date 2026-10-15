"""Document resource schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.enums import DocumentStatus
from app.schemas.extraction import DocumentExtractionOut


class DocumentOut(BaseModel):
    """Document resource; `extraction` present when status == EXTRACTED."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: str
    lead_id: str
    original_filename: str
    mime_type: str
    size_bytes: int
    page_count: int | None = None
    status: DocumentStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    extraction: DocumentExtractionOut | None = None


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")

    document_id: str
    status: DocumentStatus
