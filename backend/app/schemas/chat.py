"""Chat-related schemas: session bootstrap, streaming, message DTOs."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import LeadSource, MessageRole
from app.schemas.lead import LeadExtractedFields


class ChatSessionCreate(BaseModel):
    """Bootstrap payload for a brand-new chat session."""

    model_config = ConfigDict(extra="ignore")

    source: LeadSource = LeadSource.WEB


class ChatSessionOut(BaseModel):
    """What the UI gets back when a session starts."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    lead_id: str
    greeting: str = Field(
        default="Hi! I'm here to help you find the right insurance cover. "
        "Could you start by telling me your name?"
    )


class ChatStreamIn(BaseModel):
    """Body of the streaming request: a single user turn."""

    model_config = ConfigDict(extra="ignore")

    lead_id: str
    message: str = Field(min_length=1, max_length=4000)


class ChatStreamEvent(BaseModel):
    """Discriminated event emitted over SSE."""

    model_config = ConfigDict(extra="allow")

    type: Literal["token", "done", "error", "state"]
    text: str | None = None
    message_id: str | None = None
    qualification_score: int | None = None
    status: str | None = None
    error: str | None = None


class ChatMessageOut(BaseModel):
    """Persisted conversation message as returned by the API."""

    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: str
    lead_id: str
    role: MessageRole
    content: str
    created_at: datetime


class ChatTurnExtractorOutput(BaseModel):
    """Structured output of the chat extractor agent for one turn."""

    model_config = ConfigDict(extra="allow")

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    extracted_fields: LeadExtractedFields = Field(default_factory=LeadExtractedFields)
