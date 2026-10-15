"""Unit tests for `app.agents.errors.user_safe_message`.

The point of this module is "no raw provider string ever reaches the UI". We
assert both that each error class maps to the right canonical sentence AND
that the returned text never contains the original exception message.
"""
from __future__ import annotations

import asyncio

import pytest

from app.agents.errors import MESSAGES, UserFacingError, user_safe_message


class _FakeStatusError(Exception):
    """Mimics a provider exception that exposes `status_code`."""

    def __init__(self, status_code: int, raw_message: str) -> None:
        super().__init__(raw_message)
        self.status_code = status_code


class _FakeCodeAttr(Exception):
    def __init__(self, code: int, raw_message: str) -> None:
        super().__init__(raw_message)
        self.code = code


# ----------------------------------------------------------------------
# Mapping â€” status code â†’ canonical message
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("status_code", "expected_key"),
    [
        (429, "rate_limited"),
        (500, "unavailable"),
        (502, "unavailable"),
        (503, "unavailable"),
        (504, "unavailable"),
        (408, "timeout"),
        (400, "bad_request"),
        (404, "bad_request"),
        (422, "bad_request"),
        (401, "unauthorised"),
        (403, "unauthorised"),
    ],
)
def test_status_code_mapping(status_code: int, expected_key: str) -> None:
    secret_raw = "DO NOT LEAK: provider says the model is at capacity"
    msg = user_safe_message(_FakeStatusError(status_code, secret_raw))
    assert msg == MESSAGES[expected_key]
    assert secret_raw not in msg


def test_code_attr_also_routes() -> None:
    """SDKs that expose `.code` instead of `.status_code` still get translated."""
    msg = user_safe_message(_FakeCodeAttr(429, "quota exceeded raw"))
    assert msg == MESSAGES["rate_limited"]


# ----------------------------------------------------------------------
# Mapping â€” exception class â†’ canonical message
# ----------------------------------------------------------------------
def test_asyncio_timeout() -> None:
    msg = user_safe_message(asyncio.TimeoutError())
    assert msg == MESSAGES["timeout"]


def test_builtin_timeout() -> None:
    msg = user_safe_message(TimeoutError("socket timed out"))
    assert msg == MESSAGES["timeout"]


def test_unknown_exception_falls_back_to_generic() -> None:
    msg = user_safe_message(RuntimeError("some internal state is garbage"))
    assert msg == MESSAGES["generic"]
    assert "garbage" not in msg


def test_connect_error_mapped_to_network() -> None:
    class ConnectError(Exception):
        pass

    msg = user_safe_message(ConnectError("getaddrinfo failed for api.somewhere"))
    assert msg == MESSAGES["network"]
    assert "getaddrinfo" not in msg


# ----------------------------------------------------------------------
# Invariant â€” no raw provider text ever leaks out
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "exc",
    [
        _FakeStatusError(503, "stack trace included for devs: at line 404"),
        _FakeStatusError(500, "database password=hunter2 was in request"),
        _FakeStatusError(429, "API KEY abc123def456 has exceeded quota"),
        RuntimeError("stacktrace with internals"),
        TimeoutError("waited 42s for google"),
    ],
)
def test_no_raw_message_leaks(exc: Exception) -> None:
    rendered = user_safe_message(exc)
    raw = str(exc)
    assert raw not in rendered


# ----------------------------------------------------------------------
# UserFacingError exposes its own message safely
# ----------------------------------------------------------------------
def test_user_facing_error_carries_message() -> None:
    err = UserFacingError("friendly to show", cause=RuntimeError("ugly"))
    assert err.message == "friendly to show"
    assert str(err) == "friendly to show"
    assert isinstance(err.__cause__, RuntimeError)


# ----------------------------------------------------------------------
# All canonical messages are stable, short, and non-technical.
# ----------------------------------------------------------------------
def test_canonical_messages_shape() -> None:
    for key, text in MESSAGES.items():
        assert text.endswith("."), f"{key} should be a complete sentence"
        assert len(text) < 160, f"{key} is too long ({len(text)} chars)"
        # Nothing in these messages should reference internals.
        for banned in ("groq", "openai", "qwen", "api", "exception", "traceback", "sdk"):
            assert banned not in text.lower(), f"{key} leaks {banned!r}"
