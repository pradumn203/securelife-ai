"""Qualification agent + scorer tests — no network, no DB.

The scorer is where the anti-hallucination guarantees live, so it gets the
most coverage: quotes are verified against the prospect's words, unverified
dimensions are capped, and the overall score/verdict are server-computed.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agents.prompts import get_prompt_library
from app.agents.qualification_agent import QualificationAgent, QualificationAgentError
from app.data_models.conversation_message import ConversationMessage, MessageRole
from app.data_models.lead import Lead
from app.schemas.qualification import Dealbreaker, DimensionAssessment, QualificationLLMOutput
from app.services.qualification import QualificationScorer

PROSPECT_TEXT = (
    "Car insurance please, my Creta's policy runs out on the 14th.\n"
    "No claims this year, and I’d like to sort it this week."
)


def _output(verdict: str = "QUALIFIED", **overrides: dict) -> QualificationLLMOutput:
    dims = {
        "need_clarity": {"score": 5, "evidence_quote": "my Creta's policy runs out on the 14th"},
        "urgency": {"score": 5, "evidence_quote": "I'd like to sort it this week"},
        "budget_fit": {"score": 3, "evidence_quote": None},
        "coverage_gap": {"score": 4, "evidence_quote": "policy runs out on the 14th"},
        "engagement": {"score": 4, "evidence_quote": "No claims this year"},
    }
    for key, patch in overrides.items():
        dims[key] = {**dims[key], **patch}
    return QualificationLLMOutput(
        verdict=verdict,  # type: ignore[arg-type]
        dimensions=[
            DimensionAssessment(key=k, rationale=f"{k} rationale", **v)  # type: ignore[arg-type]
            for k, v in dims.items()
        ],
        red_flags=["  ", "Policy lapses in days"],
        follow_up_questions=[],
        summary=" Strong motor renewal lead. ",
    )


# --- Scorer -----------------------------------------------------------------


def test_verified_quotes_keep_their_scores_and_score_is_server_computed() -> None:
    final = QualificationScorer(threshold=70).finalize(
        _output(), prospect_text=PROSPECT_TEXT, missing_details=[]
    )
    by_key = {d.key: d for d in final.dimensions}
    # Curly apostrophe in the transcript still matches the straight one in the quote.
    assert by_key["urgency"].evidence_verified is True
    assert by_key["urgency"].score == 5
    # (5 + 5 + 3 + 4 + 4) / 25
    assert final.score == 84
    assert final.verdict == "QUALIFIED"
    assert final.red_flags == ["Policy lapses in days"]
    assert final.summary == "Strong motor renewal lead."


def test_invented_quote_is_dropped_and_dimension_capped() -> None:
    output = _output(urgency={"score": 5, "evidence_quote": "I need this done today"})
    final = QualificationScorer(threshold=70).finalize(
        output, prospect_text=PROSPECT_TEXT, missing_details=[]
    )
    urgency = next(d for d in final.dimensions if d.key == "urgency")
    assert urgency.evidence_verified is False
    assert urgency.evidence_quote is None
    assert urgency.score == QualificationScorer.UNVERIFIED_SCORE_CAP


def test_missing_and_unknown_dimensions_are_normalised() -> None:
    output = QualificationLLMOutput(
        verdict="NEEDS_MORE_INFO",
        dimensions=[
            DimensionAssessment(key="urgency", score=4, evidence_quote="sort it this week"),
            DimensionAssessment(key="vibes", score=5),
        ],
    )
    final = QualificationScorer(threshold=70).finalize(
        output, prospect_text=PROSPECT_TEXT, missing_details=[]
    )
    assert [d.key for d in final.dimensions] == [
        "need_clarity",
        "urgency",
        "budget_fit",
        "coverage_gap",
        "engagement",
    ]
    assert final.score == round(100 * 4 / 25)


def test_qualified_downgraded_when_plan_details_missing() -> None:
    final = QualificationScorer(threshold=70).finalize(
        _output(), prospect_text=PROSPECT_TEXT, missing_details=["Vehicle"]
    )
    assert final.verdict == "NEEDS_MORE_INFO"
    # With no agent follow-ups, the broker still gets something actionable.
    assert final.follow_up_questions == ["Ask the prospect about: vehicle."]


def test_qualified_downgraded_below_threshold() -> None:
    final = QualificationScorer(threshold=90).finalize(
        _output(), prospect_text=PROSPECT_TEXT, missing_details=[]
    )
    assert final.verdict == "NEEDS_MORE_INFO"


def test_not_qualified_verdict_is_respected() -> None:
    final = QualificationScorer(threshold=70).finalize(
        _output("NOT_QUALIFIED"), prospect_text=PROSPECT_TEXT, missing_details=[]
    )
    assert final.verdict == "NOT_QUALIFIED"


def test_hedged_verdict_on_a_bad_fit_becomes_not_qualified() -> None:
    # Observed live: a 44/100 prospect with explicit red flags came back
    # NEEDS_MORE_INFO. Low score + red flags is a no.
    weak = _output(
        "NEEDS_MORE_INFO",
        need_clarity={"score": 1},
        urgency={"score": 1},
        coverage_gap={"score": 1},
        engagement={"score": 2},
    )
    final = QualificationScorer(threshold=70, reject_below=45).finalize(
        weak, prospect_text=PROSPECT_TEXT, missing_details=[]
    )
    assert final.score < 45
    assert final.verdict == "NOT_QUALIFIED"

    # Same low score but no red flags: still "needs more info".
    weak.red_flags = []
    final = QualificationScorer(threshold=70, reject_below=45).finalize(
        weak, prospect_text=PROSPECT_TEXT, missing_details=[]
    )
    assert final.verdict == "NEEDS_MORE_INFO"


def test_verified_dealbreaker_forces_not_qualified() -> None:
    # A strong score can't outweigh something disqualifying the prospect said.
    output = _output("QUALIFIED")
    output.dealbreakers = [
        Dealbreaker(reason="Wants it within the week", evidence_quote="sort it this week"),
    ]
    final = QualificationScorer(threshold=70).finalize(
        output, prospect_text=PROSPECT_TEXT, missing_details=[]
    )
    assert final.score >= 70
    assert final.verdict == "NOT_QUALIFIED"
    assert final.dealbreakers[0].evidence_verified is True


def test_unverifiable_dealbreaker_is_dropped() -> None:
    output = _output("QUALIFIED")
    output.dealbreakers = [
        Dealbreaker(reason="Wants guaranteed returns", evidence_quote="double my money guaranteed"),
        Dealbreaker(reason="No quote at all", evidence_quote=None),
    ]
    final = QualificationScorer(threshold=70).finalize(
        output, prospect_text=PROSPECT_TEXT, missing_details=[]
    )
    assert final.dealbreakers == []
    assert final.verdict == "QUALIFIED"


def test_missing_summary_gets_a_deterministic_fallback() -> None:
    output = _output()
    output.summary = "  "
    final = QualificationScorer(threshold=70).finalize(
        output, prospect_text=PROSPECT_TEXT, missing_details=[]
    )
    assert final.summary.startswith("Qualified. Strongest signal: need clarity (5/5)")


def test_llm_output_is_lenient_on_slips() -> None:
    parsed = QualificationLLMOutput.model_validate(
        {
            "verdict": "needs more info",
            "dimensions": [{"key": "urgency", "score": 7.6, "evidence_quote": "  "}],
        }
    )
    assert parsed.verdict == "NEEDS_MORE_INFO"
    assert parsed.dimensions[0].score == 5
    assert parsed.dimensions[0].evidence_quote is None


# --- Agent ------------------------------------------------------------------


class _FakeCompletions:
    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.calls: list[dict] = []

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        content = self._contents[len(self.calls) - 1]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _agent(contents: list[str]) -> tuple[QualificationAgent, _FakeCompletions]:
    completions = _FakeCompletions(contents)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    agent = QualificationAgent(
        client=client,  # type: ignore[arg-type]
        prompt_library=get_prompt_library(),
        model_name="openai/gpt-oss-20b",
        timeout_s=5,
        max_tokens=900,
    )
    return agent, completions


def _lead_and_messages() -> tuple[Lead, list[ConversationMessage]]:
    lead = Lead(
        full_name="Rohan Gupta",
        email="rohan@example.com",
        city="Pune",
        extracted_fields={"insurance_type": "motor", "vehicle": "Hyundai Creta 2022"},
    )
    messages = [
        ConversationMessage(role=MessageRole.ASSISTANT, content="Hi! What should I call you?"),
        ConversationMessage(role=MessageRole.USER, content="Rohan. Car insurance please."),
    ]
    return lead, messages


@pytest.mark.asyncio
async def test_agent_retries_once_then_parses() -> None:
    good = json.dumps({"verdict": "NEEDS_MORE_INFO", "dimensions": [], "summary": "Thin."})
    agent, completions = _agent(["not json", good])
    lead, messages = _lead_and_messages()
    result = await agent.assess(lead, messages)
    assert result.verdict == "NEEDS_MORE_INFO"
    assert len(completions.calls) == 2
    # gpt-oss models are asked for low reasoning effort so JSON fits the cap.
    assert completions.calls[0]["extra_body"] == {"reasoning_effort": "low"}


@pytest.mark.asyncio
async def test_agent_raises_after_second_bad_output() -> None:
    agent, _ = _agent(["", "{not valid"])
    lead, messages = _lead_and_messages()
    with pytest.raises(QualificationAgentError):
        await agent.assess(lead, messages)


def test_context_marks_missing_plan_facts_and_labels_speakers() -> None:
    agent, _ = _agent([])
    lead, messages = _lead_and_messages()
    context = agent.build_user_context(lead, messages)
    assert "- Insurance type: motor" in context
    assert "- Vehicle: Hyundai Creta 2022" in context
    assert "- Policy status: NOT CAPTURED" in context
    assert "Prospect: Rohan. Car insurance please." in context
    assert "Assistant: Hi! What should I call you?" in context
