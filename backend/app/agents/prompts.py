"""Markdown prompt loader.

Prompts live as `.md` files under `app/prompts/`. We load them once at startup
and expose them by name. No inline triple-quoted strings in service code.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


class PromptNotFoundError(KeyError):
    pass


class PromptLibrary:
    """Loads and caches markdown prompt files from a directory."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._cache: dict[str, str] = {}

    def get(self, name: str) -> str:
        """Return the raw markdown body for a prompt name (no .md suffix)."""
        if name in self._cache:
            return self._cache[name]
        path = self._root / f"{name}.md"
        if not path.exists():
            raise PromptNotFoundError(f"Prompt file not found: {path}")
        body = path.read_text(encoding="utf-8")
        self._cache[name] = body
        return body

    def render(self, name: str, **substitutions: object) -> str:
        """Return the prompt with `{key}` substitutions applied.

        Uses `str.format_map` with a defaultdict so a missing key leaves the
        placeholder in place rather than raising — safer for partial renders.
        """
        from collections import defaultdict

        template = self.get(name)
        safe = defaultdict(lambda: "", {k: str(v) for k, v in substitutions.items()})
        return template.format_map(safe)


@lru_cache(maxsize=1)
def get_prompt_library() -> PromptLibrary:
    root = Path(__file__).resolve().parent.parent / "prompts"
    return PromptLibrary(root=root)
