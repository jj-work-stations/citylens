# app/models/audit.py
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_user_id",       "user_id"),
        Index("ix_audit_created_at",    "created_at"),
        Index("ix_audit_action",        "action"),
        Index("ix_audit_resource_type", "resource_type"),
        Index("ix_audit_status_code",   "status_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Who (plain FK columns ONLY — no relationship) ─────────
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_role:  Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_phone: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)

    # ── Request ────────────────────────────────────────────────
    method:       Mapped[str]            = mapped_column(String(10),  nullable=False)
    path:         Mapped[str]            = mapped_column(String(500), nullable=False)
    query_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    request_body: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # ── Response ───────────────────────────────────────────────
    status_code:      Mapped[int]           = mapped_column(Integer, nullable=False)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Classification ─────────────────────────────────────────
    action:        Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resource_id:   Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Client ─────────────────────────────────────────────────
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text,       nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )