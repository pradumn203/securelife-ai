"""Seed the database with 7 synthetic prospects — at least one per dashboard tab.

Run from `backend/`:
    uv run python scripts/seed.py            # append (skips if "Priya Nair" already exists)
    uv run python scripts/seed.py --reset    # wipe the DB file and rebuild from scratch

Every prospect follows the question plan for their insurance type, and every
stored qualification quotes the prospect's seeded messages verbatim — the same
contract the live qualification agent is held to. All values are synthetic.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.data_models import (  # noqa: E402
    Analysis,
    CloseReason,
    ConversationMessage,
    Document,
    DocumentExtraction,
    DocumentStatus,
    Lead,
    LeadSource,
    LeadStatus,
    MessageRole,
    Qualification,
)
from app.db import get_db, init_db, shutdown_db  # noqa: E402
from app.settings import get_settings  # noqa: E402

GREETING = (
    "Hi! I'm SecureLife's AI assistant. I can help you figure out the right insurance "
    "cover and connect you to a human broker when you're ready. To start — what should "
    "I call you?"
)


def _dim(key: str, score: int, rationale: str, quote: str | None) -> dict:
    return {
        "key": key,
        "score": score,
        "rationale": rationale,
        "evidence_quote": quote,
        "evidence_verified": quote is not None,
    }


class DemoSeeder:
    """Inserts a canned set of prospects + conversations + agent results."""

    def __init__(self) -> None:
        self._now = datetime.now(timezone.utc)

    def _conversation(self, lead: Lead, turns: list[tuple[str, str]]) -> list[ConversationMessage]:
        """Greeting + alternating (prospect, assistant) turns, a minute apart."""
        start = self._now - timedelta(minutes=2 * len(turns) + 5)
        greeting = ConversationMessage(lead=lead, role=MessageRole.ASSISTANT, content=GREETING)
        greeting.created_at = start - timedelta(minutes=1)
        rows = [greeting]
        for idx, (prospect, assistant) in enumerate(turns):
            user_msg = ConversationMessage(lead=lead, role=MessageRole.USER, content=prospect)
            user_msg.created_at = start + timedelta(minutes=2 * idx)
            reply = ConversationMessage(lead=lead, role=MessageRole.ASSISTANT, content=assistant)
            reply.created_at = start + timedelta(minutes=2 * idx + 1)
            rows += [user_msg, reply]
        return rows

    async def seed(self) -> None:
        async with get_db().session() as session:
            existing = (
                await session.execute(select(Lead).where(Lead.full_name == "Priya Nair"))
            ).scalar_one_or_none()
            if existing is not None:
                print("[skip] Priya Nair already present — seed appears to have run.")
                return

            print("[..] Inserting prospects …")

            # 1) NEW LEAD — health, mid-conversation (plan partly captured).
            anika = Lead(
                full_name="Anika Rao",
                phone="+919820012345",
                city="Mumbai",
                source=LeadSource.WEB,
                status=LeadStatus.NEW,
                extracted_fields={
                    "insurance_type": "health",
                    "intent": "new_policy",
                    "timeline": "lt_3mo",
                    "members_to_cover": "self 31, parents 58 and 62",
                },
            )
            session.add(anika)
            session.add_all(
                self._conversation(
                    anika,
                    [
                        ("Anika. I want health insurance for me and my parents.",
                         "Thanks Anika. Is this a new policy, or are you reviewing something you already have?"),
                        ("New one. Hoping to get it done in the next month or two.",
                         "Got it. Who exactly should it cover, and how old is everyone?"),
                        ("Me, I'm 31, and my parents are 58 and 62. My number is +91 98200 12345.",
                         "Thank you. Does anyone have an ongoing health condition the broker should know about? 'None' is a perfectly good answer."),
                    ],
                )
            )

            # 2) NEW LEAD — motor, plan complete, waiting for the broker to run qualification.
            vikram = Lead(
                full_name="Vikram Shah",
                email="vikram.shah@example.com",
                city="Ahmedabad",
                source=LeadSource.WEB,
                status=LeadStatus.NEW,
                extracted_fields={
                    "insurance_type": "motor",
                    "intent": "review_existing",
                    "timeline": "now",
                    "vehicle": "Honda City 2019",
                    "policy_expiry": "2026-10-28",
                    "recent_claims": "no claims",
                },
            )
            session.add(vikram)
            session.add_all(
                self._conversation(
                    vikram,
                    [
                        ("Vikram here. My car insurance is up for renewal and the quote looks high.",
                         "Thanks Vikram — happy to help with the renewal. What car is it, and what year?"),
                        ("Honda City, 2019 model. Policy expires on 28 October.",
                         "Got it. Did you make any claims in the last policy year? That decides your no-claim bonus."),
                        ("No claims at all. Email me at vikram.shah@example.com, I want this sorted this week.",
                         "Perfect, thanks Vikram. So — a renewal for your 2019 City expiring on 28 October, no claims this year, and I'll reach you at vikram.shah@example.com. A broker will be in touch shortly. You can also upload your current policy PDF right now for a free coverage review."),
                    ],
                )
            )

            # 3) IN PROGRESS — term life, qualified, no documents yet.
            meera = Lead(
                full_name="Meera Iyer",
                email="meera.iyer@example.com",
                phone="+919840011122",
                city="Chennai",
                source=LeadSource.WEB,
                status=LeadStatus.IN_PROGRESS,
                qualification_score=84,
                qualification_verdict="QUALIFIED",
                extracted_fields={
                    "insurance_type": "life_term",
                    "intent": "new_policy",
                    "timeline": "now",
                    "age": 35,
                    "income_band": "15-30L",
                    "dependents": 2,
                    "smoker": False,
                },
            )
            session.add(meera)
            session.add_all(
                self._conversation(
                    meera,
                    [
                        ("Meera Iyer. I need a term plan, I don't have any life cover right now.",
                         "Thanks Meera. Starting fresh is a good moment to get it right. How old are you, and roughly what's your annual income?"),
                        ("I'm 35, income is around 22 lakh a year.",
                         "Got it. How many people depend on your income?"),
                        ("Two — my daughter and my mother. I want this done this month.",
                         "Understood. Do you use tobacco in any form?"),
                        ("No, never. You can call me on 98400 11122 or email meera.iyer@example.com.",
                         "Thanks Meera. So — a new term plan at 35 for your daughter and mother, sorted this month. A broker will call you shortly, and you're welcome to upload any existing policy PDFs for a free review."),
                    ],
                )
            )
            session.add(
                Qualification(
                    lead=meera,
                    verdict="QUALIFIED",
                    score=84,
                    dimensions=[
                        _dim("need_clarity", 5, "New term plan with no existing life cover and two dependents.", "I don't have any life cover right now"),
                        _dim("urgency", 5, "Wants it done within the month.", "I want this done this month"),
                        _dim("budget_fit", 4, "22L income comfortably supports a 2-3 Cr term premium at 35.", "income is around 22 lakh a year"),
                        _dim("coverage_gap", 4, "Sole earner for two dependents with zero life cover.", "my daughter and my mother"),
                        _dim("engagement", 3, "Answered every question directly; shared both phone and email.", None),
                    ],
                    red_flags=[],
                    follow_up_questions=[
                        "Do you have any employer-provided group life cover we should net off?",
                        "Any outstanding loans (home, car) the cover should also protect?",
                    ],
                    missing_details=[],
                    summary="35-year-old sole earner with two dependents and no life cover wants a term plan this month. Strong, time-bound need.",
                    model_name="seeded",
                    raw_llm_response={"seeded": True},
                )
            )

            # 4) DOCUMENTS PENDING REVIEW — motor renewal, qualified, policy extracted,
            #    analysis not run yet (run it live in the demo).
            arjun = Lead(
                full_name="Arjun Kapoor",
                email="arjun.kapoor@example.com",
                phone="+919811022233",
                city="Bengaluru",
                source=LeadSource.WEB,
                status=LeadStatus.DOCS_PENDING,
                qualification_score=88,
                qualification_verdict="QUALIFIED",
                extracted_fields={
                    "insurance_type": "motor",
                    "intent": "review_existing",
                    "timeline": "now",
                    "vehicle": "Maruti Swift 2020",
                    "policy_expiry": "renewal, expires 2026-11-05",
                    "recent_claims": "no claims",
                    "wants_to_upload": True,
                },
            )
            session.add(arjun)
            session.add_all(
                self._conversation(
                    arjun,
                    [
                        ("Arjun. My car insurance renews next month and I want a better deal.",
                         "Thanks Arjun — happy to help with the renewal. What car is it, and what year?"),
                        ("A Maruti Swift, 2020. The policy expires on 5 November.",
                         "Got it. Did you make any claims in the last policy year? That decides your no-claim bonus."),
                        ("No claims. arjun.kapoor@example.com — I want this sorted before it lapses.",
                         "Thanks Arjun. So — a renewal for your 2020 Swift expiring on 5 November, no claims this year. A broker will reach out at arjun.kapoor@example.com, and you can upload your current policy PDF now for a free coverage review."),
                        ("Uploading it now.",
                         "Thanks — the broker will review it before they call."),
                    ],
                )
            )
            session.add(
                Qualification(
                    lead=arjun,
                    verdict="QUALIFIED",
                    score=88,
                    dimensions=[
                        _dim("need_clarity", 5, "Specific renewal with a clear goal: a better deal.", "My car insurance renews next month and I want a better deal"),
                        _dim("urgency", 5, "Fixed expiry date within weeks.", "The policy expires on 5 November"),
                        _dim("budget_fit", 3, "No budget stated; motor premiums rarely block.", None),
                        _dim("coverage_gap", 4, "Renewal window with a full no-claim bonus to protect.", "No claims"),
                        _dim("engagement", 5, "Answered every question and shared the policy.", "Uploading it now"),
                    ],
                    red_flags=[],
                    follow_up_questions=[
                        "Do you want zero-depreciation and engine-protect on the renewal?",
                        "Is the IDV on the current policy close to what the car is worth today?",
                    ],
                    missing_details=[],
                    summary="Motor renewal with a fixed 5 November expiry, a clean claims record and the policy already shared. Ready for document review.",
                    model_name="seeded",
                    raw_llm_response={"seeded": True},
                )
            )
            arjun_doc = Document(
                lead=arjun,
                original_filename="ICICI-Lombard-Motor-Swift-2025.pdf",
                stored_path="data/uploads/seed-arjun-icici-motor.pdf",
                mime_type="application/pdf",
                size_bytes=184_220,
                page_count=6,
                status=DocumentStatus.EXTRACTED,
            )
            session.add(arjun_doc)
            session.add(
                DocumentExtraction(
                    document=arjun_doc,
                    policy_type="Motor",
                    provider="ICICI Lombard General Insurance",
                    policy_number="3001/MO/22871634/00/000",
                    insured_name="Arjun Kapoor",
                    sum_insured=Decimal("520000"),
                    premium_amount=Decimal("11240"),
                    premium_frequency="annual",
                    renewal_date=date(2026, 11, 5),
                    exclusions=[
                        {"text": "Damage while driving under the influence of alcohol or drugs.", "source_page": 4},
                        {"text": "Consequential loss, wear and tear, and mechanical breakdown.", "source_page": 4},
                    ],
                    riders=[
                        {"name": "Zero Depreciation", "description": "Full claim on plastic, rubber and fibre parts without depreciation.", "source_page": 3},
                    ],
                    evidence={
                        "policy_type": {"value": "Private Car Package Policy", "source_page": 1, "source_excerpt": "PRIVATE CAR PACKAGE POLICY - SCHEDULE", "confidence": 0.97},
                        "provider": {"value": "ICICI Lombard General Insurance Company Limited", "source_page": 1, "source_excerpt": "ICICI Lombard General Insurance Company Limited, Mumbai", "confidence": 0.99},
                        "policy_number": {"value": "3001/MO/22871634/00/000", "source_page": 1, "source_excerpt": "Policy No.: 3001/MO/22871634/00/000", "confidence": 0.98},
                        "insured_name": {"value": "Arjun Kapoor", "source_page": 1, "source_excerpt": "Name of Insured: Mr. Arjun Kapoor", "confidence": 0.96},
                        "sum_insured": {"value": "Rs. 5,20,000 (IDV)", "source_page": 2, "source_excerpt": "Insured Declared Value (IDV): Rs. 5,20,000", "confidence": 0.95},
                        "premium_amount": {"value": "Rs. 11,240", "source_page": 2, "source_excerpt": "Total Premium (incl. GST): Rs. 11,240", "confidence": 0.93},
                        "premium_frequency": {"value": "Annual", "source_page": 1, "source_excerpt": "Period of Insurance: 06-Nov-2025 to 05-Nov-2026", "confidence": 0.9},
                        "renewal_date": {"value": "05-Nov-2026", "source_page": 1, "source_excerpt": "Period of Insurance: 06-Nov-2025 to 05-Nov-2026", "confidence": 0.97},
                    },
                    raw_llm_response={"seeded": True},
                    model_name="seeded",
                    extraction_duration_ms=0,
                )
            )

            # 5) COMPLETED ANALYSIS — health review with an extracted policy and an analysis. The demo star.
            priya = Lead(
                full_name="Priya Nair",
                email="priya.nair@example.com",
                phone="+919845543201",
                city="Bengaluru",
                source=LeadSource.WEB,
                status=LeadStatus.ANALYZED,
                qualification_score=88,
                qualification_verdict="QUALIFIED",
                extracted_fields={
                    "insurance_type": "health",
                    "intent": "review_existing",
                    "timeline": "lt_3mo",
                    "members_to_cover": "self 38, husband 40, kids 8 and 11",
                    "health_conditions": "none",
                    "existing_cover": "Star Health 5L family floater",
                    "budget": "up to Rs 30k a year",
                    "wants_to_upload": True,
                },
                conversation_summary=(
                    "Family of four in Bengaluru on a 5L floater; wants a review before the April renewal."
                ),
            )
            session.add(priya)
            session.add_all(
                self._conversation(
                    priya,
                    [
                        ("Priya Nair. I want to review my family health insurance, I think the cover is too low.",
                         "Thanks Priya — a second opinion on family cover is a smart move. Who does the policy cover, and how old is everyone?"),
                        ("Me 38, my husband 40, and our two kids who are 8 and 11. It's a Star Health floater for 5 lakh.",
                         "Got it, a 5 lakh floater across four people. Any ongoing health conditions a broker should know about? 'None' is a perfectly good answer."),
                        ("None for any of us. I could spend up to 30k a year if the cover is much better.",
                         "That's helpful. When would you like this sorted, and what's the best way to reach you?"),
                        ("In the next couple of months, before the April renewal. priya.nair@example.com works. I'll upload the policy now.",
                         "Thanks Priya. So — a review of your 5 lakh Star Health floater for the four of you, a budget of up to 30k a year, before the April renewal. A broker will reach out at priya.nair@example.com shortly."),
                    ],
                )
            )
            session.add(
                Qualification(
                    lead=priya,
                    verdict="QUALIFIED",
                    score=88,
                    dimensions=[
                        _dim("need_clarity", 5, "Specific concern: a 5L floater across four people.", "I think the cover is too low"),
                        _dim("urgency", 4, "Fixed deadline at the April renewal.", "before the April renewal"),
                        _dim("budget_fit", 5, "30k/year comfortably buys a 15-20L floater for this family.", "I could spend up to 30k a year"),
                        _dim("coverage_gap", 4, "5L floater is thin for four lives in Bengaluru.", "It's a Star Health floater for 5 lakh"),
                        _dim("engagement", 4, "Volunteered details and offered to upload the policy.", "I'll upload the policy now"),
                    ],
                    red_flags=[],
                    follow_up_questions=[
                        "Does either of you have employer group health cover that could be layered with a top-up?",
                        "Would you consider a super top-up instead of switching insurers before April?",
                    ],
                    missing_details=[],
                    summary="Family of four on a thin 5L floater with a 30k budget and an April renewal deadline. High-value health review.",
                    model_name="seeded",
                    raw_llm_response={"seeded": True},
                )
            )

            priya_doc = Document(
                lead=priya,
                original_filename="StarHealth-FamilyFloater-2025.pdf",
                stored_path="data/uploads/seed-priya-starhealth.pdf",
                mime_type="application/pdf",
                size_bytes=312_104,
                page_count=14,
                status=DocumentStatus.EXTRACTED,
            )
            session.add(priya_doc)
            session.add(
                DocumentExtraction(
                    document=priya_doc,
                    policy_type="Health",
                    provider="Star Health and Allied Insurance",
                    policy_number="SH/BG/20250412-00987",
                    insured_name="Priya Nair",
                    sum_insured=Decimal("500000"),
                    premium_amount=Decimal("18420"),
                    premium_frequency="annual",
                    renewal_date=date(2026, 4, 11),
                    exclusions=[
                        {"text": "Pre-existing diseases waiting period: 24 months from inception.", "source_page": 7},
                        {"text": "Maternity benefits excluded under this product variant.", "source_page": 8},
                        {"text": "Any treatment arising out of adventure sports.", "source_page": 9},
                    ],
                    riders=[
                        {
                            "name": "Hospital Cash",
                            "description": "₹2,000 per day for up to 30 days of hospitalization.",
                            "source_page": 10,
                        }
                    ],
                    evidence={
                        "policy_type": {"value": "Health", "source_page": 1, "source_excerpt": "FAMILY HEALTH OPTIMA INSURANCE PLAN — Schedule of Benefits", "confidence": 0.98},
                        "provider": {"value": "Star Health and Allied Insurance Co. Ltd.", "source_page": 1, "source_excerpt": "Issued by Star Health and Allied Insurance Co. Ltd., Chennai.", "confidence": 0.99},
                        "policy_number": {"value": "SH/BG/20250412-00987", "source_page": 2, "source_excerpt": "Policy No.: SH/BG/20250412-00987", "confidence": 0.97},
                        "insured_name": {"value": "Priya Nair", "source_page": 2, "source_excerpt": "Proposer: Priya Nair (DoB 06-Jun-1988)", "confidence": 0.95},
                        "sum_insured": {"value": "Rs. 5,00,000", "source_page": 2, "source_excerpt": "Sum Insured: Rs. 5,00,000 (Five Lakhs only) — floater basis.", "confidence": 0.96},
                        "premium_amount": {"value": "Rs. 18,420 (incl. GST)", "source_page": 2, "source_excerpt": "Annual premium payable: Rs. 18,420 (inclusive of applicable GST).", "confidence": 0.9},
                        "premium_frequency": {"value": "Annual", "source_page": 2, "source_excerpt": "Mode of payment: Annual", "confidence": 0.99},
                        "renewal_date": {"value": "11-Apr-2026", "source_page": 2, "source_excerpt": "Policy Period: 12-Apr-2025 to 11-Apr-2026 (both days inclusive).", "confidence": 0.97},
                    },
                    raw_llm_response={"seeded": True},
                    model_name="seeded",
                    extraction_duration_ms=0,
                )
            )
            session.add(
                Analysis(
                    lead=priya,
                    coverage_gaps=[
                        {"area": "sum_insured_adequacy", "description": "₹5L floater is thin for a Bengaluru family of 4. One critical-illness hospitalization can exhaust the cover.", "severity": "high"},
                        {"area": "maternity_cover", "description": "Current product excludes maternity. Not a current need but noted for lifecycle.", "severity": "low"},
                        {"area": "critical_illness_rider", "description": "No critical-illness rider captured on the health policy.", "severity": "medium"},
                    ],
                    potential_savings={
                        "annual_inr": 9600,
                        "rationale": "A ₹15L floater from a comparable insurer would price around ₹25–28K/yr, within the stated 30k budget; dropping the hospital-cash rider (duplicative with higher sum insured) saves ~₹9,600 annually.",
                    },
                    risk_flags=[
                        {"flag": "under_insured_floater", "description": "Floater of ₹5L spread across 4 lives is below typical Bengaluru hospitalization costs for cardiac events (~₹7–10L).", "severity": "high"},
                        {"flag": "renewal_soon", "description": "Policy renews on 11 Apr 2026 — the window to switch without a break in coverage.", "severity": "medium"},
                    ],
                    recommended_action=(
                        "Pitch a ₹15–20L family floater with a critical-illness rider at the April renewal, "
                        "within the ₹30k budget Priya mentioned."
                    ),
                    confidence=78,
                    model_name="seeded",
                    raw_llm_response={"seeded": True},
                )
            )

            # 6) CLOSED (disqualified) — wants guaranteed returns, which insurance can't promise.
            karan = Lead(
                full_name="Karan Mehta",
                email="karan.mehta@example.com",
                city="Pune",
                source=LeadSource.WEB,
                status=LeadStatus.CLOSED,
                close_reason=CloseReason.DISQUALIFIED,
                close_note="Wants guaranteed 2-year doubling; suggested a mutual fund SIP instead.",
                qualification_score=36,
                qualification_verdict="NOT_QUALIFIED",
                extracted_fields={
                    "insurance_type": "investment_linked",
                    "intent": "other",
                    "timeline": "undecided",
                    "age": 27,
                    "goal": "double the money quickly",
                    "horizon": "2 years",
                },
            )
            session.add(karan)
            session.add_all(
                self._conversation(
                    karan,
                    [
                        ("Karan. I want an insurance plan that doubles my money in 2 years, guaranteed.",
                         "Thanks Karan. I should be upfront — insurance-linked plans can't promise guaranteed doubling. Could you tell me a bit about what the money is for?"),
                        ("Just want quick returns honestly. Not sure when I'd buy, just checking options.",
                         "Understood. How old are you, and what premium would feel comfortable?"),
                        ("27. karan.mehta@example.com. I don't really want to commit to a monthly amount.",
                         "Thanks Karan, I've noted that. A broker can explain realistic options if you'd like — you can reach us any time."),
                    ],
                )
            )
            session.add(
                Qualification(
                    lead=karan,
                    verdict="NOT_QUALIFIED",
                    score=36,
                    dimensions=[
                        _dim("need_clarity", 2, "Wants short-term guaranteed returns, which insurance doesn't offer.", "doubles my money in 2 years, guaranteed"),
                        _dim("urgency", 1, "No timeline; only browsing.", "just checking options"),
                        _dim("budget_fit", 1, "Unwilling to commit to any premium.", "I don't really want to commit to a monthly amount"),
                        _dim("coverage_gap", 2, "No protection need expressed.", None),
                        _dim("engagement", 3, "Answered questions but kept the conversation short.", None),
                    ],
                    dealbreakers=[
                        {"reason": "Expects guaranteed returns from an insurance product", "evidence_quote": "doubles my money in 2 years, guaranteed", "evidence_verified": True},
                        {"reason": "Won't commit to any premium", "evidence_quote": "I don't really want to commit to a monthly amount", "evidence_verified": True},
                    ],
                    red_flags=[
                        "No budget and no timeline — browsing only",
                    ],
                    follow_up_questions=[
                        "Would a mutual fund SIP better match a 2-year return goal than an insurance plan?",
                    ],
                    missing_details=["Premium budget"],
                    summary="Looking for guaranteed short-term returns, which insurance can't provide, with no budget or timeline. Not a fit right now.",
                    model_name="seeded",
                    raw_llm_response={"seeded": True},
                )
            )

            # 7) CLOSED (purchased) — won.
            rohan = Lead(
                full_name="Rohan Gupta",
                email="rohan.gupta@example.com",
                phone="+919920033344",
                city="Delhi",
                source=LeadSource.WEB,
                status=LeadStatus.CLOSED,
                close_reason=CloseReason.PURCHASED,
                close_note="Bought a ₹1Cr term plan through the senior broker on 2026-10-02.",
                qualification_score=92,
                qualification_verdict="QUALIFIED",
                extracted_fields={
                    "insurance_type": "life_term",
                    "intent": "new_policy",
                    "timeline": "now",
                    "age": 29,
                    "income_band": "5-15L",
                    "dependents": 1,
                    "smoker": False,
                },
            )
            session.add(rohan)
            session.add(
                Qualification(
                    lead=rohan,
                    verdict="QUALIFIED",
                    score=92,
                    dimensions=[
                        _dim("need_clarity", 5, "New term plan for a dependent spouse.", None),
                        _dim("urgency", 5, "Wanted it immediately.", None),
                        _dim("budget_fit", 4, "Income supports a 1Cr term premium at 29.", None),
                        _dim("coverage_gap", 5, "No existing life cover.", None),
                        _dim("engagement", 4, "Fast, complete answers.", None),
                    ],
                    red_flags=[],
                    follow_up_questions=[],
                    missing_details=[],
                    summary="29-year-old with a dependent spouse and no life cover; ready to buy.",
                    model_name="seeded",
                    raw_llm_response={"seeded": True},
                )
            )

            # Dates: spread the prospects over the past fortnight.
            await session.flush()
            vikram.created_at = self._now - timedelta(hours=5)
            meera.created_at = self._now - timedelta(days=1)
            arjun.created_at = self._now - timedelta(days=2)
            priya.created_at = self._now - timedelta(days=3)
            karan.created_at = self._now - timedelta(days=4)
            rohan.created_at = self._now - timedelta(days=12)

            await session.commit()
            print(
                "[done] 7 prospects inserted: 2 new leads, 1 in progress, 1 documents "
                "pending review, 1 completed analysis, 2 closed (disqualified, purchased)."
            )


async def run(reset: bool) -> None:
    if reset:
        db_file = Path(get_settings().database_url.replace("sqlite+aiosqlite:///", ""))
        # SQLite's WAL side files belong to the old database; remove them too.
        for path in (db_file, Path(f"{db_file}-wal"), Path(f"{db_file}-shm")):
            if not path.exists():
                continue
            try:
                path.unlink()
            except PermissionError:
                raise SystemExit(
                    f"[error] {path} is in use. Stop the backend (uvicorn) first, then rerun."
                ) from None
            print(f"[reset] Deleted {path}")

    await init_db()
    try:
        await DemoSeeder().seed()
    except OperationalError as exc:
        if "no such column" in str(exc) or "no such table" in str(exc):
            raise SystemExit(
                "[error] The database file doesn't match the current schema. Stop the backend, "
                "then run: uv run python scripts/seed.py --reset  (this wipes existing data)."
            ) from None
        raise
    finally:
        await shutdown_db()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete the DB file before seeding.")
    args = parser.parse_args()
    # Ensure we're writing to backend/data/securelife.db relative to backend/
    os.chdir(Path(__file__).resolve().parent.parent)
    asyncio.run(run(reset=args.reset))


if __name__ == "__main__":
    main()
