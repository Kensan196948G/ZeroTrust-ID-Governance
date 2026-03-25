"""
レート制限ミドルウェア（スライディングウィンドウ方式）

認証エンドポイントへのブルートフォース攻撃を防止し、
一般 API への過負荷リクエストを制御する。

設計方針:
- Redis が利用可能な場合は Redis ベースのカウンタを使用（分散環境対応）
- Redis 未起動時はインメモリカウンタにフォールバック（単一インスタンスのみ有効）
- 制限超過時は 429 Too Many Requests を返す

準拠:
- ISO27001:2022 A.8.3 情報へのアクセス制限
- ISO27001:2022 A.5.17 認証情報の管理
- NIST CSF 2.0 PR.AC-7 ユーザー・デバイス認証（試行回数制限）
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = structlog.get_logger(__name__)

# レート制限設定（エンドポイント別）
_RATE_LIMITS: dict[str, tuple[int, int]] = {
    # パスプレフィックス: (最大リクエスト数, ウィンドウ秒数)
    "/api/v1/auth/login": (10, 60),    # 認証: 10 req/min (ブルートフォース防止)
    "/api/v1/auth/refresh": (20, 60),  # リフレッシュ: 20 req/min
    "/api/v1/auth": (30, 60),          # 認証系全体: 30 req/min
    "/api/v1": (200, 60),              # 一般 API: 200 req/min
}

# Redis キープレフィックス
_RATE_KEY_PREFIX = "zt:ratelimit:"

# インメモリフォールバック用カウンタ {key: [(timestamp), ...]}
_memory_counters: dict[str, list[float]] = defaultdict(list)
_memory_lock = Lock()


def _get_rate_limit(path: str) -> tuple[int, int]:
    """パスに対応するレート制限値を返す（最も具体的なマッチを使用）"""
    for prefix, limit in sorted(_RATE_LIMITS.items(), key=lambda x: -len(x[0])):
        if path.startswith(prefix):
            return limit
    return (200, 60)  # デフォルト


def _check_rate_limit_redis(key: str, max_requests: int, window_secs: int) -> bool:
    """Redis スライディングウィンドウでレート制限チェック

    Returns:
        True: 制限内（リクエスト許可）
        False: 制限超過
    """
    try:
        from core.token_store import _get_redis  # noqa: PLC0415

        r = _get_redis()
        now = time.time()
        pipe = r.pipeline()
        # 古いエントリを削除してカウント
        pipe.zremrangebyscore(key, 0, now - window_secs)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_secs + 1)
        results = pipe.execute()
        count = results[2]
        return count <= max_requests
    except Exception as exc:
        logger.debug("Rate limit Redis unavailable, falling back to memory", error=str(exc))
        return None  # type: ignore[return-value]


def _check_rate_limit_memory(key: str, max_requests: int, window_secs: int) -> bool:
    """インメモリスライディングウィンドウでレート制限チェック"""
    now = time.time()
    with _memory_lock:
        timestamps = _memory_counters[key]
        # ウィンドウ外のエントリを削除
        cutoff = now - window_secs
        _memory_counters[key] = [t for t in timestamps if t > cutoff]
        _memory_counters[key].append(now)
        return len(_memory_counters[key]) <= max_requests


class RateLimitMiddleware(BaseHTTPMiddleware):
    """IP アドレスベースのレート制限ミドルウェア"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # API パス以外はスキップ
        if not path.startswith("/api/"):
            return await call_next(request)

        # クライアント IP 取得 (X-Forwarded-For 優先)
        forwarded_for = request.headers.get("X-Forwarded-For")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (
            request.client.host if request.client else "unknown"
        )

        max_req, window = _get_rate_limit(path)
        redis_key = f"{_RATE_KEY_PREFIX}{client_ip}:{path}"

        # Redis → メモリの順でチェック
        allowed = _check_rate_limit_redis(redis_key, max_req, window)
        if allowed is None:
            allowed = _check_rate_limit_memory(redis_key, max_req, window)

        if not allowed:
            logger.warning(
                "Rate limit exceeded",
                client_ip=client_ip,
                path=path,
                limit=max_req,
                window_secs=window,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "data": None,
                    "errors": [{"message": "Too many requests. Please try again later."}],
                },
                headers={
                    "Retry-After": str(window),
                    "X-RateLimit-Limit": str(max_req),
                    "X-RateLimit-Window": str(window),
                },
            )

        response = await call_next(request)
        # レート制限情報をレスポンスヘッダーに含める
        response.headers["X-RateLimit-Limit"] = str(max_req)
        return response
