"""
JWT セキュリティユーティリティ
アクセストークン・リフレッシュトークンの生成と検証

準拠: ISO27001 A.8.2 情報アクセス制限 / NIST CSF PR.AA-02
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import settings

# --- パスワードハッシュコンテキスト（bcrypt）---
# OWASP Password Storage Cheat Sheet 2024: rounds >= 12 推奨
# ISO27001 A.8.1: 認証情報の強度基準
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=13,
)


def hash_password(plain: str) -> str:
    """プレーンテキストパスワードを bcrypt でハッシュ化"""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """パスワードを検証する"""
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """JWT アクセストークンを生成する

    Args:
        subject: トークンの主体（通常はユーザーID）
        extra_claims: 追加クレーム（roles, email 等）
        expires_delta: カスタム有効期限（省略時は設定値を使用）

    Returns:
        署名済み JWT 文字列
    """
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """JWT リフレッシュトークンを生成する"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """JWT トークンをデコード・検証する

    Args:
        token: JWT 文字列

    Returns:
        デコードされたペイロード辞書

    Raises:
        JWTError: トークンが無効・期限切れの場合
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def get_subject_from_token(token: str) -> str | None:
    """トークンから subject (ユーザーID) を安全に取得する

    検証失敗時は None を返す（例外を握り潰さない用途では decode_token を使用すること）
    """
    try:
        payload = decode_token(token)
        return str(payload.get("sub"))
    except JWTError:
        return None
