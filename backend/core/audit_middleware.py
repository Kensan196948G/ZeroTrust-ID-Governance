"""
監査ログ自動記録ミドルウェア

全 API リクエストを AuditLog テーブルへ自動記録する。
パスワード等の機密情報はログに含まない。

準拠:
- ISO27001:2022 A.8.15 ログ記録 / A.8.16 監視活動
- NIST CSF 2.0 DE.CM-01 ネットワーク活動の監視
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import Request, Response
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from core.database import AsyncSessionLocal
from core.security import decode_token
from models.audit_log import AuditLog

logger = structlog.get_logger(__name__)

# 監査ログを記録しないパス（ヘルスチェック・静的リソース）
_SKIP_PATHS = frozenset({
    "/health",
    "/api/v1/health",
    "/api/docs",
    "/api/redoc",
    "/openapi.json",
})

# HTTP メソッド → イベント種別マッピング
_METHOD_TO_EVENT = {
    "GET": "api_read",
    "POST": "api_create",
    "PATCH": "api_update",
    "PUT": "api_update",
    "DELETE": "api_delete",
}


def _extract_user_from_request(request: Request) -> tuple[str | None, list[str]]:
    """Authorization ヘッダーから user_id と roles を抽出する（失敗時は None）"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, []
    token = auth.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
        if payload.get("type") == "access":
            return payload.get("sub"), payload.get("roles", [])
    except JWTError:
        pass
    return None, []


def _get_client_ip(request: Request) -> str | None:
    """クライアント IP を取得（X-Forwarded-For 対応）"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """全 API リクエストを監査ログへ自動記録するミドルウェア

    ISO27001 A.8.15 の要件:
    - 誰が (actor_user_id)
    - どこから (actor_ip)
    - 何をしたか (action = HTTP method + path)
    - 結果は (result = success/failure)
    - いつ (event_time = UTC)
    を記録する。
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # スキップ対象パスはログしない
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        # API エンドポイントのみ記録（/api/v1/ プレフィックス）
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # ユーザー情報の事前取得
        user_id_str, roles = _extract_user_from_request(request)
        actor_user_id: uuid.UUID | None = None
        if user_id_str:
            try:
                actor_user_id = uuid.UUID(user_id_str)
            except ValueError:
                pass

        actor_ip = _get_client_ip(request)
        event_type = _METHOD_TO_EVENT.get(request.method, "api_request")
        action = f"{request.method} {request.url.path}"

        # エンドポイント実行
        response = await call_next(request)

        # 結果判定（2xx/3xx → success, それ以外 → failure）
        result = "success" if response.status_code < 400 else "failure"

        # 非同期 DB セッションで監査ログを書き込む
        await self._write_audit_log(
            event_type=event_type,
            action=action,
            result=result,
            actor_user_id=actor_user_id,
            actor_ip=actor_ip,
            status_code=response.status_code,
            roles=roles,
        )

        return response

    async def _write_audit_log(
        self,
        event_type: str,
        action: str,
        result: str,
        actor_user_id: uuid.UUID | None,
        actor_ip: str | None,
        status_code: int,
        roles: list[str],
    ) -> None:
        """AuditLog レコードを DB に書き込む（失敗しても本体リクエストに影響させない）"""
        try:
            async with AsyncSessionLocal() as session:
                log_entry = AuditLog(
                    event_type=event_type[:50],
                    source_system="ZeroTrust-API",
                    actor_user_id=actor_user_id,
                    actor_ip=actor_ip,
                    action=action[:100],
                    result=result[:20],
                    details={
                        "status_code": status_code,
                        "roles": roles,
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                session.add(log_entry)
                await session.commit()
        except Exception as exc:
            # 監査ログ書き込み失敗はサーバサイドにのみ記録（本体レスポンスには影響させない）
            logger.warning(
                "Audit log write failed",
                action=action,
                result=result,
                error=str(exc),
            )
