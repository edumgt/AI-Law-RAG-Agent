import uuid

from app.database.postgres import get_session_factory
from app.models import AuditEvent
from app.models.base import SYSTEM_USER_ID


def _resolve_user_id(raw: str) -> uuid.UUID | None:
    if not raw:
        return None
    if raw == "quant_system":
        return SYSTEM_USER_ID
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


async def audit(user_id: str, client_id: str, event_type: str, payload: dict) -> None:
    try:
        session_factory = get_session_factory()
        async with session_factory() as db:
            db.add(AuditEvent(
                user_id=_resolve_user_id(user_id),
                client_id=client_id,
                event_type=event_type,
                payload=payload,
            ))
            await db.commit()
    except Exception:
        pass  # 감사 로그 실패는 무시
