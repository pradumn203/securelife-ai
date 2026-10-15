"""AnalysisAgent - the Groq call that synthesizes a broker analysis.

Thin wrapper around a single chat completion in JSON mode with a
Pydantic-validated response. All state (DB session, lead load, persistence)
is the orchestrator's responsibility; this class just turns a Lead + a list of
DocumentExtractions into an `AnalysisLLMOutput`.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

from app.agents.client import ModelFallback
from app.agents.prompts import PromptLibrary
from app.schemas.analysis import AnalysisLLMOutput
from app.services.analysis_grounding import EvidenceStatus
from app.services.question_plan import QuestionPlan

if TYPE_CHECKING:
    from app.data_models.document_extraction import DocumentExtraction
    from app.data_models.lead import Lead


log = logging.getLogger(__name__)


class AnalysisAgent:
    """Call Groq once to produce an `AnalysisLLMOutput` for a lead.

    The client can be passed in directly OR as a zero-arg factory so
    construction of the agent doesn't force the client to be built eagerly.
    This matters because `get_groq_client()` raises if `GROQ_API_KEY` is empty,
    and we want 404/400 checks (lead not found, no extractions) to still
    return cleanly in that case.
    """

    PROMPT_NAME = "analysis_agent"

    def __init__(
        self,
        client: AsyncOpenAI | Callable[[], AsyncOpenAI],
        model_name: str,
        timeout_s: int,
        max_tokens: int,
        prompts: PromptLibrary,
    ) -> None:
        self._client_or_factory = client
        self._models = ModelFallback.for_agent(model_name)
        self._model_used = model_name
        self._timeout_s = timeout_s
        self._max_tokens = max_tokens
        self._prompts = prompts

    @property
    def model_name(self) -> str:
        """The model that produced the latest result (may be a fallback)."""
        return self._model_used

    def _get_client(self) -> AsyncOpenAI:
        if callable(self._client_or_factory):
            return self._client_or_factory()
        return self._client_or_factory

    async def synthesize(
        self,
        lead: Lead,
        extractions: list[DocumentExtraction],
    ) -> AnalysisLLMOutput:
        """Run one JSON-mode chat completion. Returns the parsed schema.

        Raises whatever the SDK raises on transport/auth failures. The SDK's
        built-in retry handles transient 5xx; callers translate exceptions to
        user-safe copy before surfacing them to the UI.
        """
        system = self._prompts.get(self.PROMPT_NAME)
        user_context = self._build_user_context(lead, extractions)

        client = self._get_client()
        self._model_used, response = await self._models.create(
            client,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_context},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=self._max_tokens,
            timeout=self._timeout_s,
        )

        content = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not content:
            raise RuntimeError("Analysis call returned an empty body.")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            log.warning("Analysis JSON parse failed: %s", exc)
            raise RuntimeError("Analysis call returned non-JSON content.") from exc
        return AnalysisLLMOutput.model_validate(payload)

    # ------------------------------------------------------------------
    # User-context block
    # ------------------------------------------------------------------
    def _build_user_context(
        self, lead: Lead, extractions: list[DocumentExtraction]
    ) -> str:
        """Format the lead profile + policy extractions as a markdown-ish block.

        Grounds the LLM: everything it is allowed to reason about is
        in this string. The system prompt forbids inventing details
        not present here.
        """
        today = datetime.now(UTC).date().isoformat()
        lines: list[str] = []
        lines.append(f"Today's date: {today}")
        lines.append("")
        lines.append("# Client profile")
        lines.append(f"- Name: {lead.full_name or 'unknown'}")
        lines.append(f"- City: {lead.city or 'unknown'}")
        # The question plan carries the insurance category (the most important
        # input for scoping the analysis) plus the type-specific answers.
        plan = QuestionPlan.for_lead(lead)
        lines.append(
            f"- Insurance category they're asking about: {plan.insurance_type or 'unknown'}"
        )
        for item in plan.checklist():
            if item.captured and item.key not in ("full_name", "contact", "insurance_type"):
                lines.append(f"- {item.label} (self-reported): {item.value}")
        fields: dict[str, Any] = dict(lead.extracted_fields or {})
        for key, label in (("occupation", "Occupation"), ("risk_appetite", "Risk appetite")):
            if fields.get(key):
                lines.append(f"- {label}: {fields[key]}")
        if lead.qualification_score:
            lines.append(f"- Qualification agent score: {lead.qualification_score}/100")

        if not extractions:
            lines.append("")
            lines.append("# Current policies")
            lines.append("(No policy documents extracted yet.)")
            return "\n".join(lines)

        lines.append("")
        lines.append("# Current policies")
        lines.append(
            "Facts were checked against the PDF text. A fact marked \"could not be verified\" "
            "was not found in the document: treat it as unknown and never repeat that label. \"Not captured\" means "
            "the extraction doesn't mention it, not that the policy lacks it."
        )
        for idx, ext in enumerate(extractions, start=1):
            lines.append(f"## Policy {idx}")
            fact = self._fact_formatter(ext)
            lines.append(f"- Policy type: {fact('policy_type', ext.policy_type)}")
            lines.append(f"- Provider: {fact('provider', ext.provider)}")
            if ext.policy_number:
                lines.append(f"- Policy number: {fact('policy_number', ext.policy_number)}")
            if ext.insured_name:
                lines.append(f"- Insured name: {fact('insured_name', ext.insured_name)}")
            lines.append(f"- Sum insured: {fact('sum_insured', self._fmt_amount(ext.sum_insured))}")
            if ext.premium_amount is not None or ext.premium_frequency:
                freq = ext.premium_frequency or "unknown frequency"
                premium = fact("premium_amount", self._fmt_amount(ext.premium_amount))
                lines.append(f"- Premium: {premium} ({freq})")
            if ext.renewal_date is not None:
                lines.append(f"- Renewal date: {fact('renewal_date', ext.renewal_date.isoformat())}")
            self._append_items(lines, "Exclusions", list(ext.exclusions or []))
            self._append_items(lines, "Riders", list(ext.riders or []))
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _fact_formatter(ext: DocumentExtraction) -> Callable[[str, Any], str]:
        """Render a value, labelling the ones the evidence check rejected."""

        def fmt(field: str, value: Any) -> str:
            if value is None or value == "not captured":
                return "not captured"
            if EvidenceStatus.field(ext, field) is False:
                return f"{value} (could not be verified against the document — treat as unknown)"
            return str(value)

        return fmt

    def _append_items(self, lines: list[str], label: str, items: list[Any]) -> None:
        """Exclusions / riders, leaving out the ones not found in the document."""
        kept = [i for i in items if EvidenceStatus.item(i) is not False]
        dropped = len(items) - len(kept)
        if kept:
            lines.append(f"- {label}:")
            lines.extend(f"  - {self._fmt_item(item)}" for item in kept)
        else:
            lines.append(f"- {label}: none captured (not confirmed absent)")
        if dropped:
            lines.append(f"  ({dropped} more could not be found in the document and were left out)")

    @staticmethod
    def _fmt_amount(value: Decimal | float | int | None) -> str:
        if value is None:
            return "not captured"
        try:
            d = Decimal(value) if not isinstance(value, Decimal) else value
            normalized = d.normalize()
            as_str = f"{normalized:f}"
            return f"Rs. {as_str}"
        except (ValueError, ArithmeticError):
            return f"Rs. {value}"

    @staticmethod
    def _fmt_item(item: Any) -> str:
        """Exclusions/riders are stored as list[dict]. Render whichever text we have."""
        if isinstance(item, dict):
            text = item.get("text") or item.get("name") or item.get("description")
            page = item.get("source_page")
            if text and page:
                return f"{text} (p. {page})"
            if text:
                return str(text)
            return str(item)
        return str(item)
