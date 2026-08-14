"""대화 이력 저장 및 상태 관리 API.

대화 스레드(Conversation) 개념을 도입하여 여러 세션에 걸친
대화 이력을 구조적으로 관리합니다.

PostgreSQL 테이블:
  conversations – 스레드 메타데이터
  chats         – 메시지 (conversation_id FK로 스레드에 연결)

엔드포인트:
  POST   /api/conversations            – 새 대화 스레드 생성
  GET    /api/conversations            – 내 대화 목록
  GET    /api/conversations/{cid}      – 스레드 상세 + 메시지 목록
  PATCH  /api/conversations/{cid}      – 제목 수정
  DELETE /api/conversations/{cid}      – 스레드 + 메시지 삭제
  GET    /api/conversations/active     – 현재 활성 스레드
  POST   /api/conversations/{cid}/activate – 특정 스레드를 활성으로 설정
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_pg_session
from app.models import Chat, Conversation
from app.lib.jwt_auth import get_current_user_any
from app.lib.user_state import (
    clear_active_conversation,
    get_active_conversation,
    get_user_state,
    set_active_conversation,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _oid(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except Exception:
        raise HTTPException(400, "유효하지 않은 대화 ID입니다.")


# ── 스키마 ─────────────────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ConversationPatch(BaseModel):
    title: str


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _serialize(conv: Conversation) -> dict:
    return {
        "id": str(conv.id),
        "user_id": str(conv.user_id),
        "title": conv.title,
        "message_count": conv.message_count,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    }


def _serialize_message(msg: Chat) -> dict:
    return {
        "id": str(msg.id),
        "user_id": str(msg.user_id),
        "client_id": msg.client_id,
        "conversation_id": str(msg.conversation_id),
        "question": msg.question,
        "answer": msg.answer,
        "steps": msg.steps,
        "citations": msg.citations,
        "created_at": msg.created_at.isoformat(),
    }


async def _assert_owner(db: AsyncSession, cid: str, user_id: str) -> Conversation:
    """스레드가 존재하고 현재 사용자 소유인지 확인합니다."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == _oid(cid), Conversation.user_id == _oid(user_id))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "대화를 찾을 수 없습니다.")
    return conv


# ── 엔드포인트 ─────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_conversation(
    body: ConversationCreate,
    user=Depends(get_current_user_any),
    db: AsyncSession = Depends(get_pg_session),
):
    """새 대화 스레드를 생성하고 활성 스레드로 설정합니다."""
    title = body.title or f"대화 {_now()[:10]}"
    conv = Conversation(user_id=uuid.UUID(user["id"]), title=title, message_count=0)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    cid = str(conv.id)
    await set_active_conversation(user["id"], cid)
    return {"id": cid, "title": title, "active": True}


@router.get("")
async def list_conversations(
    limit: int = 20,
    offset: int = 0,
    user=Depends(get_current_user_any),
    db: AsyncSession = Depends(get_pg_session),
):
    """내 대화 스레드 목록을 최신 순으로 반환합니다."""
    uid = _oid(user["id"])
    active_cid = await get_active_conversation(user["id"])
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == uid)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    items = []
    for conv in result.scalars().all():
        item = _serialize(conv)
        item["active"] = item["id"] == active_cid
        items.append(item)
    total = await db.scalar(select(func.count()).select_from(Conversation).where(Conversation.user_id == uid))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/active")
async def get_active(
    user=Depends(get_current_user_any),
    db: AsyncSession = Depends(get_pg_session),
):
    """현재 활성 대화 스레드를 반환합니다."""
    cid = await get_active_conversation(user["id"])
    if not cid:
        return {"active_conversation": None}
    result = await db.execute(
        select(Conversation).where(Conversation.id == _oid(cid), Conversation.user_id == _oid(user["id"]))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        await clear_active_conversation(user["id"])
        return {"active_conversation": None}
    return {"active_conversation": _serialize(conv)}


@router.get("/{cid}")
async def get_conversation(
    cid: str,
    msg_limit: int = 50,
    msg_offset: int = 0,
    user=Depends(get_current_user_any),
    db: AsyncSession = Depends(get_pg_session),
):
    """스레드 메타데이터와 메시지 목록을 함께 반환합니다."""
    conv = await _assert_owner(db, cid, user["id"])

    result = await db.execute(
        select(Chat)
        .where(Chat.conversation_id == conv.id, Chat.user_id == _oid(user["id"]))
        .order_by(Chat.created_at.asc())
        .offset(msg_offset)
        .limit(msg_limit)
    )
    messages = [_serialize_message(m) for m in result.scalars().all()]

    msg_total = await db.scalar(
        select(func.count()).select_from(Chat).where(Chat.conversation_id == conv.id, Chat.user_id == _oid(user["id"]))
    )

    out = _serialize(conv)
    out["messages"] = messages
    out["msg_total"] = msg_total
    return out


@router.patch("/{cid}")
async def update_conversation(
    cid: str,
    body: ConversationPatch,
    user=Depends(get_current_user_any),
    db: AsyncSession = Depends(get_pg_session),
):
    """대화 제목을 수정합니다."""
    conv = await _assert_owner(db, cid, user["id"])
    conv.title = body.title
    await db.commit()
    return {"ok": True, "title": body.title}


@router.delete("/{cid}", status_code=204)
async def delete_conversation(
    cid: str,
    user=Depends(get_current_user_any),
    db: AsyncSession = Depends(get_pg_session),
):
    """스레드와 해당 스레드의 모든 메시지를 삭제합니다."""
    conv = await _assert_owner(db, cid, user["id"])
    await db.execute(delete(Chat).where(Chat.conversation_id == conv.id))
    await db.delete(conv)
    await db.commit()

    # 활성 스레드가 삭제된 경우 초기화
    if await get_active_conversation(user["id"]) == cid:
        await clear_active_conversation(user["id"])


@router.post("/{cid}/activate")
async def activate_conversation(
    cid: str,
    user=Depends(get_current_user_any),
    db: AsyncSession = Depends(get_pg_session),
):
    """특정 스레드를 현재 활성 대화로 설정합니다."""
    await _assert_owner(db, cid, user["id"])
    await set_active_conversation(user["id"], cid)
    return {"ok": True, "active_conversation_id": cid}


@router.get("/{cid}/messages")
async def list_messages(
    cid: str,
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_current_user_any),
    db: AsyncSession = Depends(get_pg_session),
):
    """특정 스레드의 메시지 목록을 페이지네이션으로 반환합니다."""
    conv = await _assert_owner(db, cid, user["id"])
    result = await db.execute(
        select(Chat)
        .where(Chat.conversation_id == conv.id, Chat.user_id == _oid(user["id"]))
        .order_by(Chat.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    messages = [_serialize_message(m) for m in result.scalars().all()]
    total = await db.scalar(
        select(func.count()).select_from(Chat).where(Chat.conversation_id == conv.id, Chat.user_id == _oid(user["id"]))
    )
    return {"items": messages, "total": total}
