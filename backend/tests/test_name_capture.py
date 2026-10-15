"""GreetingNameCapture — the deterministic name safety net."""
from __future__ import annotations

import pytest

from app.services.name_capture import GreetingNameCapture


@pytest.mark.parametrize(
    ("reply", "name"),
    [
        ("Pradumn", "Pradumn"),
        ("pradumn", "Pradumn"),
        ("Pradumn Kumar Mishra", "Pradumn Kumar Mishra"),
        ("I'm Rohan", "Rohan"),
        ("hi, my name is Priya Nair.", "Priya Nair"),
        ("Call me Sam", "Sam"),
        ("This is Arjun here", "Arjun"),
        ("Pradumn this side", "Pradumn"),
        ("D'Souza", "D'Souza"),
    ],
)
def test_accepts_names(reply: str, name: str) -> None:
    assert GreetingNameCapture().extract(reply) == name


@pytest.mark.parametrize(
    "reply",
    [
        "Hi",
        "hello!",
        "I need car insurance",
        "renew my policy urgently",
        "yes",
        "what is this?",
        "my number is 9876543210",
        "Hi there, I am looking for a health plan for my whole family",
        "",
    ],
)
def test_rejects_non_names(reply: str) -> None:
    assert GreetingNameCapture().extract(reply) is None
