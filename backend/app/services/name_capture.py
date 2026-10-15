"""Deterministic name capture from the reply to the chat's opening question.

The chat always opens by asking what to call the prospect, and the name is
what makes a lead visible to brokers (§5.1 of ARCHITECTURE.md). A bare reply
like "Pradumn" is easy for an extractor model to dismiss as "no information",
so this class is a safety net: if the chat extractor agent didn't record a
name, the reply to the opening greeting is parsed here.

Conservative by design — it only accepts short replies made of name-like
words, and rejects anything that reads like a request ("I need car insurance").
"""
from __future__ import annotations

import re

_LEAD_IN = re.compile(
    r"^\s*(?:(?:hi|hello|hey|namaste|hii+)\b[\s,!.\-]*)?"
    r"(?:(?:i\s*am|i'm|im|my\s+name\s+is|my\s+name's|name\s+is|this\s+is|it's|its|call\s+me|it\s+is)\b\s*)?",
    re.IGNORECASE,
)
_TRAILER = re.compile(r"[\s,!.]*(?:here|this\s+side|speaking)?[\s,!.]*$", re.IGNORECASE)
_NAME_WORD = re.compile(r"^[A-Za-z][A-Za-z.'\-]*$")

# Words that mean the reply is a request or small talk, not a name.
_NOT_NAME_WORDS = frozenset(
    {
        "i", "me", "my", "we", "you", "hi", "hello", "hey", "ok", "okay", "yes", "yeah", "no",
        "nope", "sure", "thanks", "thank", "please", "need", "want", "looking", "for", "get",
        "buy", "renew", "renewal", "insurance", "insure", "cover", "policy", "car", "bike",
        "motor", "health", "life", "term", "travel", "home", "quote", "help", "claim", "urgent",
        "urgently", "what", "how", "why", "when", "where", "is", "are", "the", "a", "an", "and",
        "or", "to", "of", "in", "on", "it", "its", "am", "just", "not",
    }
)
_MAX_WORDS = 4


class GreetingNameCapture:
    """Parse a name from the prospect's reply to the opening greeting."""

    def extract(self, reply: str) -> str | None:
        """Return the name, or None if the reply doesn't look like one."""
        text = _LEAD_IN.sub("", reply.strip(), count=1)
        text = _TRAILER.sub("", text)
        words = text.split()
        if not 1 <= len(words) <= _MAX_WORDS:
            return None
        if any(not _NAME_WORD.match(w) or w.lower().strip(".'-") in _NOT_NAME_WORDS for w in words):
            return None
        return " ".join(w if any(c.isupper() for c in w) else w.capitalize() for w in words)
