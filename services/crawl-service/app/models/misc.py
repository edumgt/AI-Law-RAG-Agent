from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, CreatedAtMixin, UUIDPkMixin, UpdatedAtMixin


class AuditEvent(Base, UUIDPkMixin, CreatedAtMixin):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class NotificationSettings(Base, UUIDPkMixin, UpdatedAtMixin):
    __tablename__ = "notification_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    channels: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    telegram_token: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    telegram_chat_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    slack_webhook_url: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    email_to: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    email_host: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    email_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    email_user: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    email_password: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    email_from: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    kakao_api_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    kakao_api_secret: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    kakao_sender_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    kakao_phone: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    sms_api_key: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    sms_api_secret: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    sms_from: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    sms_to: Mapped[str] = mapped_column(String(30), nullable=False, default="")


class NotificationLog(Base, UUIDPkMixin, CreatedAtMixin):
    __tablename__ = "notification_log"
    __table_args__ = (Index("ix_notification_log_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    channels: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class CrawledDoc(Base, UUIDPkMixin):
    __tablename__ = "crawled_docs"
    __table_args__ = (Index("ix_crawled_docs_crawled_at", "crawled_at"),)

    url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UploadedDoc(Base, UUIDPkMixin, CreatedAtMixin):
    __tablename__ = "uploaded_docs"
    __table_args__ = (Index("ix_uploaded_docs_user_created", "user_id", "created_at"),)

    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    uploader: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(400), nullable=False)
    chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ext: Mapped[str] = mapped_column(String(20), nullable=False, default="")
