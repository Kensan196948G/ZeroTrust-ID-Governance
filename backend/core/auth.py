"""
FastAPI 認証 Dependency
Bearer トークン検証と現在ユーザー取得

準拠: ISO27001 A.5.15 アクセス制御ポリシー / NIST CSF PR.AA-01
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from core.security import decode_token
from core.token_store import is_token_revoked

# Bearer スキーム（auto_error=False で 401 を自前で返す）
_bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    """認証済みユーザー情報（依存性注入で受け取る値オブジェクト）"""

    def __init__(self, user_id: str, roles: list[str], email: str | None = None) -> None:
        self.user_id = user_id
        self.roles = roles
        self.email = email

    def has_role(self, role: str) -> bool:
        return role in self.roles


def _unauthorized(detail: str = "認証が必要です") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """Bearer トークンを検証して CurrentUser を返す FastAPI Dependency

    Usage:
        @router.get("/protected")
        async def protected(user: CurrentUser = Depends(get_current_user)):
            return {"user_id": user.user_id}
    """
    if credentials is None:
        raise _unauthorized()

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise _unauthorized("トークンが無効または期限切れです")

    # type クレームで refresh トークンの誤用を防ぐ
    if payload.get("type") != "access":
        raise _unauthorized("アクセストークンが必要です")

    # Redis ブラックリストチェック（ログアウト・強制失効済みトークンを拒否）
    jti: str | None = payload.get("jti")
    if jti and is_token_revoked(jti):
        raise _unauthorized("トークンは失効済みです")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise _unauthorized("トークンに subject が含まれていません")

    roles: list[str] = payload.get("roles", [])
    email: str | None = payload.get("email")

    return CurrentUser(user_id=user_id, roles=roles, email=email)


def require_role(required_role: str):
    """特定ロールを必須とする Dependency ファクトリ（sync 関数）

    Usage:
        @router.delete("/users/{id}")
        async def delete_user(user=Depends(require_role("GlobalAdmin"))):
            ...
    """

    async def _check(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current.has_role(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"ロール '{required_role}' が必要です",
            )
        return current

    return _check
