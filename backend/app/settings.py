"""Application configuration loaded from environment and .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings. All values can be overridden by env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Groq (OpenAI-compatible endpoint)
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # One model per agent. On Groq's free tier every model has its own
    # tokens-per-minute bucket (8000), so agents are spread across models such
    # that consecutive broker steps (qualify → extract → analyse) never hit the
    # same bucket, and the per-turn chat extractor never competes with chat.
    groq_model_chat: str = "qwen/qwen3.8-27b"
    groq_model_chat_extractor: str = "openai/gpt-oss-20b"
    groq_model_qualification: str = "openai/gpt-oss-20b"
    groq_model_extraction: str = "openai/gpt-oss-120b"
    groq_model_analysis: str = "qwen/qwen3.8-27b"

    # When an agent's model is rate-limited (per-minute or per-day quota) or
    # unavailable, the call moves down this list. The free tier gives each
    # model its own 200k tokens/day, so the fallback triples daily headroom.
    groq_fallback_models: str = "qwen/qwen3.8-27b,openai/gpt-oss-120b,openai/gpt-oss-20b"

    groq_timeout_chat: int = 60
    groq_timeout_qualification: int = 60
    groq_timeout_extraction: int = 120
    groq_timeout_analysis: int = 60
    groq_max_retries: int = 3

    # Per-agent output-token caps. Groq can reject a request whose `max_tokens`
    # exceeds the org's output-tokens-per-minute limit (1000 on the free tier)
    # with a 429 before a single token is generated, so every cap stays under it.
    # Raise them if your Groq tier allows.
    groq_max_tokens_chat: int = 400
    groq_max_tokens_chat_extractor: int = 400
    groq_max_tokens_qualification: int = 900
    groq_max_tokens_extraction: int = 900
    groq_max_tokens_analysis: int = 900

    # How much PDF text (characters) the document extractor agent sends per
    # call. Groq counts input + max_tokens against the model's tokens-per-
    # minute limit (8000 for gpt-oss-120b on the free tier); ~18k chars of
    # policy text + the prompt + 900 output tokens fits under it. Later pages
    # beyond the budget are dropped with a visible `[truncated]` marker.
    groq_extraction_max_input_chars: int = 18_000

    # Qualification agent: a QUALIFIED verdict needs an overall score (0-100,
    # aggregated server-side from the agent's per-dimension scores) at or above
    # this threshold.
    qualification_threshold: int = 70
    # A NEEDS_MORE_INFO verdict becomes NOT_QUALIFIED when the score is below
    # this AND the agent raised red flags: a low score with concrete red flags
    # is a no, not a request for more questions.
    qualification_reject_below: int = 45

    # Storage
    database_url: str = "sqlite+aiosqlite:///./data/securelife.db"
    upload_dir: str = "./data/uploads"

    # CORS
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174"
    )

    # Logging
    log_level: str = "INFO"

    # Paths
    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def groq_fallback_model_list(self) -> list[str]:
        return [m.strip() for m in self.groq_fallback_models.split(",") if m.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
