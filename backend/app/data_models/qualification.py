"""Qualification entity — one qualification agent run for a Lead."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.data_models.lead import Lead


class Qualification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "qualifications"

    lead_id: Mapped[str] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # QUALIFIED | NOT_QUALIFIED | NEEDS_MORE_INFO — finalised server-side.
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    # 0-100, aggregated server-side from the per-dimension scores.
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # [{key, score, rationale, evidence_quote, evidence_verified}]
    dimensions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # [{reason, evidence_quote, evidence_verified}] — verified ones only.
    dealbreakers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    red_flags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    follow_up_questions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Labels of question-plan facts still missing when the agent ran.
    missing_details: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_llm_response: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="qualifications")
