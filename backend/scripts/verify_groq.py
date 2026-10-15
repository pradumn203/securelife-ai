"""Smoke-test Groq configuration.

Run: `uv run python scripts/verify_groq.py` from `backend/`.

Checks:
  1. API key is set in .env.
  2. The configured chat model is reachable through the OpenAI-compatible endpoint.
  3. A trivial chat completion returns a non-empty response.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.client import get_groq_client  # noqa: E402
from app.settings import get_settings  # noqa: E402


class GroqVerifier:
    def __init__(self) -> None:
        self._settings = get_settings()

    def check_key(self) -> None:
        if not self._settings.groq_api_key:
            raise SystemExit("GROQ_API_KEY is not set in backend/.env")
        print(f"[ok] GROQ_API_KEY present (length={len(self._settings.groq_api_key)})")
        print(f"[..] Base URL: {self._settings.groq_base_url}")

    async def check_completion(self) -> None:
        client = get_groq_client()
        model = self._settings.groq_model_chat
        print(f"[..] Calling {model} with a trivial prompt ...")
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            temperature=0,
            # Reasoning models (gpt-oss) emit a hidden chain-of-thought before
            # the visible answer, so a tiny budget returns an empty string.
            max_tokens=512,
            timeout=self._settings.groq_timeout_chat,
        )
        text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
        print(f"[ok] Response: {text!r}")
        if not text:
            raise SystemExit(
                "Empty response from the assistant. Check model name and quota."
            )

    async def run(self) -> None:
        self.check_key()
        await self.check_completion()
        print("[done] Verification succeeded.")


if __name__ == "__main__":
    asyncio.run(GroqVerifier().run())
