"""QualificationAgent — judges whether a prospect is worth a broker's time.

Runs when the broker clicks "Run qualification agent". It reads the full chat
transcript plus the prospect's question-plan checklist (core facts and the
insurance-type-specific details) and returns a `QualificationLLMOutput`:
a verdict, five 0-5 dimension scores each backed by a verbatim quote from the
prospect, red flags, and follow-up questions for the broker.

The agent's output is advisory input to `QualificationOrchestrator`, which
verifies every quote against the transcript, computes the overall score and
finalises the verdict. The agent never touches the DB.
"""
from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI, BadRequestError

from app.agents.client import ModelFallback, is_invalid_json_output
from app.agents.prompts import PromptLibrary
from app.data_models.conversation_message import ConversationMessage, MessageRole
from app.data_models.lead import Lead
from app.schemas.qualification import QualificationLLMOutput
from app.services.question_plan import QuestionPlan

log = logging.getLogger("securelife.agents.qualification")


class QualificationAgentError(RuntimeError):
    """Raised when the model returned no usable output after one retry."""


class QualificationAgent:
    """One JSON-mode call over a lead's profile + transcript."""

    PROMPT_NAME = "qualification_agent"
    # Keeps prompt + transcript + max_tokens inside the model's per-minute
    # token budget. The most recent messages are kept; older ones are elided.
    MAX_TRANSCRIPT_CHARS = 12_000
    _RETRY_PREAMBLE = (
        "Return ONLY a valid JSON object with the keys verdict, dimensions, "
        "red_flags, follow_up_questions, summary. No markdown, no commentary.\n\n"
    )

    def __init__(
        self,
        *,
        client: AsyncOpenAI,
        prompt_library: PromptLibrary,
        model_name: str,
        timeout_s: int,
        max_tokens: int,
    ) -> None:
        self._client = client
        self._prompts = prompt_library
        self._models = ModelFallback.for_agent(model_name)
        self._model_used = model_name
        self._timeout_s = timeout_s
        self._max_tokens = max_tokens

    @property
    def model_name(self) -> str:
        """The model that produced the latest result (may be a fallback)."""
        return self._model_used

    async def assess(
        self, lead: Lead, messages: list[ConversationMessage]
    ) -> QualificationLLMOutput:
        """Run the agent; one strict retry on malformed output."""
        system_prompt = self._prompts.get(self.PROMPT_NAME)
        user_context = self.build_user_context(lead, messages)

        parsed = await self._call(system_prompt, user_context)
        if parsed is None:
            log.warning("Qualification agent output unusable; retrying with strict preamble")
            parsed = await self._call(system_prompt, self._RETRY_PREAMBLE + user_context)
        if parsed is None:
            raise QualificationAgentError(
                "The qualification agent did not return a usable assessment after one retry."
            )
        return parsed

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------
    def build_user_context(self, lead: Lead, messages: list[ConversationMessage]) -> str:
        """Profile checklist + transcript — everything the agent may reason about."""
        plan = QuestionPlan.for_lead(lead)
        lines: list[str] = ["# Prospect profile"]
        lines.append(f"- Insurance type: {plan.insurance_type or 'unknown'}")
        if lead.city:
            lines.append(f"- City: {lead.city}")
        for item in plan.checklist():
            if item.key in ("full_name", "contact", "insurance_type"):
                continue
            lines.append(f"- {item.label}: {item.value if item.captured else 'NOT CAPTURED'}")

        lines.append("")
        lines.append("# Conversation transcript (oldest first)")
        lines.append(self._render_transcript(messages))
        return "\n".join(lines)

    def _render_transcript(self, messages: list[ConversationMessage]) -> str:
        rendered: list[str] = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                continue
            speaker = "Prospect" if msg.role == MessageRole.USER else "Assistant"
            rendered.append(f"{speaker}: {msg.content.strip()}")
        if not rendered:
            return "(no messages)"

        # Keep the most recent turns that fit the budget.
        kept: list[str] = []
        used = 0
        for line in reversed(rendered):
            if used + len(line) > self.MAX_TRANSCRIPT_CHARS:
                kept.append("[earlier messages omitted]")
                break
            kept.append(line)
            used += len(line)
        return "\n".join(reversed(kept))

    # ------------------------------------------------------------------
    # Model call
    # ------------------------------------------------------------------
    async def _call(self, system_prompt: str, user_prompt: str) -> QualificationLLMOutput | None:
        """Returns None for output problems (retryable); transport errors raise."""
        try:
            self._model_used, response = await self._models.create(
                self._client,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=self._max_tokens,
                timeout=self._timeout_s,
            )
        except BadRequestError as exc:
            if is_invalid_json_output(exc):
                return None
            raise
        content = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not content:
            return None
        try:
            return QualificationLLMOutput.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValueError) as exc:
            log.warning("Could not parse qualification agent JSON: %s", exc)
            return None
