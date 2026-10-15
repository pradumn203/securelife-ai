"""Question plans — what a broker needs to know, per insurance type.

One registry drives the whole qualification flow:

* `ChatAgent` is told, every turn, exactly which facts are still missing for
  this prospect's insurance type, so it asks targeted questions and stops
  asking once the plan is complete.
* `ChatExtractorAgent` gets the matching field guide, so answers land in
  well-known `extracted_fields` keys.
* `LeadOut.profile_checklist` / `profile_completeness` render the plan for
  the broker.
* `QualificationAgent` sees which details are captured and which are missing.

Every plan is deliberately short (2–4 questions). Core facts (name, contact,
insurance type, intent, timeline) are shared by every plan; type-specific
facts are only asked once the insurance type is known.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PlanQuestion:
    """One fact the broker needs.

    `key` is the field name under `Lead.extracted_fields` (or a Lead column
    for the core contact facts). `ask` tells the chat agent what to find out;
    `hint` tells the chat extractor agent how to record the answer.
    """

    key: str
    label: str
    ask: str
    hint: str


@dataclass(frozen=True, slots=True)
class ChecklistItem:
    """A plan question resolved against one lead."""

    key: str
    label: str
    group: str  # "core" | "details"
    value: str | None

    @property
    def captured(self) -> bool:
        return self.value is not None


# --- Core facts every plan shares ---------------------------------------------

# Order matters: it's the order the chat agent asks in. Insurance type comes
# straight after the name because every later question depends on it.
CORE_QUESTIONS: tuple[PlanQuestion, ...] = (
    PlanQuestion("full_name", "Name", "how they'd like the broker to address them", "proper name, titles stripped"),
    PlanQuestion(
        "insurance_type",
        "Insurance type",
        "what kind of cover they want — health, life, motor, home, travel…",
        "one of health | life_term | life_whole | motor | home | travel | investment_linked | multiple | other",
    ),
    PlanQuestion("intent", "Intent", "whether they want a new policy, a review of an existing one, or claim help", "one of new_policy | review_existing | claim_help | other"),
    PlanQuestion("contact", "Email or phone", "an email address or phone number the broker can use", "email and/or Indian phone number"),
    PlanQuestion(
        "timeline",
        "Timeline",
        "when they want it sorted",
        "one of now | lt_3mo | gt_3mo | undecided — map relative to today's date: 'urgent', 'asap', 'this week/month' → now; a date or month within 3 months → lt_3mo; later dates or a later year → gt_3mo; 'not sure', 'just looking' → undecided",
    ),
)

# The minimum the qualification agent needs to say anything useful: who the
# prospect is, how to reach them, and what product they want. Intent and
# timeline are still asked in chat and shown to the agent, but a missing one
# doesn't block qualification — the agent judges urgency from the transcript.
REQUIRED_TO_QUALIFY: tuple[str, ...] = ("full_name", "contact", "insurance_type")

# --- Type-specific plans -------------------------------------------------------

_LIFE_SAVINGS_PLAN: tuple[PlanQuestion, ...] = (
    PlanQuestion("age", "Age", "their age", "integer years"),
    PlanQuestion("goal", "Goal", "what the money is for (retirement, child's education, wealth building, legacy)", "short phrase"),
    PlanQuestion("horizon", "Time horizon", "how many years they can stay invested", "e.g. '15 years'"),
    PlanQuestion("budget", "Premium budget", "a comfortable monthly or yearly premium", "amount + period in INR, e.g. 'Rs 10k/month'"),
)

PLANS: dict[str, tuple[PlanQuestion, ...]] = {
    "health": (
        PlanQuestion("members_to_cover", "Members to cover", "who the policy should cover (self, spouse, children, parents) and their ages", "e.g. 'self 38, spouse 36, kids 8 and 11'"),
        PlanQuestion("health_conditions", "Pre-existing conditions", "any ongoing health conditions for anyone to be covered — 'none' is a fine answer", "short list, or 'none' when explicitly denied"),
        PlanQuestion("existing_cover", "Current health cover", "any health cover they already have (employer or personal) and roughly its sum insured", "one line, or 'none'"),
        PlanQuestion("budget", "Premium budget", "a comfortable yearly premium, or the cover amount they have in mind", "amount in INR, e.g. 'Rs 25k/year' or '10L cover'"),
    ),
    "life_term": (
        PlanQuestion("age", "Age", "their age", "integer years"),
        PlanQuestion("income_band", "Annual income", "their rough annual income — the cover is usually sized from it", "one of <5L | 5-15L | 15-30L | >30L"),
        PlanQuestion("dependents", "Dependents", "how many people depend on their income", "integer"),
        PlanQuestion("smoker", "Tobacco use", "whether they use tobacco in any form — ask neutrally", "true / false"),
    ),
    "life_whole": _LIFE_SAVINGS_PLAN,
    "investment_linked": _LIFE_SAVINGS_PLAN,
    "motor": (
        PlanQuestion("vehicle", "Vehicle", "the vehicle's make, model and year", "e.g. 'Hyundai Creta 2022'"),
        PlanQuestion("policy_expiry", "Policy status", "whether it's a brand-new vehicle, or has a current policy — and if so when it expires", "short phrase in their terms, e.g. 'brand-new vehicle', 'renewal, expires 2026-11-05', 'used car, previous policy (expiry not given)', 'policy lapsed'"),
        PlanQuestion("recent_claims", "Claims last year", "whether they made a claim in the last policy year (this decides their no-claim bonus)", "'no claims' or a short description"),
    ),
    "home": (
        PlanQuestion("home_ownership", "Own or rent", "whether they own or rent the home", "one of own | rent"),
        PlanQuestion("property_value", "Property value", "the type of home and its rough value (skip value if they rent)", "e.g. '2BHK flat, ~Rs 80L'"),
        PlanQuestion("contents_value", "Contents value", "a rough value of furniture, electronics and valuables to cover", "amount in INR"),
    ),
    "travel": (
        PlanQuestion("destination", "Destination", "where they're travelling", "countries or region"),
        PlanQuestion("trip_dates", "Trip dates", "when they leave and how long the trip is", "e.g. '12 Dec, 3 weeks'"),
        PlanQuestion("travellers", "Travellers", "how many people are travelling and their ages", "e.g. '2 adults (34, 36)'"),
        PlanQuestion("health_conditions", "Pre-existing conditions", "any ongoing health conditions among the travellers — 'none' is fine", "short list, or 'none'"),
    ),
    "multiple": (
        PlanQuestion("products_wanted", "Products wanted", "which kinds of cover they want and which matters most", "e.g. 'health first, then term life'"),
        PlanQuestion("members_to_cover", "Household", "who in the household needs cover and their ages", "e.g. 'self 40, spouse 38, son 10'"),
        PlanQuestion("income_band", "Annual income", "their rough annual income", "one of <5L | 5-15L | 15-30L | >30L"),
        PlanQuestion("budget", "Premium budget", "a comfortable total yearly premium", "amount in INR"),
    ),
    "other": (
        PlanQuestion("need_description", "What they need", "what they want covered, in their own words", "one sentence"),
        PlanQuestion("budget", "Premium budget", "a comfortable premium", "amount in INR"),
    ),
}


class QuestionPlan:
    """Resolves the question plan for one lead.

    Takes plain values (not an ORM row) so the same logic serves the chat
    agents, the API schemas and the qualification orchestrator.
    """

    def __init__(
        self,
        *,
        full_name: str | None,
        email: str | None,
        phone: str | None,
        extracted_fields: Mapping[str, Any] | None,
    ) -> None:
        self._full_name = full_name
        self._email = email
        self._phone = phone
        self._fields = dict(extracted_fields or {})

    @classmethod
    def for_lead(cls, lead: Any) -> QuestionPlan:
        """Build from anything with `full_name`, `email`, `phone`, `extracted_fields`."""
        return cls(
            full_name=lead.full_name,
            email=lead.email,
            phone=lead.phone,
            extracted_fields=_as_dict(lead.extracted_fields),
        )

    # ------------------------------------------------------------------
    # Plan resolution
    # ------------------------------------------------------------------
    @property
    def insurance_type(self) -> str | None:
        value = _display(self._fields.get("insurance_type"))
        return value if value in PLANS else None

    @property
    def detail_questions(self) -> tuple[PlanQuestion, ...]:
        """Type-specific questions, empty until the insurance type is known."""
        insurance_type = self.insurance_type
        return PLANS[insurance_type] if insurance_type else ()

    def checklist(self) -> list[ChecklistItem]:
        items = [
            ChecklistItem(q.key, q.label, "core", self._core_value(q.key)) for q in CORE_QUESTIONS
        ]
        items += [
            ChecklistItem(q.key, q.label, "details", _display(self._fields.get(q.key)))
            for q in self.detail_questions
        ]
        return items

    def missing_core(self) -> list[ChecklistItem]:
        return [item for item in self.checklist() if item.group == "core" and not item.captured]

    def missing_required_to_qualify(self) -> list[ChecklistItem]:
        """Facts the qualification agent can't run without (see REQUIRED_TO_QUALIFY)."""
        return [item for item in self.missing_core() if item.key in REQUIRED_TO_QUALIFY]

    def missing_details(self) -> list[ChecklistItem]:
        return [item for item in self.checklist() if item.group == "details" and not item.captured]

    def completeness(self) -> int:
        """Percent of the plan captured. Unknown type counts core facts only."""
        items = self.checklist()
        captured = sum(1 for item in items if item.captured)
        return round(100 * captured / len(items)) if items else 0

    # ------------------------------------------------------------------
    # Prompt rendering
    # ------------------------------------------------------------------
    def render_for_chat_agent(self) -> str:
        """The per-turn question plan block injected into `chat_agent.md`."""
        questions = {q.key: q for q in (*CORE_QUESTIONS, *self.detail_questions)}
        missing = [item for item in self.checklist() if not item.captured]
        captured = [item for item in self.checklist() if item.captured]

        lines: list[str] = []
        insurance_type = self.insurance_type
        if insurance_type:
            lines.append(f"Insurance type: {insurance_type}.")
        else:
            lines.append(
                "Insurance type: not known yet. Find it out early — the follow-up "
                "questions depend on it. Do not ask type-specific questions until you know it."
            )
        if missing:
            lines.append("Still to find out, in this order (one or two per turn):")
            lines += [f"- {questions[item.key].label}: {questions[item.key].ask}" for item in missing]
        else:
            lines.append(
                "Everything the broker needs is captured. Do not ask further qualifying "
                "questions — wrap up now (see 'When you have everything')."
            )
        if captured:
            lines.append("Already captured — never ask again:")
            lines += [f"- {item.label}: {item.value}" for item in captured]
        return "\n".join(lines)

    def render_field_guide(self) -> str:
        """Field guide for `chat_extractor_agent.md`.

        Known type → that plan's keys. Unknown type → every plan's keys, since
        the prospect may name the type and answer details in the same message.
        """
        plans = (
            {self.insurance_type: self.detail_questions} if self.insurance_type else PLANS
        )
        lines: list[str] = []
        seen: set[str] = set()
        for insurance_type, questions in plans.items():
            for q in questions:
                if q.key in seen:
                    continue
                seen.add(q.key)
                lines.append(f"- `{q.key}` ({q.label}; {insurance_type}): {q.hint}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _core_value(self, key: str) -> str | None:
        if key == "full_name":
            return _display(self._full_name)
        if key == "contact":
            parts = [p for p in (_display(self._email), _display(self._phone)) if p]
            return " · ".join(parts) if parts else None
        return _display(self._fields.get(key))


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    return dump() if callable(dump) else {}


def _display(value: Any) -> str | None:
    """Render a captured value for prompts/UI; None means 'not captured'.

    Booleans and zero are real answers ("no tobacco", "0 dependents").
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (list, tuple, set, dict)):
        return ", ".join(str(v) for v in value) if value else None
    return str(value)
