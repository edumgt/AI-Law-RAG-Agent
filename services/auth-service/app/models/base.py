"""SQLAlchemy declarative base + 공통 컬럼 믹스인."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class UUIDPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# Mongo 시절 "quant_system" sentinel user_id를 대체하는 고정 UUID 시스템 유저.
# 자동매매 등 실제 회원가입 없이 시스템이 스스로 생성하는 레코드의 user_id로 쓰인다.
SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
