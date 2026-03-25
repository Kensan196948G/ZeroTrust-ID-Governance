"""
認証 API（ログイン・ログアウト・トークンリフレッシュ）

準拠: ISO27001 A.5.15 アクセス制御 / NIST CSF PR.AA-01 アクセス認証
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import CurrentUser, get_current_user
from core.config import settings
from core.database import get_db
from core.security import create_access_token, create_refresh_token, decode_token
from core.token_store import is_token_revoked, revoke_token
from models.user import User

router = APIRouter()
_bearer_scheme = HTTPBearer(auto_error=False)

# テスト用管理者アカウント（APP_ENV=test 時のみ有効）
_TEST_ADMIN_USERNAME = "admin"
_TEST_ADMIN_PASSWORD = "AdminPass123!"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="ログイン（テスト環境専用）",
)
async def login(payload_in: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """テスト/開発環境専用の JSON ログインエンドポイント。

    本番環境では 403 を返す。
    E2E テスト（Newman）がバックエンド認証フローを検証するために使用する。

    ISO27001 A.5.15: アクセス管理 — テスト環境でのみ有効な認証手段。
    """
    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="このエンドポイントは本番環境では使用できません",
        )

    if payload_in.username != _TEST_ADMIN_USERNAME or payload_in.password != _TEST_ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが正しくありません",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # テスト管理者ユーザーを取得または作成
    result = await db.execute(select(User).where(User.username == _TEST_ADMIN_USERNAME))
    user = result.scalar_one_or_none()

    if user is None:
        from datetime import date

        user = User(
            id=uuid.uuid4(),
            employee_id="E000001",
            username=_TEST_ADMIN_USERNAME,
            display_name="Test Admin",
            email="admin@example.com",
            user_type="admin",
            hire_date=date(2020, 1, 1),
            account_status="active",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    subject = str(user.id)
    access_token = create_access_token(subject, extra_claims={"roles": ["GlobalAdmin"]})
    refresh_token = create_refresh_token(subject)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="ログアウト（アクセストークン失効）",
)
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> Response:
    """現在のアクセストークンを Redis ブラックリストへ登録して無効化する。

    ISO27001 A.5.15: セッション終了時のアクセス権取り消し要件に対応。
    """
    if credentials is not None:
        try:
            payload = decode_token(credentials.credentials)
            jti: str | None = payload.get("jti")
            exp: int | None = payload.get("exp")
            if jti and exp:
                revoke_token(jti, exp)
        except JWTError:
            pass  # デコード失敗は無視（既に期限切れ等）
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="アクセストークン更新（リフレッシュトークン使用）",
)
async def refresh_tokens(payload_in: RefreshRequest) -> TokenResponse:
    """有効なリフレッシュトークンを受け取り、新しいアクセス/リフレッシュトークンペアを返す。

    ローテーション戦略: 旧リフレッシュトークンは使用後に失効させ、
    リプレイ攻撃を防ぐ。
    """
    try:
        payload = decode_token(payload_in.refresh_token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="リフレッシュトークンが無効または期限切れです",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="リフレッシュトークンが必要です",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 旧リフレッシュトークンの jti が失効済みでないか確認
    old_jti: str | None = payload.get("jti")
    old_exp: int | None = payload.get("exp")
    if old_jti and is_token_revoked(old_jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="リフレッシュトークンは失効済みです",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject: str | None = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="トークンに subject が含まれていません",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 旧リフレッシュトークンを失効（リプレイ攻撃防止）
    if old_jti and old_exp:
        revoke_token(old_jti, old_exp)

    # 新しいトークンペアを発行
    roles: list[str] = payload.get("roles", [])
    new_access = create_access_token(subject, extra_claims={"roles": roles})
    new_refresh = create_refresh_token(subject)

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)
