"""Deterministic email / phone capture from a prospect's message.

Name + contact is what makes a lead visible to brokers, so it must not depend
on an LLM being available (rate limits, outages). Emails and Indian mobile
numbers are regular enough to read with a regex; this runs after the chat
extractor agent and fills in anything it missed.
"""
from __future__ import annotations

import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Indian mobile: optional +91 / 91 / 0 prefix, then 10 digits starting 6-9,
# allowing single spaces or dashes between digit groups.
_PHONE = re.compile(r"(?<![\d+])(?:\+?91[\s\-]?|0)?([6-9](?:[\s\-]?\d){9})(?!\d)")


class ContactCapture:
    """Find an email address and/or Indian mobile number in free text."""

    def email(self, text: str) -> str | None:
        match = _EMAIL.search(text)
        return match.group(0).rstrip(".").lower() if match else None

    def phone(self, text: str) -> str | None:
        match = _PHONE.search(text)
        if not match:
            return None
        digits = re.sub(r"\D", "", match.group(1))
        return digits if len(digits) == 10 else None
