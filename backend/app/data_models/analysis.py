"""Analysis entity — the broker-facing synthesis for a Lead."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.data_models.lead import Lead


class Analysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analyses"

    lead_id: Mapped[str] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )

    coverage_gaps: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    potential_savings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    risk_flags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_llm_response: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="analyses")
