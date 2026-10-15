"""ModelFallback — rate-limited models hand the call to the next one."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError, RateLimitError

from app.agents.client import ModelFallback

_REQ = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def _rate_limited() -> RateLimitError:
    return RateLimitError(
        "tokens per day (TPD): Limit 200000", response=httpx.Response(429, request=_REQ), body=None
    )


class _FakeClient:
    """Fails with the queued exception per model, else returns a response."""

    def __init__(self, failures: dict[str, Exception]) -> None:
        self.failures = failures
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **_: object) -> _FakeClient:
        return self

    async def create(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        exc = self.failures.get(str(kwargs["model"]))
        if exc:
            raise exc
        return f"response from {kwargs['model']}"


@pytest.mark.asyncio
async def test_rate_limited_model_falls_back_to_next() -> None:
    client = _FakeClient({"openai/gpt-oss-20b": _rate_limited()})
    models = ModelFallback(["openai/gpt-oss-20b", "qwen/qwen3.8-27b"])
    used, response = await models.create(client, messages=[])  # type: ignore[arg-type]
    assert used == "qwen/qwen3.8-27b"
    assert response == "response from qwen/qwen3.8-27b"
    # Reasoning options follow the model actually called.
    assert client.calls[0]["extra_body"] == {"reasoning_effort": "low"}
    assert client.calls[1]["extra_body"] is None


@pytest.mark.asyncio
async def test_bad_request_is_not_hidden_by_fallback() -> None:
    bad = BadRequestError("bad", response=httpx.Response(400, request=_REQ), body=None)
    client = _FakeClient({"openai/gpt-oss-20b": bad})
    with pytest.raises(BadRequestError):
        await ModelFallback(["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]).create(client)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_last_model_failure_raises() -> None:
    client = _FakeClient({"a": _rate_limited(), "b": _rate_limited()})
    with pytest.raises(RateLimitError):
        await ModelFallback(["a", "b"]).create(client)  # type: ignore[arg-type]


def test_for_agent_puts_the_agents_model_first_without_duplicates() -> None:
    models = ModelFallback.for_agent("openai/gpt-oss-120b").models
    assert models[0] == "openai/gpt-oss-120b"
    assert len(models) == len(set(models))
