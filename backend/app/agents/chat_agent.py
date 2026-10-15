"""ChatAgent — the prospect-facing conversational agent (streaming).

Separation of concerns:
    * This class owns the LLM-call shape (messages list, streaming loop). It
      does NOT touch the DB.
    * The router owns transactional work (persist user msg → stream → persist
      assistant msg → hand the turn to `ChatExtractorAgent`). This keeps the
      agent testable without a session.

Resilience: streaming failures are reported inline via `error` SSE events; we
don't retry across the stream (the SDK handles transient 5xx under the hood).
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.agents.client import ModelFallback, get_groq_client
from app.agents.errors import user_safe_message
from app.agents.prompts import PromptLibrary, get_prompt_library
from app.data_models.conversation_message import ConversationMessage, MessageRole
from app.data_models.lead import Lead
from app.services.question_plan import QuestionPlan
from app.settings import Settings, get_settings

log = logging.getLogger("securelife.agents.chat")


class ChatAgentError(RuntimeError):
    """Raised when the Groq streaming call fails hard. Message is user-safe."""


class ChatAgent:
    """Streams the assistant's reply for one prospect turn."""

    PROMPT_NAME = "chat_agent"

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

    async def stream_reply(
        self,
        *,
        lead: Lead,
        history: list[ConversationMessage],
    ) -> AsyncIterator[str]:
        """Yield assistant text chunks as the Groq stream produces them.

        `history` MUST already include the current user turn as the final entry
        (the router persists it before calling us). We build a chronological
        OpenAI-style `messages` list with the system prompt first.
        """
        messages = self._build_messages(lead, history)

        try:
            _model, stream = await ModelFallback.for_agent(self._settings.groq_model_chat).create(
                self._client,
                messages=messages,
                temperature=0.6,
                max_tokens=self._settings.groq_max_tokens_chat,
                stream=True,
                timeout=self._settings.groq_timeout_chat,
            )
        except Exception as exc:
            log.exception(
                "Failed to open chat stream (model=%s)",
                self._settings.groq_model_chat,
            )
            raise ChatAgentError(user_safe_message(exc)) from exc

        try:
            async for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                text = getattr(delta, "content", None) if delta is not None else None
                if text:
                    yield text
        except Exception as exc:
            log.exception(
                "Chat stream failed mid-flight (model=%s)",
                self._settings.groq_model_chat,
            )
            raise ChatAgentError(user_safe_message(exc)) from exc

    def _build_messages(
        self, lead: Lead, history: list[ConversationMessage]
    ) -> list[dict[str, Any]]:
        """Convert the agent prompt + history to OpenAI message format.

        Rules:
            * System row first (from `chat_agent.md`), with the prospect's
              question plan rendered in: which facts are still missing for
              their insurance type, and which are already captured. This is
              what keeps the agent's questions targeted and finite.
            * SYSTEM-role DB rows are dropped (we never persist those, but
              we're defensive).
            * ASSISTANT → role="assistant", USER → role="user".
        """
        system_prompt = self._prompts.render(
            self.PROMPT_NAME,
            question_plan=QuestionPlan.for_lead(lead).render_for_chat_agent(),
        )

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for msg in history:
            if msg.role == MessageRole.SYSTEM:
                continue
            role = "assistant" if msg.role == MessageRole.ASSISTANT else "user"
            messages.append({"role": role, "content": msg.content})
        return messages
