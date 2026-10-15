"""Lead entity — the prospect being qualified."""
from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.data_models.analysis import Analysis
    from app.data_models.conversation_message import ConversationMessage
    from app.data_models.document import Document
    from app.data_models.qualification import Qualification


class LeadStatus(str, enum.Enum):
    """Pipeline stage — one dashboard tab each.

    Transitions are owned by `app.services.pipeline.PipelineRules`:
    NEW (chatting, not yet qualified) → IN_PROGRESS (qualification agent has
    run) → DOCS_PENDING (documents uploaded, awaiting review) → ANALYZED
    (analysis agent has run). CLOSED is set by the broker with a reason.
    """

    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    DOCS_PENDING = "DOCS_PENDING"
    ANALYZED = "ANALYZED"
    CLOSED = "CLOSED"


class CloseReason(str, enum.Enum):
    """Why the broker closed a lead. Every closure also carries a free-text note."""

    DISQUALIFIED = "DISQUALIFIED"
    PURCHASED = "PURCHASED"
    OTHER = "OTHER"


class LeadSource(str, enum.Enum):
    WEB = "WEB"
    WHATSAPP = "WHATSAPP"
    PHONE = "PHONE"


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    status: Mapped[LeadStatus] = mapped_column(
        String(32), default=LeadStatus.NEW, nullable=False, index=True
    )
    source: Mapped[LeadSource] = mapped_column(
        String(16), default=LeadSource.WEB, nullable=False
    )
    # Latest qualification agent result, denormalised for the dashboard tiles:
    # score 0-100 (0 until it has run) and verdict
    # (QUALIFIED | NOT_QUALIFIED | NEEDS_MORE_INFO, null until it has run).
    qualification_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qualification_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Set only while status == CLOSED.
    close_reason: Mapped[CloseReason | None] = mapped_column(String(16), nullable=True)
    close_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Flexible structured fields captured by the chatbot; see schemas.lead.LeadExtractedFields.
    extracted_fields: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    conversation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="Document.created_at.desc()",
    )
    qualifications: Mapped[list["Qualification"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="Qualification.created_at.desc()",
    )
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="Analysis.created_at.desc()",
    )
