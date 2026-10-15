"""Structured extraction result for a Document (one-to-one)."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.data_models.document import Document


class DocumentExtraction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_extractions"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Canonical extracted fields
    policy_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(200), nullable=True)
    policy_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    insured_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sum_insured: Mapped[Numeric | None] = mapped_column(Numeric(14, 2), nullable=True)
    premium_amount: Mapped[Numeric | None] = mapped_column(Numeric(14, 2), nullable=True)
    premium_frequency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    exclusions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    riders: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Field-level evidence: {field_name: {value, source_page, source_excerpt, confidence}}
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    raw_llm_response: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    extraction_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="extraction")
