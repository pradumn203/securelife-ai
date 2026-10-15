"""DocumentExtractorAgent — structured policy extraction for an uploaded PDF.

Groq's chat models are text-only, so this agent orchestrates:

1. Open the PDF with PyMuPDF and pull per-page text layers.
2. Build a chat message block with explicit `--- Page N ---` markers so the
   model can cite `source_page` in its evidence.
3. Call `chat.completions.create` with `response_format={"type": "json_object"}`
   and a prompt that demands the exact `DocumentExtractionLLMSchema` shape.
4. On a malformed response, do ONE retry with a stricter preamble.
5. Return the parsed Pydantic instance and elapsed duration.

**Limitation.** Scanned (image-only) PDFs have no text layer. The ingestor
upstream still accepts them, but extraction will see empty content for those
pages and should return `null` + `confidence: 0.0` per our prompt rules. Full
OCR is a production addition (see ARCHITECTURE.md §10).

The agent does not touch the DB. Persistence is the background task's job.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import pymupdf
from openai import AsyncOpenAI, BadRequestError

from app.agents.client import ModelFallback, is_invalid_json_output
from app.agents.prompts import PromptLibrary
from app.data_models.document import Document
from app.schemas.extraction import DocumentExtractionLLMSchema

log = logging.getLogger(__name__)


class ExtractionResult:
    """Parsed response + timing. Kept simple for the caller."""

    __slots__ = ("parsed", "duration_ms")

    def __init__(self, parsed: DocumentExtractionLLMSchema, duration_ms: int) -> None:
        self.parsed = parsed
        self.duration_ms = duration_ms


class ExtractionFailed(RuntimeError):
    """Raised when the model returned no usable structured response after retry."""


class DocumentExtractorAgent:
    """Encapsulates one extraction call for one PDF."""

    PROMPT_NAME = "document_extractor_agent"
    _USER_PREFIX = (
        "Below is the text layer of an insurance policy PDF, split by page. "
        "Extract the fields described in the system prompt. Cite `source_page` "
        "based on the page markers.\n\n"
    )
    _RETRY_PREAMBLE = (
        "Return ONLY a valid JSON object matching the described schema. No "
        "markdown code fences, no commentary, no preamble. Use null for every "
        "field you cannot find in the document."
    )

    def __init__(
        self,
        *,
        client: AsyncOpenAI,
        prompt_library: PromptLibrary,
        model_name: str,
        timeout_s: int,
        max_tokens: int,
        max_input_chars: int,
    ) -> None:
        self._client = client
        self._prompts = prompt_library
        self._models = ModelFallback.for_agent(model_name)
        self._model_used = model_name
        self._timeout_s = timeout_s
        self._max_tokens = max_tokens
        # Hard cap on how much PDF text goes into one call. Groq counts input +
        # max_tokens against the model's tokens-per-minute limit, so a long
        # policy wording would otherwise be rejected outright (413).
        self._max_input_chars = max_input_chars

    @property
    def model_name(self) -> str:
        """The model that produced the latest result (may be a fallback)."""
        return self._model_used

    async def extract(self, _doc: Document, local_path: Path) -> ExtractionResult:
        """Run one extraction. Caller handles DB persistence."""
        document_text = self._extract_text(local_path)
        system_prompt = self._prompts.get(self.PROMPT_NAME)

        started = time.monotonic()
        parsed = await self._call(
            system_prompt=system_prompt,
            user_prompt=self._USER_PREFIX + document_text,
        )
        if parsed is None:
            log.warning(
                "Extraction returned no parsed response for %s; retrying with strict preamble",
                local_path.name,
            )
            parsed = await self._call(
                system_prompt=system_prompt,
                user_prompt=f"{self._RETRY_PREAMBLE}\n\n{self._USER_PREFIX}{document_text}",
            )
        duration_ms = int((time.monotonic() - started) * 1000)

        if parsed is None:
            raise ExtractionFailed(
                "The assistant did not return a parseable extraction after one retry."
            )

        return ExtractionResult(parsed=parsed, duration_ms=duration_ms)

    # ------------------------------------------------------------------
    # PDF text layer
    # ------------------------------------------------------------------
    def _extract_text(self, local_path: Path) -> str:
        """Pull per-page text with `--- Page N ---` markers.

        Pages with no text layer (scanned images) still get a marker so the
        model can report "not visible on page N" rather than silently
        mis-attributing citations.
        """
        parts: list[str] = []
        running_chars = 0
        with pymupdf.open(local_path) as doc:
            for idx in range(doc.page_count):
                page = doc.load_page(idx)
                raw = page.get_text("text").strip() or "[no extractable text on this page]"
                block = f"--- Page {idx + 1} ---\n{raw}\n"
                if running_chars + len(block) > self._max_input_chars:
                    parts.append(
                        f"--- Page {idx + 1} ---\n"
                        "[truncated: document exceeds context window; later pages omitted]\n"
                    )
                    break
                parts.append(block)
                running_chars += len(block)
        return "".join(parts) if parts else "[document had no readable text]"

    # ------------------------------------------------------------------
    # Model call
    # ------------------------------------------------------------------
    async def _call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> DocumentExtractionLLMSchema | None:
        """One model call. Returns None for any *output* problem (so the caller
        can retry); transport / auth / rate-limit errors still raise."""
        try:
            self._model_used, response = await self._models.create(
                self._client,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=self._max_tokens,
                timeout=self._timeout_s,
            )
        except BadRequestError as exc:
            if is_invalid_json_output(exc):
                log.warning("Provider rejected the model's JSON output; treating as unparseable")
                return None
            raise
        content = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not content:
            return None
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            log.warning("Extraction JSON parse failed: %s", exc)
            return None
        try:
            return DocumentExtractionLLMSchema.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not validate parsed dict against schema: %s", exc)
            return None


__all__ = [
    "DocumentExtractorAgent",
    "ExtractionFailed",
    "ExtractionResult",
]
