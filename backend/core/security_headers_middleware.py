"""
HTTP セキュリティヘッダーミドルウェア

全レスポンスにセキュリティヘッダーを付与し、
クリックジャッキング・XSS・SSL ダウングレード攻撃等を防止する。

準拠:
- ISO27001:2022 A.8.22 Web フィルタリング
- NIST CSF 2.0 PR.PT-3 通信・接続セキュリティ
- OWASP Security Headers Project
"""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """レスポンス全体にセキュリティヘッダーを付与する"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # クリックジャッキング防止 (ISO27001 A.8.22)
        response.headers["X-Frame-Options"] = "DENY"

        # MIME タイプスニッフィング防止
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS フィルター有効化 (レガシーブラウザ向け)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HTTPS 強制 (SSL ストリッピング防止)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # リファラポリシー (情報漏洩防止)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # コンテンツセキュリティポリシー
        # API サーバなので JS 実行を禁止し default-src を none に設定
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )

        # キャッシュ制御 (認証情報の意図しないキャッシュ防止)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"

        return response
