"""
認証 API（ログアウト・トークンリフレッシュ）

準拠: ISO27001 A.5.15 アクセス制御 / NIST CSF PR.AA-01 アクセス認証
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel

from core.auth import CurrentUser, get_current_user
from core.security import create_access_token, create_refresh_token, decode_token
from core.token_store import is_token_revoked, revoke_token

router = APIRouter()
_bearer_scheme = HTTPBearer(auto_error=False)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


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
