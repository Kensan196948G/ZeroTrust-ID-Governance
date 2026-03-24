"""
Alembic マイグレーション環境設定
asyncio 対応（asyncpg ドライバ使用）

準拠: ISO27001 A.8.9 設定管理
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from alembic import context

# モデルの Base と全テーブルをインポート（autogenerate のため）
from models.base import Base  # noqa: E402
import models.access_request  # noqa: F401, E402
import models.audit_log  # noqa: F401, E402
import models.department  # noqa: F401, E402
import models.resource  # noqa: F401, E402
import models.role  # noqa: F401, E402
import models.user  # noqa: F401, E402

from core.config import settings  # noqa: E402

# Alembic Config オブジェクト
config = context.config

# ロギング設定
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 用のメタデータ
target_metadata = Base.metadata


def get_url() -> str:
    """環境変数から DB URL を取得（asyncpg ドライバに変換）"""
    url = settings.DATABASE_URL
    # asyncpg は asyncio 専用ドライバ
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """オフラインモード: エンジン接続なしで SQL スクリプトを生成する"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """オンラインモード: 実際の DB に接続してマイグレーションを実行する"""
    config_section = config.get_section(config.config_ini_section, {})
    config_section["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        config_section,
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda conn: context.configure(
                connection=conn,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )
        )

        async with connection.begin():
            await connection.run_sync(lambda conn: context.run_migrations())

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
