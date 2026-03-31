"""
ZeroTrust-ID-Governance バックエンド API
FastAPI アプリケーションエントリーポイント

準拠: ISO27001 A.5.15〜A.8.2 / NIST CSF PROTECT PR.AA
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from api.v1 import access, audit, auth, roles, users, workflows
from core.audit_middleware import AuditLoggingMiddleware
from core.config import settings
from core.rate_limit_middleware import RateLimitMiddleware
from core.security_headers_middleware import SecurityHeadersMiddleware
from models import base  # noqa: F401 – テーブル登録のため必要

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動・終了時の処理"""
    logger.info("Starting ZeroTrust-ID-Governance API", version=settings.APP_VERSION)
    yield
    logger.info("Shutting down ZeroTrust-ID-Governance API")


app = FastAPI(
    title="ZeroTrust-ID-Governance API",
    description="""
## ゼロトラスト ID統合ガバナンスシステム

EntraID Connect × HENGEONE × AD 統合アイデンティティ管理プラットフォーム

### 準拠規格
- ISO27001:2022 A.5.15〜A.8.2
- NIST CSF 2.0 PROTECT PR.AA
- ISO20000-1:2018 アクセス管理
""",
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/api/redoc" if settings.APP_ENV != "production" else None,
    lifespan=lifespan,
)

# --- ミドルウェア設定 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

# HTTP セキュリティヘッダー付与（ISO27001 A.8.22 / NIST CSF PR.PT-3）
# ※ 最外層に置くことで全レスポンスに適用
app.add_middleware(SecurityHeadersMiddleware)

# レート制限（ISO27001 A.8.3 / NIST CSF PR.AC-7）
app.add_middleware(RateLimitMiddleware)

# 監査ログ自動記録（ISO27001 A.8.15 / NIST CSF DE.CM-01）
# ※ TrustedHostMiddleware より内側に置くことで信頼済みホストのみ記録
app.add_middleware(AuditLoggingMiddleware)


# --- グローバル例外ハンドラ ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未処理例外のキャッチオール

    ISO27001 A.8.16: セキュリティ監視 — サーバサイドログのみに詳細を記録し
    クライアントへは汎用メッセージを返す（情報漏洩防止）
    """
    is_production = settings.APP_ENV == "production"
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=not is_production,  # 開発環境のみスタックトレースを出力
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "data": None,
            "errors": [{"message": "Internal server error"}],
        },
    )


# --- ルーター登録 ---
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(users.router, prefix="/api/v1", tags=["Users"])
app.include_router(roles.router, prefix="/api/v1", tags=["Roles"])
app.include_router(access.router, prefix="/api/v1", tags=["Access Requests"])
app.include_router(workflows.router, prefix="/api/v1", tags=["Workflows"])
app.include_router(audit.router, prefix="/api/v1", tags=["Audit Logs"])


# --- Prometheus メトリクス（内部監視用 /metrics エンドポイント）---
# ISO27001 A.8.16: セキュリティ監視 / NIST CSF DE.CM-01: 継続的モニタリング
Instrumentator().instrument(app).expose(app, include_in_schema=False, tags=["System"])


# --- ヘルスチェック ---
@app.get("/health", tags=["System"])
@app.get("/api/v1/health", tags=["System"])
async def health_check() -> dict:
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
    }
