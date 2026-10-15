"""User-facing error translation for the LLM transport.

Design rule for this codebase: NEVER surface a provider exception string to
the UI. Translate exceptions to a short, friendly, non-technical sentence at
the boundary where they would otherwise leave the backend; the full exception
goes to the logs via `log.exception(...)`.

Callers:
    * `app.agents.chat_agent.ChatAgent.stream_reply` wraps the chat call.
    * `app.routers.chat` emits SSE `error` frames using the translated text.
    * `app.routers.documents.extract_document_task` stores the translated text
      in `Document.error_message` so the UI can render it directly.
    * `app.routers.analysis` returns the translated text under HTTP 502.

If you add a new agent, pass `user_safe_message(exc)` to whatever will end up
visible to the user.
"""
from __future__ import annotations

import asyncio
import logging

try:
    import openai as _openai  # type: ignore[import]

    _OPENAI_APISTATUS = getattr(_openai, "APIStatusError", None)
    _OPENAI_RATE_LIMIT = getattr(_openai, "RateLimitError", None)
    _OPENAI_TIMEOUT = getattr(_openai, "APITimeoutError", None)
    _OPENAI_CONNECT = getattr(_openai, "APIConnectionError", None)
    _OPENAI_UNAUTHZ = getattr(_openai, "AuthenticationError", None)
    _OPENAI_BAD = getattr(_openai, "BadRequestError", None)
except Exception:  # pragma: no cover - SDK absent in some tests
    _OPENAI_APISTATUS = None
    _OPENAI_RATE_LIMIT = None
    _OPENAI_TIMEOUT = None
    _OPENAI_CONNECT = None
    _OPENAI_UNAUTHZ = None
    _OPENAI_BAD = None


log = logging.getLogger("securelife.errors")


# ---------------------------------------------------------------------------
# Canonical, UI-safe copy. Keep sentences short, non-technical, actionable.
# ---------------------------------------------------------------------------
MESSAGES = {
    "unavailable": "The assistant is briefly unavailable. Please try again in a minute.",
    "rate_limited": "We've hit our AI usage limit for the moment. Please try again shortly.",
    "timeout": "The assistant took too long to reply. Please try again.",
    "bad_request": "Something about that message confused the assistant. Please rephrase and try again.",
    "unauthorised": "The assistant isn't configured correctly. Please contact support.",
    "network": "Could not reach the assistant service. Please check your connection and try again.",
    "generic": "Something went wrong while talking to the assistant. Please try again.",
}


class UserFacingError(RuntimeError):
    """Carries both a UI-safe `.message` and the original cause."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.__cause__ = cause


def _status_code_of(exc: BaseException) -> int | None:
    """Pull a status code off a provider exception without hard-coding the SDK."""
    for attr in ("status_code", "code", "http_status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def user_safe_message(exc: BaseException) -> str:
    """Translate `exc` into one short, user-safe sentence.

    Logs the full exception at INFO so the mapping is observable in dev.
    Does NOT include `str(exc)` or any provider detail in the returned text.
    """
    log.info("Translating exception for UI: %s: %s", type(exc).__name__, exc)

    # OpenAI SDK typed errors (used by Groq via the compatible endpoint).
    if _OPENAI_RATE_LIMIT is not None and isinstance(exc, _OPENAI_RATE_LIMIT):
        return MESSAGES["rate_limited"]
    if _OPENAI_TIMEOUT is not None and isinstance(exc, _OPENAI_TIMEOUT):
        return MESSAGES["timeout"]
    if _OPENAI_UNAUTHZ is not None and isinstance(exc, _OPENAI_UNAUTHZ):
        return MESSAGES["unauthorised"]
    if _OPENAI_CONNECT is not None and isinstance(exc, _OPENAI_CONNECT):
        return MESSAGES["network"]
    if _OPENAI_BAD is not None and isinstance(exc, _OPENAI_BAD):
        return MESSAGES["bad_request"]

    # Timeouts (asyncio or wrapped by SDK)
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return MESSAGES["timeout"]

    # Any exception with a status code we can route on.
    code = _status_code_of(exc)
    if code is not None:
        if code == 429:
            return MESSAGES["rate_limited"]
        if code in (500, 502, 503, 504):
            return MESSAGES["unavailable"]
        if code == 408:
            return MESSAGES["timeout"]
        if code in (400, 404, 422):
            return MESSAGES["bad_request"]
        if code in (401, 403):
            return MESSAGES["unauthorised"]

    # Catch-all for `APIStatusError` without a numeric code we recognised.
    if _OPENAI_APISTATUS is not None and isinstance(exc, _OPENAI_APISTATUS):
        return MESSAGES["generic"]

    # Transport-level network issues (hostname resolution, refused connection).
    name = type(exc).__name__
    if name in {"ConnectError", "ConnectTimeout", "RemoteProtocolError", "ReadError"}:
        return MESSAGES["network"]

    return MESSAGES["generic"]
