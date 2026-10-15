"""ChatExtractorAgent — turns one chat turn into structured lead fields.

Runs after `ChatAgent` finishes streaming a reply. It reads the previous
assistant message + the prospect's latest reply and returns a
`ChatTurnExtractorOutput` (contact details + question-plan answers). The
field guide in its prompt comes from the prospect's question plan, so answers
land in the keys the chat agent and the qualification agent read.

BEST-EFFORT by design: if the call or the JSON parse fails, the agent logs and
returns an empty output. Chat continuity beats perfect extraction; a missed
fact simply stays on the chat agent's plan and is asked again.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

from openai import AsyncOpenAI

from app.agents.client import ModelFallback, get_groq_client
from app.agents.prompts import PromptLibrary, get_prompt_library
from app.data_models.lead import Lead
from app.schemas.chat import ChatTurnExtractorOutput
from app.services.question_plan import QuestionPlan
from app.settings import Settings, get_settings

log = logging.getLogger("securelife.agents.chat_extractor")


class ChatExtractorAgent:
    """Non-streaming JSON-mode extraction over a single chat turn."""

    PROMPT_NAME = "chat_extractor_agent"

    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        prompt_library: PromptLibrary | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._client = client or get_groq_client()
        self._prompts = prompt_library or get_prompt_library()
        self._settings = settings or get_settings()

    async def extract_turn(
        self,
        *,
        lead: Lead,
        assistant_message: str,
        user_message: str,
    ) -> ChatTurnExtractorOutput:
        """Run the extractor. Best-effort — never raises outward."""
        try:
            return await asyncio.wait_for(
                self._extract_turn_inner(lead, assistant_message, user_message),
                timeout=self._settings.groq_timeout_chat,
            )
        except Exception as exc:
            log.warning("Chat extractor agent failed, returning empty delta: %s", exc)
            return ChatTurnExtractorOutput()

    async def _extract_turn_inner(
        self,
        lead: Lead,
        assistant_message: str,
        user_message: str,
    ) -> ChatTurnExtractorOutput:
        current_fields = json.dumps(
            {
                "full_name": lead.full_name,
                "email": lead.email,
                "phone": lead.phone,
                "city": lead.city,
                **{k: v for k, v in (lead.extracted_fields or {}).items() if v is not None},
            },
            ensure_ascii=False,
        )
        prompt_body = self._prompts.render(
            self.PROMPT_NAME,
            today=date.today().isoformat(),
            current_fields=current_fields,
            field_guide=QuestionPlan.for_lead(lead).render_field_guide(),
            assistant_message=assistant_message or "(none — opening turn)",
            user_message=user_message,
        )

        _model, response = await ModelFallback.for_agent(
            self._settings.groq_model_chat_extractor
        ).create(
            self._client,
            messages=[
                {"role": "system", "content": prompt_body},
                {
                    "role": "user",
                    "content": "Return ONLY the JSON object. No prose, no markdown.",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=self._settings.groq_max_tokens_chat_extractor,
            timeout=self._settings.groq_timeout_chat,
        )

        text = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not text:
            return ChatTurnExtractorOutput()
        try:
            payload = json.loads(text)
            return ChatTurnExtractorOutput.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            log.warning("Could not parse chat extractor JSON: %s", exc)
            return ChatTurnExtractorOutput()
