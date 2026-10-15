"""AnalysisGrounding — code-side checks on the analysis agent's output.

The analysis agent is told to ground every claim, but its output is still
advice about money, so two rules are enforced in code before it's stored:

* **Savings need a verified premium.** SecureLife has no market-quote data,
  so the only defensible saving is one carved out of what the client already
  pays. A non-zero figure is kept only when a document carries a verified
  premium, and only when it's smaller than that premium. Anything else is
  stored as "not quantified" with a rationale that says why.
* **"Confirmed in the document" needs a checked document.** A gap may only
  claim document backing when at least one extraction has verified facts;
  otherwise it's downgraded to "not captured", which the UI shows as
  something to confirm with the client.

Extractions stored before citation checking existed carry no `verified`
flags; their values are treated as usable, the same as before.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.schemas.analysis import AnalysisLLMOutput, PotentialSavings

if TYPE_CHECKING:
    from app.data_models.document_extraction import DocumentExtraction


class EvidenceStatus:
    """Reads the checker's verdicts off a stored extraction."""

    @staticmethod
    def field(extraction: DocumentExtraction, name: str) -> bool | None:
        """True / False from the checker, None if the field was never checked."""
        ev = (extraction.evidence or {}).get(name)
        if isinstance(ev, dict):
            flag = ev.get("verified")
            return flag if isinstance(flag, bool) else None
        return None

    @staticmethod
    def item(item: Any) -> bool | None:
        flag = item.get("verified") if isinstance(item, dict) else None
        return flag if isinstance(flag, bool) else None

    @classmethod
    def usable(cls, extraction: DocumentExtraction, name: str) -> bool:
        """The value exists and the checker didn't reject it."""
        return getattr(extraction, name, None) is not None and cls.field(extraction, name) is not False


class AnalysisGrounding:
    """Applies the savings and gap-basis rules to one analysis."""

    PAYMENTS_PER_YEAR = {"monthly": 12, "quarterly": 4, "half_yearly": 2, "annual": 1}

    NO_PREMIUM = (
        "Not quantified: the shared documents have no verified premium to base a saving on. "
        "Get comparison quotes before discussing a number with the client."
    )
    OVER_PREMIUM = (
        "Not quantified: the estimate was larger than the client's current premium, so it "
        "can't be supported. Get comparison quotes before discussing a number with the client."
    )
    NOTHING_FOUND = "No saving identified from the shared documents."

    def __init__(self, extractions: list[DocumentExtraction]) -> None:
        self._extractions = extractions

    def apply(self, output: AnalysisLLMOutput) -> AnalysisLLMOutput:
        gaps = output.coverage_gaps
        if not self.has_checked_document_facts():
            gaps = [
                g.model_copy(update={"basis": "not_captured"})
                if g.basis == "confirmed_in_document"
                else g
                for g in gaps
            ]
        return output.model_copy(
            update={"potential_savings": self._ground_savings(output.potential_savings), "coverage_gaps": gaps}
        )

    def annual_premium(self) -> Decimal | None:
        """Total yearly premium across documents whose premium is usable."""
        total = Decimal(0)
        found = False
        for ext in self._extractions:
            per_year = self.PAYMENTS_PER_YEAR.get((ext.premium_frequency or "").lower())
            if per_year is None or not EvidenceStatus.usable(ext, "premium_amount"):
                continue
            total += Decimal(ext.premium_amount) * per_year
            found = True
        return total if found else None

    def has_checked_document_facts(self) -> bool:
        """At least one document fact the gap could legitimately rest on."""
        fields = ("sum_insured", "premium_amount", "renewal_date", "policy_type")
        for ext in self._extractions:
            if any(EvidenceStatus.usable(ext, f) for f in fields):
                return True
            items = list(ext.exclusions or []) + list(ext.riders or [])
            if any(EvidenceStatus.item(i) is not False for i in items):
                return True
        return False

    def _ground_savings(self, savings: PotentialSavings) -> PotentialSavings:
        if savings.annual_inr <= 0:
            return PotentialSavings(
                annual_inr=0,
                rationale=savings.rationale.strip() or self.NOTHING_FOUND,
                basis="not_quantified",
            )
        premium = self.annual_premium()
        if premium is None:
            return PotentialSavings(annual_inr=0, rationale=self.NO_PREMIUM, basis="not_quantified")
        if savings.annual_inr >= premium:
            return PotentialSavings(annual_inr=0, rationale=self.OVER_PREMIUM, basis="not_quantified")
        return savings.model_copy(update={"basis": "verified_premium"})


__all__ = ["AnalysisGrounding", "EvidenceStatus"]
