"""ContactCapture — contact details never depend on an LLM."""
from __future__ import annotations

import pytest

from app.services.contact_capture import ContactCapture


@pytest.mark.parametrize(
    ("text", "phone"),
    [
        ("8576082090", "8576082090"),
        ("call me on +91 98765 01234", "9876501234"),
        ("my number is 91-9876501234.", "9876501234"),
        ("098765-01234", "9876501234"),
        ("2026, 8576082090", "8576082090"),
        ("I'm 26 and it expires in 2027", None),
        ("policy no 3001223344556", None),
        ("5123456789", None),
    ],
)
def test_phone(text: str, phone: str | None) -> None:
    assert ContactCapture().phone(text) == phone


@pytest.mark.parametrize(
    ("text", "email"),
    [
        ("rahul.test@example.com", "rahul.test@example.com"),
        ("mail me at Priya.Nair@Example.co.in.", "priya.nair@example.co.in"),
        ("no email, just call", None),
    ],
)
def test_email(text: str, email: str | None) -> None:
    assert ContactCapture().email(text) == email
