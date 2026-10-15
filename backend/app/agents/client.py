"""Shared Groq client factory.

Groq exposes an OpenAI-compatible endpoint, so we talk to it via the official
`openai` async SDK pointed at `settings.groq_base_url`. One `AsyncOpenAI`
instance per process — the SDK handles connection pooling and transient
retries internally.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

from app.settings import get_settings

log = logging.getLogger("securelife.agents.client")


class GroqClientFactory:
    """Builds and caches the process-wide `AsyncOpenAI` client."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        max_retries: int,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is empty. Set it in backend/.env before starting the server."
            )
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries,
        )

    @property
    def client(self) -> AsyncOpenAI:
        return self._client


@lru_cache(maxsize=1)
def get_groq_factory() -> GroqClientFactory:
    """Return the cached GroqClientFactory for this process."""
    settings = get_settings()
    return GroqClientFactory(
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        max_retries=settings.groq_max_retries,
    )


def get_groq_client() -> AsyncOpenAI:
    """Convenience accessor for the raw async client."""
    return get_groq_factory().client


def reasoning_options(model_name: str) -> dict[str, str] | None:
    """Provider-specific `extra_body` for reasoning models, or None.

    gpt-oss models spend hidden reasoning tokens out of `max_tokens` before
    writing any visible output; at the default effort they can use the whole
    budget on a JSON task. Agents ask them for low effort. Other models reject
    the parameter, so it is only sent to gpt-oss.
    """
    if model_name.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low"}
    return None


def is_invalid_json_output(exc: BadRequestError) -> bool:
    """True when Groq rejected the *model's output* in JSON mode.

    Groq validates JSON mode server-side and answers 400 `json_validate_failed`
    when the generation wasn't valid JSON (e.g. reasoning used up `max_tokens`
    before any JSON was written). That's a malformed response, not a bad
    request, so JSON agents treat it like an unparseable reply and retry.
    """
    body = exc.body if isinstance(exc.body, dict) else {}
    inner = body.get("error", body)
    return isinstance(inner, dict) and inner.get("code") == "json_validate_failed"


class ModelFallback:
    """An agent's ordered list of models: its own model first, then the shared fallbacks.

    If a model is rate-limited (Groq's per-minute or per-day quota) or the
    provider fails, the same request is retried on the next model instead of
    failing the agent. Attempts that still have a fallback skip the SDK's own
    retries, so a model that's out of quota for the day costs no waiting.
    Only provider-side failures fall through; a bad request (our bug) raises.
    """

    _FALLBACK_ERRORS = (RateLimitError, InternalServerError, APITimeoutError, APIConnectionError)

    def __init__(self, models: Sequence[str]) -> None:
        self._models = list(dict.fromkeys(m for m in models if m))
        if not self._models:
            raise ValueError("ModelFallback needs at least one model")

    @classmethod
    def for_agent(cls, primary: str) -> ModelFallback:
        return cls([primary, *get_settings().groq_fallback_model_list])

    @property
    def models(self) -> list[str]:
        return list(self._models)

    @property
    def primary(self) -> str:
        return self._models[0]

    async def create(self, client: AsyncOpenAI, **kwargs: Any) -> tuple[str, Any]:
        """`chat.completions.create` with fallback. Returns (model actually used, response)."""
        for i, model in enumerate(self._models):
            is_last = i == len(self._models) - 1
            with_options = getattr(client, "with_options", None)
            attempt = client if is_last or with_options is None else with_options(max_retries=0)
            try:
                response = await attempt.chat.completions.create(
                    model=model, extra_body=reasoning_options(model), **kwargs
                )
                return model, response
            except self._FALLBACK_ERRORS as exc:
                if is_last:
                    raise
                log.warning(
                    "Model %s unavailable (%s); falling back to %s",
                    model,
                    _failure_reason(exc),
                    self._models[i + 1],
                )
        raise AssertionError("unreachable")


def _failure_reason(exc: Exception) -> str:
    """Short reason for logs, e.g. "RateLimitError: tokens per day (TPD)"."""
    match = re.search(r"on ((?:tokens|requests) per (?:minute|day) \(\w+\))", str(exc))
    return f"{type(exc).__name__}: {match.group(1)}" if match else type(exc).__name__
