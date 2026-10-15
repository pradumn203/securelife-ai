"""Declarative base and shared mixins for all ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """SQLAlchemy declarative base. All models inherit from this."""


class UUIDPrimaryKeyMixin:
    """Adds a string UUID primary key."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)


class TimestampMixin:
    """Adds created_at / updated_at with server-side defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.current_timestamp(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.current_timestamp(),
        nullable=False,
    )
