from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_pg_session
from app.lib.session import get_current_user
from app.models import (
    AuditEvent, BankProduct, BrokerSettings, Chat, CorporateCbStat,
    CrawledDoc, FundProduct, Order, PersonalCbStat, Portfolio,
)
from app.services.audit import audit

router = APIRouter(prefix="/api/admin")

FINANCIAL_MODELS = [PersonalCbStat, CorporateCbStat, BankProduct, FundProduct]
USER_MODELS = [Chat, Portfolio, Order, BrokerSettings, CrawledDoc, AuditEvent]


def _require_admin(user=Depends(get_current_user)):
    if "admin" not in user.get("roles", []):
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return user


@router.post("/reset")
async def reset_db(
    user=Depends(_require_admin),
    db: AsyncSession = Depends(get_pg_session),
):
    for model in FINANCIAL_MODELS + USER_MODELS:
        await db.execute(delete(model))
    await db.commit()

    table_names = [m.__tablename__ for m in FINANCIAL_MODELS + USER_MODELS]
    await audit(user["id"], "", "admin.db_reset", {"tables": table_names})
    return {"ok": True, "message": f"PostgreSQL {len(FINANCIAL_MODELS)}개 금융테이블 + {len(USER_MODELS)}개 사용자테이블 초기화 완료"}


@router.get("/stats")
async def db_stats(
    user=Depends(_require_admin),
    db: AsyncSession = Depends(get_pg_session),
):
    stats: dict = {}
    for model in FINANCIAL_MODELS + USER_MODELS:
        count = await db.scalar(select(func.count()).select_from(model))
        stats[f"postgres.{model.__tablename__}"] = count
    return {"stats": stats}


@router.get("/audit-log")
async def audit_log(
    event_type: str = Query("", description="이벤트 유형 부분 일치 필터 (예: order, broker, auto_trade)"),
    user_id:    str = Query("", description="사용자 ID 필터"),
    limit:      int = Query(100, ge=1, le=500),
    user=Depends(_require_admin),
    db: AsyncSession = Depends(get_pg_session),
):
    """감사 로그 조회 (관리자 전용). 최신순, 이벤트 유형/사용자로 필터링."""
    from app.services.audit import _resolve_user_id

    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type.ilike(f"%{event_type}%"))
    if user_id:
        stmt = stmt.where(AuditEvent.user_id == _resolve_user_id(user_id))

    result = await db.execute(stmt)
    events = [{
        "id": str(ev.id),
        "user_id": str(ev.user_id) if ev.user_id else "",
        "client_id": ev.client_id,
        "event_type": ev.event_type,
        "payload": ev.payload,
        "created_at": ev.created_at.isoformat(),
    } for ev in result.scalars().all()]
    return {"events": events, "count": len(events)}
