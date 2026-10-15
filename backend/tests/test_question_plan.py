"""Unit tests for QuestionPlan — pure, no LLM, no DB."""
from __future__ import annotations

from app.services.question_plan import PLANS, QuestionPlan


def _plan(**fields: object) -> QuestionPlan:
    return QuestionPlan(
        full_name=fields.pop("full_name", None),  # type: ignore[arg-type]
        email=fields.pop("email", None),  # type: ignore[arg-type]
        phone=fields.pop("phone", None),  # type: ignore[arg-type]
        extracted_fields=fields,
    )


def test_every_plan_is_short() -> None:
    # The whole point: never interrogate the prospect.
    assert all(1 <= len(questions) <= 4 for questions in PLANS.values())


def test_unknown_type_has_no_detail_questions() -> None:
    plan = _plan(full_name="Rohan")
    assert plan.insurance_type is None
    assert plan.detail_questions == ()
    assert [i.group for i in plan.checklist()] == ["core"] * 5


def test_unrecognised_type_is_treated_as_unknown() -> None:
    assert _plan(insurance_type="pet").insurance_type is None


def test_motor_plan_asks_only_motor_questions() -> None:
    plan = _plan(insurance_type="motor")
    keys = {q.key for q in plan.detail_questions}
    assert keys == {"vehicle", "policy_expiry", "recent_claims"}
    rendered = plan.render_for_chat_agent()
    assert "Vehicle" in rendered
    assert "Pre-existing conditions" not in rendered
    assert "Members to cover" not in rendered


def test_missing_core_and_details() -> None:
    plan = _plan(
        full_name="Priya",
        email="p@example.com",
        insurance_type="health",
        intent="new_policy",
        members_to_cover="self 38, spouse 36",
    )
    assert [i.label for i in plan.missing_core()] == ["Timeline"]
    assert [i.label for i in plan.missing_details()] == [
        "Pre-existing conditions",
        "Current health cover",
        "Premium budget",
    ]


def test_only_name_contact_and_type_are_required_to_qualify() -> None:
    # Intent and timeline missing: still asked in chat, but not blocking.
    plan = _plan(full_name="Pradumn", phone="8576082090", insurance_type="motor")
    assert [i.label for i in plan.missing_core()] == ["Intent", "Timeline"]
    assert plan.missing_required_to_qualify() == []

    blocked = _plan(full_name="Pradumn", intent="new_policy", timeline="now")
    assert [i.label for i in blocked.missing_required_to_qualify()] == [
        "Insurance type",
        "Email or phone",
    ]


def test_completeness_counts_core_plus_details() -> None:
    plan = _plan(
        full_name="Rohan",
        phone="+919999999999",
        insurance_type="motor",
        intent="review_existing",
        timeline="now",
        vehicle="Creta 2022",
    )
    # 5 core + 3 motor details; 6 captured.
    assert plan.completeness() == round(100 * 6 / 8)


def test_false_and_zero_are_real_answers() -> None:
    plan = _plan(insurance_type="life_term", smoker=False, dependents=0)
    by_key = {i.key: i for i in plan.checklist()}
    assert by_key["smoker"].captured and by_key["smoker"].value == "no"
    assert by_key["dependents"].captured and by_key["dependents"].value == "0"


def test_chat_plan_says_wrap_up_when_complete() -> None:
    plan = _plan(
        full_name="Asha",
        email="a@example.com",
        insurance_type="other",
        intent="new_policy",
        timeline="lt_3mo",
        need_description="Cover for my bakery equipment",
        budget="Rs 20k/year",
    )
    rendered = plan.render_for_chat_agent()
    assert "Still to find out" not in rendered
    assert "wrap up" in rendered


def test_field_guide_lists_every_key_when_type_unknown() -> None:
    guide = _plan().render_field_guide()
    for questions in PLANS.values():
        for q in questions:
            assert f"`{q.key}`" in guide
