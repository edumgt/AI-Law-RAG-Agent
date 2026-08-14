"""PostgreSQL 비동기 연결 계층 (SQLAlchemy 2.0 + asyncpg).

app/database/mongo.py가 쓰던 모듈 전역 싱글톤 + 미연결시 RuntimeError 패턴을
그대로 따른다. FastAPI 라우트에서는 `db=Depends(get_pg_session)`으로 주입한다.
"""
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def connect_postgres() -> None:
    global _engine, _session_factory
    _engine = create_async_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=5,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    async with _engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def close_postgres() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("PostgreSQL not connected")
    return _session_factory


async def get_pg_session() -> AsyncIterator[AsyncSession]:
    """FastAPI Depends용 PostgreSQL 세션 의존성."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
