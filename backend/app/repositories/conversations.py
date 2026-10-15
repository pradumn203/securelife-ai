"""ConversationMessageRepository — append + fetch messages for a lead."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data_models.conversation_message import ConversationMessage, MessageRole


class ConversationMessageRepository:
    """SQLAlchemy query encapsulation for ConversationMessage."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        lead_id: str,
        role: MessageRole,
        content: str,
        token_count: int | None = None,
    ) -> ConversationMessage:
        """Insert a single message. Caller controls commit."""
        message = ConversationMessage(
            lead_id=lead_id,
            role=role,
            content=content,
            token_count=token_count,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_for_lead(
        self, lead_id: str, *, include_system: bool = True
    ) -> list[ConversationMessage]:
        """Return messages in chronological order."""
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.lead_id == lead_id)
            .order_by(ConversationMessage.created_at.asc())
        )
        if not include_system:
            stmt = stmt.where(ConversationMessage.role != MessageRole.SYSTEM)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_lead(self, lead_id: str) -> int:
        stmt = select(ConversationMessage.id).where(
            ConversationMessage.lead_id == lead_id
        )
        result = await self._session.execute(stmt)
        return len(result.scalars().all())
