"""
トークン失効ストア（Redis ベース）

ログアウト・強制失効時に JWT の jti（JWT ID）を Redis へ登録し、
以降の検証時にブラックリストチェックを行う。

設計方針:
- Redis 未起動・接続失敗時は警告のみ（本体リクエストに影響させない）
- TTL = トークンの残存有効期限（expire 時刻 - 現在時刻）に自動設定
  → ブラックリストが際限なく肥大化することを防ぐ

準拠:
- ISO27001:2022 A.5.15 アクセス制御（強制ログアウト・失効制御）
- NIST CSF 2.0 PR.AC-01 ID 管理・認証・アクセス制御
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from core.config import settings

logger = structlog.get_logger(__name__)

# Redis キープレフィックス
_KEY_PREFIX = "zt:revoked_token:"


def _get_redis():
    """Redis クライアントを取得（遅延接続）"""
    import redis  # noqa: PLC0415 — ローカルインポートで import エラーを局所化

    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def revoke_token(jti: str, exp: int) -> None:
    """指定 jti をブラックリストに登録する

    Args:
        jti: JWT ID クレーム
        exp: JWT exp クレーム（UNIX タイムスタンプ）

    Note:
        Redis 接続失敗時はサーバサイドのみに記録（本体には影響しない）
    """
    try:
        r = _get_redis()
        now_ts = int(datetime.now(timezone.utc).timestamp())
        ttl = max(exp - now_ts, 1)  # 残存秒数（最低 1 秒）
        r.setex(f"{_KEY_PREFIX}{jti}", ttl, "1")
        logger.info("Token revoked", jti=jti, ttl=ttl)
    except Exception as exc:
        logger.warning("Failed to revoke token in Redis", jti=jti, error=str(exc))


def is_token_revoked(jti: str) -> bool:
    """指定 jti がブラックリストに存在するか確認する

    Args:
        jti: JWT ID クレーム

    Returns:
        True: 失効済み（ブラックリスト登録あり）
        False: 有効（未登録）または Redis 接続失敗時（フェイルオープン）

    Note:
        Redis 接続失敗時はフェイルオープン（有効と見なす）とし、
        可用性を優先する。セキュリティ要件が高い場合は
        フェイルクローズ（False → True）に変更すること。
    """
    try:
        r = _get_redis()
        return r.exists(f"{_KEY_PREFIX}{jti}") > 0
    except Exception as exc:
        logger.warning("Failed to check token revocation in Redis", jti=jti, error=str(exc))
        return False  # フェイルオープン: 可用性優先
