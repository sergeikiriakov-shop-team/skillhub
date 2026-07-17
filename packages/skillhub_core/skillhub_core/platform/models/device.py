"""The OAuth 2.0 Device Authorization Grant (RFC 8628) state — used by the stdio MCP."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import DEVICE_PENDING, Base


class DeviceCode(Base):
    """One in-flight OAuth 2.0 Device Authorization Grant (RFC 8628). We store only the SHA-256 of
    the ``device_code``; ``user_code`` is the short human-typed code (worthless without the
    device_code, so kept plaintext)."""

    __tablename__ = "device_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(12), default=DEVICE_PENDING)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    client_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    interval: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
