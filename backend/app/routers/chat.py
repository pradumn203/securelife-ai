"""Chat router — session bootstrap + SSE streaming.

The POST /sessions handler creates a Lead row, persists the opening greeting as
an ASSISTANT message so turn 1 has history, and returns `{lead_id, greeting}`.

The POST /stream handler persists the user turn, streams the `ChatAgent` reply
via SSE, persists the assistant text, then hands the turn to the
`ChatExtractorAgent` in a background task that updates the Lead's captured
fields.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.agents.chat_agent import ChatAgent, ChatAgentError
from app.agents.chat_extractor_agent import ChatExtractorAgent
from app.agents.errors import MESSAGES, user_safe_message
from app.data_models.conversation_message import MessageRole
from app.db import get_db
from app.repositories.conversations import ConversationMessageRepository
from app.repositories.leads import LeadRepository
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionOut,
    ChatStreamIn,
)
from app.services.contact_capture import ContactCapture
from app.services.name_capture import GreetingNameCapture

log = logging.getLogger("securelife.router.chat")

router = APIRouter()

GREETING_TEXT = (
    "Hi! I'm SecureLife's AI assistant. I can help you figure out the right "
    "insurance cover and connect you to a human broker when you're ready. "
    "To start — what should I call you?"
)


# ----------------------------------------------------------------------
# POST /api/chat/sessions
# ----------------------------------------------------------------------
@router.post("/sessions", response_model=ChatSessionOut)
async def create_session(body: ChatSessionCreate) -> ChatSessionOut:
    """Create a new chat session (Lead row) and return the opening greeting."""
    db = get_db()
    async with db.session() as session:
        leads = LeadRepository(session)
        messages = ConversationMessageRepository(session)
        lead = await leads.create_lead(source=body.source)
        await messages.append(
            lead_id=lead.id, role=MessageRole.ASSISTANT, content=GREETING_TEXT
        )
        await session.commit()
        return ChatSessionOut(lead_id=lead.id, greeting=GREETING_TEXT)


# ----------------------------------------------------------------------
# POST /api/chat/stream
# ----------------------------------------------------------------------
@router.post("/stream")
async def stream_chat(body: ChatStreamIn) -> StreamingResponse:
    """SSE endpoint: streams assistant tokens for the next turn."""

    # Validate the lead exists BEFORE opening the SSE stream so we can
    # return a proper 404 instead of an SSE error event.
    db = get_db()
    async with db.session() as session:
        leads_repo = LeadRepository(session)
        lead = await leads_repo.get_by_id(body.lead_id)
        if lead is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead {body.lead_id} not found",
            )

    handler = ChatStreamHandler(lead_id=body.lead_id, user_message=body.message)
    return StreamingResponse(
        handler.events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Response-Timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


class ChatStreamHandler:
    """Owns the lifecycle of a single POST /stream request.

    Why a class: the SSE generator needs to coordinate three persistence steps,
    a token stream, and a post-stream extractor. Keeping it in a class makes
    the state (accumulated assistant text, message_id) explicit.
    """

    def __init__(self, *, lead_id: str, user_message: str) -> None:
        self._lead_id = lead_id
        self._user_message = user_message
        # Agents are built lazily inside the generator so a missing
        # GROQ_API_KEY (or any other construction error) is reported as an
        # SSE `error` event rather than a 500 status before the stream opens.
        self._chat_agent: ChatAgent | None = None
        self._extractor_agent: ChatExtractorAgent | None = None

    async def events(self) -> AsyncIterator[str]:
        """Produce `data: {...}\\n\\n` SSE frames end-to-end."""
        try:
            self._chat_agent = ChatAgent()
            self._extractor_agent = ChatExtractorAgent()
        except Exception:
            log.exception("Chat agent construction failed")
            yield _sse_frame({"type": "error", "error": MESSAGES["unauthorised"]})
            return
        try:
            async for frame in self._run():
                yield frame
        except Exception as exc:  # pragma: no cover - last-chance safety net
            log.exception("Unhandled error in SSE handler")
            yield _sse_frame({"type": "error", "error": user_safe_message(exc)})

    async def _run(self) -> AsyncIterator[str]:
        db = get_db()
        assistant_text_parts: list[str] = []
        last_assistant_before: str = ""

        # --- Step 1: persist user message, load history, open stream ---
        async with db.session() as session:
            leads_repo = LeadRepository(session)
            messages_repo = ConversationMessageRepository(session)

            lead = await leads_repo.get_by_id(self._lead_id)
            if lead is None:
                yield _sse_frame({"type": "error", "error": "lead not found"})
                return

            history = await messages_repo.list_for_lead(self._lead_id)
            if history:
                for msg in reversed(history):
                    if msg.role == MessageRole.ASSISTANT:
                        last_assistant_before = msg.content
                        break

            await messages_repo.append(
                lead_id=self._lead_id,
                role=MessageRole.USER,
                content=self._user_message,
            )
            # Reload full history (now includes the user turn) for the LLM.
            history = await messages_repo.list_for_lead(self._lead_id)
            await session.commit()

            # Snapshot lead state for the stream call — session will close after this.
            lead_snapshot = lead

            try:
                async for text_chunk in self._chat_agent.stream_reply(
                    lead=lead_snapshot, history=history
                ):
                    assistant_text_parts.append(text_chunk)
                    yield _sse_frame({"type": "token", "text": text_chunk})
            except ChatAgentError as exc:
                log.exception("Chat stream failed")
                yield _sse_frame({"type": "error", "error": str(exc)})
                return

        assistant_text = "".join(assistant_text_parts).strip()
        if not assistant_text:
            # Degenerate case: stream returned nothing. Emit a minimal fallback.
            assistant_text = (
                "Sorry — I lost my train of thought there. Could you say that one more time?"
            )

        # --- Step 2: persist assistant message, emit `done` IMMEDIATELY ---
        # The chat extractor agent + score update are deferred to a
        # background task so the user can start typing their next message
        # the instant the stream ends. The frontend fires a `useLeadDetail`
        # invalidate on `done` and a second one 2.5s later to catch the
        # delayed extractor state.
        async with db.session() as session:
            leads_repo = LeadRepository(session)
            messages_repo = ConversationMessageRepository(session)

            lead = await leads_repo.get_by_id(self._lead_id)
            if lead is None:  # pragma: no cover - deleted mid-stream
                yield _sse_frame({"type": "error", "error": "lead vanished mid-stream"})
                return

            assistant_msg = await messages_repo.append(
                lead_id=self._lead_id,
                role=MessageRole.ASSISTANT,
                content=assistant_text,
            )
            await session.commit()
            message_id = assistant_msg.id
            score_now = lead.qualification_score
            status_now = lead.status

        yield _sse_frame(
            {
                "type": "done",
                "message_id": message_id,
                "qualification_score": score_now,
                "status": status_now.value if hasattr(status_now, "value") else str(status_now),
            }
        )

        # Fire-and-forget: run the chat extractor agent in a task that owns
        # its own DB session. Best-effort (chat continuity > perfect
        # extraction): a missed fact stays on the chat agent's question plan
        # and gets asked again next turn.
        task = asyncio.create_task(
            _run_turn_extraction_bg(
                extractor_agent=self._extractor_agent,
                lead_id=self._lead_id,
                user_message=self._user_message,
                last_assistant_before=last_assistant_before,
            )
        )
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)


def _sse_frame(payload: dict) -> str:
    """Format a dict as a single SSE `data:` frame."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ----------------------------------------------------------------------
# Background chat extractor agent (runs after `done` so the UI unlocks instantly)
# ----------------------------------------------------------------------

_BACKGROUND_TASKS: set[asyncio.Task] = set()


async def _run_turn_extraction_bg(
    *,
    extractor_agent: ChatExtractorAgent,
    lead_id: str,
    user_message: str,
    last_assistant_before: str,
) -> None:
    """Run the chat extractor agent without blocking the SSE.

    Design note: this only records facts (contact details + question-plan
    answers). Scoring and status are the qualification agent's job, run when
    the broker clicks "Run qualification agent". This keeps the New /
    Qualified / Not qualified sections of the dashboard meaningful.
    """
    try:
        db = get_db()
        async with db.session() as session:
            leads_repo = LeadRepository(session)

            lead = await leads_repo.get_by_id(lead_id)
            if lead is None:
                return

            extractor_output = await extractor_agent.extract_turn(
                lead=lead,
                assistant_message=last_assistant_before,
                user_message=user_message,
            )

            extracted_fields_patch = (
                extractor_output.extracted_fields.model_dump(exclude_none=True)
                if extractor_output.extracted_fields
                else {}
            )

            full_name = extractor_output.full_name
            if not (full_name or lead.full_name) and last_assistant_before == GREETING_TEXT:
                # Safety net: the reply to our fixed opening question is the
                # name, and the name is what makes the lead visible to brokers.
                full_name = GreetingNameCapture().extract(user_message)

            # Contact details are regex-readable, so they never depend on the
            # extractor agent being available (rate limits, outages).
            contacts = ContactCapture()
            email = extractor_output.email or contacts.email(user_message)
            phone = extractor_output.phone or contacts.phone(user_message)

            await leads_repo.update_from_chat(
                lead,
                full_name=full_name,
                email=email,
                phone=phone,
                city=extractor_output.city,
                extracted_fields=extracted_fields_patch or None,
            )
            await session.commit()
    except Exception:  # noqa: BLE001 — best-effort, must never raise outward.
        log.exception("Background turn-extraction failed for lead %s", lead_id)
