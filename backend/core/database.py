"""
データベース接続管理
SQLAlchemy 2.0 非同期エンジン（FastAPI 用）と
同期エンジン（Celery ワーカー用）を両方提供する。
"""

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.config import settings

# 非同期エンジン（asyncpg ドライバ使用）
_db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(
    _db_url,
    echo=settings.APP_ENV == "development",
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# 同期エンジン（Celery ワーカー用 - asyncio ループ外で使用）
_sync_db_url = settings.DATABASE_URL
if "postgresql+asyncpg://" in _sync_db_url:
    _sync_db_url = _sync_db_url.replace("postgresql+asyncpg://", "postgresql://")

sync_engine = create_engine(
    _sync_db_url,
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends で使用するDBセッション提供"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
